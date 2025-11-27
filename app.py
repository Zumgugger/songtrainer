from flask import Flask, render_template, request, jsonify, send_file, abort, Response
from werkzeug.utils import secure_filename
from database import get_db, init_db, ensure_indexes_and_normalize, ensure_audio_path_column, ensure_chart_path_column, ensure_repertoire_id_column, ensure_release_date_column, ensure_repertoire_sort_order_column
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTS = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}
ALLOWED_CHART_EXTS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.doc', '.docx'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database on first run
if not os.path.exists('songs.db'):
    init_db()
    ensure_audio_path_column()
    ensure_chart_path_column()
    ensure_repertoire_id_column()
    ensure_release_date_column()
    ensure_repertoire_sort_order_column()
    ensure_indexes_and_normalize()
else:
    # Ensure constraints exist and ordering is normalized on startup
    try:
        ensure_audio_path_column()
    except Exception:
        pass
    try:
        ensure_chart_path_column()
    except Exception:
        pass
    try:
        ensure_repertoire_id_column()
    except Exception:
        pass
    try:
        ensure_release_date_column()
    except Exception:
        pass
    try:
        ensure_repertoire_sort_order_column()
    except Exception:
        pass
    try:
        ensure_indexes_and_normalize()
    except Exception:
        pass

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Main song list page"""
    return render_template('index.html')

@app.route('/admin')
def admin():
    """Admin page for managing skills"""
    return render_template('admin.html')

# ==================== SONGS API ====================

@app.route('/api/songs', methods=['GET'])
def get_songs():
    """Get all songs with their skills, optionally filtered by repertoire"""
    repertoire_id = request.args.get('repertoire_id', type=int)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get songs, optionally filtered by repertoire
        if repertoire_id:
            songs = cursor.execute('''
                SELECT * FROM songs WHERE repertoire_id = ? ORDER BY song_number ASC
            ''', (repertoire_id,)).fetchall()
        else:
            songs = cursor.execute('''
                SELECT * FROM songs ORDER BY repertoire_id, song_number ASC
            ''').fetchall()
        
        songs_list = []
        for song in songs:
            # Get skills for this song
            skills = cursor.execute('''
                SELECT s.id, s.name, ss.is_mastered
                FROM skills s
                LEFT JOIN song_skills ss ON s.id = ss.skill_id AND ss.song_id = ?
                ORDER BY s.id
            ''', (song['id'],)).fetchall()
            
            song_dict = dict(song)
            song_dict['skills'] = [dict(skill) for skill in skills]
            
            # Calculate progress percentage
            total_skills = len([s for s in skills if s['is_mastered'] is not None])
            mastered_skills = len([s for s in skills if s['is_mastered'] == 1])
            song_dict['skills_progress'] = (mastered_skills / total_skills * 100) if total_skills > 0 else 0
            song_dict['practice_progress'] = (song['practice_count'] / song['practice_target'] * 100) if song['practice_target'] > 0 else 0
            
            songs_list.append(song_dict)
        
        return jsonify(songs_list)

@app.route('/api/songs', methods=['POST'])
def create_song():
    """Create a new song"""
    data = request.json
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO songs (title, artist, song_number, repertoire_id, priority, practice_target, date_added, release_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['title'],
            data['artist'],
            data.get('song_number', 1),
            data['repertoire_id'],
            data.get('priority', 'mid'),
            data.get('practice_target', 0),
            datetime.now().isoformat(),
            data.get('release_date'),
            data.get('notes', '')
        ))
        
        song_id = cursor.lastrowid
        
        # Add selected skills for this song
        if 'skill_ids' in data:
            for skill_id in data['skill_ids']:
                cursor.execute('''
                    INSERT INTO song_skills (song_id, skill_id, is_mastered)
                    VALUES (?, ?, 0)
                ''', (song_id, skill_id))
        
        return jsonify({'id': song_id, 'message': 'Song created successfully'}), 201

@app.route('/api/songs/<int:song_id>', methods=['PUT'])
def update_song(song_id):
    """Update a song"""
    data = request.json
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get current song_number before update
        old_song = cursor.execute('SELECT song_number, repertoire_id FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not old_song:
            return jsonify({'error': 'Song not found'}), 404
        
        old_number = old_song['song_number']
        # Accept new_number; if missing or invalid fallback to old_number
        new_number = data.get('song_number', old_number)
        if not isinstance(new_number, int):
            try:
                new_number = int(new_number)
            except Exception:
                new_number = old_number
        # Use existing repertoire_id (ignore changes via edit form to avoid cross-repertoire side-effects)
        repertoire_id = old_song['repertoire_id']
        
        # Reorder other songs if song_number changed (within same repertoire)
        if old_number != new_number:
            # Get total count of songs in repertoire
            max_row = cursor.execute('SELECT COUNT(*) as cnt FROM songs WHERE repertoire_id = ?', (repertoire_id,)).fetchone()
            max_count = max_row['cnt']
            
            # Allow any number - will be normalized to valid range
            # Clamp to reasonable bounds (1 to max_count)
            if new_number < 1:
                new_number = 1
            if new_number > max_count:
                new_number = max_count

            # Use sentinel approach: move target song out of the way first
            sentinel = max_count + 100  # Safe temporary value
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (sentinel, song_id))

            if new_number < old_number:
                # Moving up: shift songs in range [new_number, old_number-1] down by 1
                cursor.execute('''
                    UPDATE songs SET song_number = song_number + 1
                    WHERE repertoire_id = ? AND song_number >= ? AND song_number < ?
                ''', (repertoire_id, new_number, old_number))
            else:
                # Moving down: shift songs in range (old_number, new_number] up by 1
                cursor.execute('''
                    UPDATE songs SET song_number = song_number - 1
                    WHERE repertoire_id = ? AND song_number > ? AND song_number <= ?
                ''', (repertoire_id, old_number, new_number))

            # Place moved song at desired position
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (new_number, song_id))

            # Normalize all song_numbers to ensure clean 1..N sequence
            rows = cursor.execute('SELECT id FROM songs WHERE repertoire_id = ? ORDER BY song_number ASC', (repertoire_id,)).fetchall()
            for i, row in enumerate(rows, start=1):
                cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, row['id']))
        
        # Update the song itself
        cursor.execute('''
            UPDATE songs
            SET title = ?, artist = ?, song_number = ?, priority = ?, 
                practice_target = ?, release_date = ?, notes = ?
            WHERE id = ?
        ''', (
            data.get('title'),
            data.get('artist'),
            new_number,
            data.get('priority', 'mid'),
            data.get('practice_target', 0),
            data.get('release_date'),
            data.get('notes', ''),
            song_id
        ))
        
        # Update skills for this song
        if 'skill_ids' in data:
            # Get current skills to preserve mastery status
            current_skills = cursor.execute('''
                SELECT skill_id, is_mastered FROM song_skills WHERE song_id = ?
            ''', (song_id,)).fetchall()
            current_skills_dict = {row['skill_id']: row['is_mastered'] for row in current_skills}
            
            # Remove skills no longer selected
            selected_ids = set(data['skill_ids'])
            cursor.execute('DELETE FROM song_skills WHERE song_id = ? AND skill_id NOT IN ({})'.format(
                ','.join('?' * len(selected_ids)) if selected_ids else 'NULL'
            ), [song_id] + list(selected_ids) if selected_ids else [song_id])
            
            # Add new skills (preserve mastery for existing ones)
            for skill_id in selected_ids:
                is_mastered = current_skills_dict.get(skill_id, 0)
                cursor.execute('''
                    INSERT OR REPLACE INTO song_skills (song_id, skill_id, is_mastered)
                    VALUES (?, ?, ?)
                ''', (song_id, skill_id, is_mastered))
        
        return jsonify({'message': 'Song updated successfully'})

@app.route('/api/songs/<int:song_id>', methods=['DELETE'])
def delete_song(song_id):
    """Delete a song"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM songs WHERE id = ?', (song_id,))
        
        return jsonify({'message': 'Song deleted successfully'})

# ==================== PRACTICE API ====================

@app.route('/api/songs/<int:song_id>/practice', methods=['POST'])
def practice_song(song_id):
    """Mark a song as practiced (increment counter and update last practiced)"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Update practice count and last practiced date
        cursor.execute('''
            UPDATE songs
            SET practice_count = practice_count + 1,
                last_practiced = ?
            WHERE id = ?
        ''', (now, song_id))
        
        # Record practice session
        cursor.execute('''
            INSERT INTO practice_sessions (song_id, practiced_at)
            VALUES (?, ?)
        ''', (song_id, now))
        
        return jsonify({'message': 'Practice recorded successfully'})

@app.route('/api/songs/<int:song_id>/target/increase', methods=['POST'])
def increase_target(song_id):
    """Increase practice target by current practice count to reset progress bar while keeping history."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        result = cursor.execute(
            'SELECT practice_count, practice_target FROM songs WHERE id = ?',
            (song_id,)
        ).fetchone()
        
        if not result:
            return jsonify({'error': 'Song not found'}), 404
        
        # New target = current target + current count (resets progress bar to 0%)
        new_target = result['practice_target'] + result['practice_count']
        
        cursor.execute(
            'UPDATE songs SET practice_target = ? WHERE id = ?',
            (new_target, song_id)
        )
        
        return jsonify({'message': 'Target increased', 'new_target': new_target})

@app.route('/api/songs/<int:song_id>/skills/<int:skill_id>/toggle', methods=['POST'])
def toggle_skill(song_id, skill_id):
    """Toggle skill mastery status"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if song_skill exists
        result = cursor.execute('''
            SELECT is_mastered FROM song_skills
            WHERE song_id = ? AND skill_id = ?
        ''', (song_id, skill_id)).fetchone()
        
        if result is None:
            return jsonify({'error': 'Skill not assigned to this song'}), 404
        
        # Toggle the mastery status
        new_status = 0 if result['is_mastered'] == 1 else 1
        
        cursor.execute('''
            UPDATE song_skills
            SET is_mastered = ?
            WHERE song_id = ? AND skill_id = ?
        ''', (new_status, song_id, skill_id))
        
        return jsonify({'is_mastered': new_status})

@app.route('/api/songs/<int:song_id>/priority/toggle', methods=['POST'])
def toggle_priority(song_id):
    """Toggle priority: mid -> high -> low -> mid"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        result = cursor.execute('SELECT priority FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not result:
            return jsonify({'error': 'Song not found'}), 404
        
        # Cycle: mid -> high -> low -> mid
        priority_cycle = {'mid': 'high', 'high': 'low', 'low': 'mid'}
        new_priority = priority_cycle.get(result['priority'], 'mid')
        
        cursor.execute('UPDATE songs SET priority = ? WHERE id = ?', (new_priority, song_id))
        
        return jsonify({'priority': new_priority})

# ==================== ORDERING API ====================

@app.route('/api/songs/reorder', methods=['POST'])
def reorder_songs():
    """Reorder songs by array of song IDs in desired order; song_number becomes 1..N within repertoire."""
    data = request.json or {}
    ordered_ids = data.get('ordered_ids', [])
    repertoire_id = data.get('repertoire_id')

    if not isinstance(ordered_ids, list) or not all(isinstance(x, int) for x in ordered_ids):
        return jsonify({'error': 'ordered_ids must be an array of integers'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        # Get existing songs in this repertoire
        if repertoire_id:
            existing = cursor.execute(
                'SELECT id FROM songs WHERE repertoire_id = ? ORDER BY song_number ASC, id ASC',
                (repertoire_id,)
            ).fetchall()
        else:
            existing = cursor.execute('SELECT id FROM songs ORDER BY song_number ASC, id ASC').fetchall()
        
        existing_ids = [row['id'] for row in existing]

        # If client sent subset, append remaining in current order
        seen = set(ordered_ids)
        remaining = [sid for sid in existing_ids if sid not in seen]
        full_order = ordered_ids + remaining

        # Two-phase renumber to avoid UNIQUE conflicts: phase 1 assign high temp numbers
        base = 100000
        for i, sid in enumerate(full_order, start=1):
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (base + i, sid))
        # Phase 2 normalize to 1..N
        for i, sid in enumerate(full_order, start=1):
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, sid))

        return jsonify({'message': 'Order updated', 'count': len(full_order)})

# ==================== MEDIA SERVING ====================

def windows_path_to_wsl(win_path):
    """Convert Windows path to WSL path"""
    if not win_path:
        return None
    # Convert e:\ to /mnt/e/ and backslashes to forward slashes
    wsl_path = win_path.replace('e:\\', '/mnt/e/').replace('E:\\', '/mnt/e/')
    wsl_path = wsl_path.replace('\\', '/')
    return wsl_path

@app.route('/media/<int:song_id>')
def media(song_id):
    """Serve the linked audio file for a song, if present."""
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute('SELECT audio_path, title FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not row:
            abort(404)
        path = row['audio_path']
        if not path:
            abort(404)
        # Convert Windows path to WSL if needed
        wsl_path = windows_path_to_wsl(path)
        if not os.path.isfile(wsl_path):
            abort(404)
        # Force download with Content-Disposition header to trigger "Open with" dialog
        with open(wsl_path, 'rb') as f:
            data = f.read()
        response = Response(data, mimetype='audio/mpeg')
        response.headers['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
        return response

@app.route('/chart/<int:song_id>')
def chart(song_id):
    """Serve the linked chart file for a song, if present."""
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute('SELECT chart_path, title FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not row:
            abort(404)
        path = row['chart_path']
        if not path:
            abort(404)
        # Convert Windows path to WSL if needed
        wsl_path = windows_path_to_wsl(path)
        if not os.path.isfile(wsl_path):
            abort(404)
        return send_file(wsl_path, as_attachment=False, download_name=os.path.basename(path))

@app.route('/api/songs/<int:song_id>/audio', methods=['POST', 'DELETE'])
def manage_audio(song_id):
    """Attach (upload) or remove audio for a song.
    POST multipart/form-data with field 'file' to upload.
    DELETE to unlink existing audio_path.
    """
    with get_db() as conn:
        cur = conn.cursor()
        exist = cur.execute('SELECT id, audio_path FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not exist:
            return jsonify({'error': 'Song not found'}), 404

        if request.method == 'DELETE':
            cur.execute('UPDATE songs SET audio_path = NULL WHERE id = ?', (song_id,))
            return jsonify({'message': 'Audio link removed'})

        # POST upload
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTS:
            return jsonify({'error': f'Unsupported file type {ext}'}), 400
        save_name = f"song_{song_id}_{int(datetime.now().timestamp())}{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, save_name)
        file.save(save_path)
        cur.execute('UPDATE songs SET audio_path = ? WHERE id = ?', (save_path, song_id))
        return jsonify({'message': 'Audio uploaded', 'audio_path': save_path})

@app.route('/api/songs/<int:song_id>/chart', methods=['POST', 'DELETE'])
def manage_chart(song_id):
    """Attach (upload) or remove chart for a song.
    POST multipart/form-data with field 'file' to upload.
    DELETE to unlink existing chart_path.
    """
    with get_db() as conn:
        cur = conn.cursor()
        exist = cur.execute('SELECT id, chart_path FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not exist:
            return jsonify({'error': 'Song not found'}), 404

        if request.method == 'DELETE':
            cur.execute('UPDATE songs SET chart_path = NULL WHERE id = ?', (song_id,))
            return jsonify({'message': 'Chart link removed'})

        # POST upload
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_CHART_EXTS:
            return jsonify({'error': f'Unsupported file type {ext}'}), 400
        save_name = f"chart_{song_id}_{int(datetime.now().timestamp())}{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, save_name)
        file.save(save_path)
        cur.execute('UPDATE songs SET chart_path = ? WHERE id = ?', (save_path, song_id))
        return jsonify({'message': 'Chart uploaded', 'chart_path': save_path})

# ==================== SKILLS API ====================

@app.route('/api/skills', methods=['GET'])
def get_skills():
    """Get all skills"""
    with get_db() as conn:
        cursor = conn.cursor()
        skills = cursor.execute('SELECT * FROM skills ORDER BY id').fetchall()
        
        return jsonify([dict(skill) for skill in skills])

@app.route('/api/skills', methods=['POST'])
def create_skill():
    """Create a new skill"""
    data = request.json
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO skills (name) VALUES (?)', (data['name'],))
            skill_id = cursor.lastrowid
            
            return jsonify({'id': skill_id, 'message': 'Skill created successfully'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Skill already exists'}), 400

@app.route('/api/skills/<int:skill_id>', methods=['PUT'])
def update_skill(skill_id):
    """Update a skill"""
    data = request.json
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('UPDATE skills SET name = ? WHERE id = ?', (data['name'], skill_id))
            return jsonify({'message': 'Skill updated successfully'})
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Skill name already exists'}), 400

@app.route('/api/skills/<int:skill_id>', methods=['DELETE'])
def delete_skill(skill_id):
    """Delete a skill"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM skills WHERE id = ?', (skill_id,))
        
        return jsonify({'message': 'Skill deleted successfully'})

# ==================== REPERTOIRES API ====================

@app.route('/api/repertoires', methods=['GET'])
def get_repertoires():
    """Get all repertoires with their default skills"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        repertoires = cursor.execute('SELECT * FROM repertoires ORDER BY COALESCE(sort_order, id), id').fetchall()
        repertoires_list = []
        
        for rep in repertoires:
            rep_dict = dict(rep)
            
            # Get default skills for this repertoire
            skills = cursor.execute('''
                SELECT s.id, s.name
                FROM skills s
                INNER JOIN repertoire_skills rs ON s.id = rs.skill_id
                WHERE rs.repertoire_id = ?
                ORDER BY s.id
            ''', (rep['id'],)).fetchall()
            
            rep_dict['default_skills'] = [dict(skill) for skill in skills]
            
            # Get song count
            song_count = cursor.execute(
                'SELECT COUNT(*) as count FROM songs WHERE repertoire_id = ?',
                (rep['id'],)
            ).fetchone()
            rep_dict['song_count'] = song_count['count']
            
            repertoires_list.append(rep_dict)
        
        return jsonify(repertoires_list)

@app.route('/api/repertoires', methods=['POST'])
def create_repertoire():
    """Create a new repertoire"""
    data = request.json
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'INSERT INTO repertoires (name, date_created) VALUES (?, ?)',
                (data['name'], datetime.now().isoformat())
            )
            repertoire_id = cursor.lastrowid
            
            # Add default skills if provided
            if 'skill_ids' in data:
                for skill_id in data['skill_ids']:
                    cursor.execute(
                        'INSERT INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                        (repertoire_id, skill_id)
                    )
            
            return jsonify({'id': repertoire_id, 'message': 'Repertoire created successfully'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Repertoire name already exists'}), 400

@app.route('/api/repertoires/<int:repertoire_id>', methods=['PUT'])
def update_repertoire(repertoire_id):
    """Update a repertoire's name and default skills"""
    data = request.json
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if repertoire exists
        rep = cursor.execute('SELECT id FROM repertoires WHERE id = ?', (repertoire_id,)).fetchone()
        if not rep:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Update name
        if 'name' in data:
            try:
                cursor.execute(
                    'UPDATE repertoires SET name = ? WHERE id = ?',
                    (data['name'], repertoire_id)
                )
            except sqlite3.IntegrityError:
                return jsonify({'error': 'Repertoire name already exists'}), 400
        
        # Update default skills
        if 'skill_ids' in data:
            # Remove all current default skills
            cursor.execute('DELETE FROM repertoire_skills WHERE repertoire_id = ?', (repertoire_id,))
            
            # Add new default skills
            for skill_id in data['skill_ids']:
                cursor.execute(
                    'INSERT INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                    (repertoire_id, skill_id)
                )
        
        return jsonify({'message': 'Repertoire updated successfully'})

@app.route('/api/repertoires/<int:repertoire_id>', methods=['DELETE'])
def delete_repertoire(repertoire_id):
    """Delete a repertoire and cascade delete all songs in it"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get song count for confirmation message (already shown on frontend)
        song_count = cursor.execute(
            'SELECT COUNT(*) as count FROM songs WHERE repertoire_id = ?',
            (repertoire_id,)
        ).fetchone()
        
        # Delete all songs in this repertoire first (cascade)
        cursor.execute('DELETE FROM songs WHERE repertoire_id = ?', (repertoire_id,))
        
        # Delete the repertoire itself
        cursor.execute('DELETE FROM repertoires WHERE id = ?', (repertoire_id,))
        
        return jsonify({
            'message': 'Repertoire deleted successfully',
            'songs_deleted': song_count['count']
        })

@app.route('/api/repertoires/reorder', methods=['POST'])
def reorder_repertoires():
    """Persist a new ordering of repertoires given an array of repertoire IDs."""
    data = request.json or {}
    order = data.get('order')
    if not isinstance(order, list) or not all(isinstance(i, int) for i in order):
        return jsonify({'error': 'Invalid order payload'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        # Validate all IDs exist
        existing_ids = {row['id'] for row in cursor.execute('SELECT id FROM repertoires').fetchall()}
        if set(order) - existing_ids:
            return jsonify({'error': 'Unknown repertoire id(s) in order'}), 400

        for position, rep_id in enumerate(order, start=1):
            cursor.execute('UPDATE repertoires SET sort_order = ? WHERE id = ?', (position, rep_id))

    return jsonify({'message': 'Repertoires reordered successfully'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(debug=True, host='0.0.0.0', port=port)
