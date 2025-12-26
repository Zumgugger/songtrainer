from flask import Blueprint, request, jsonify, Response, send_file, g, abort
from database import get_db
from utils.decorators import login_required, admin_required
from utils.permissions import resolve_scope_user_id, require_song, require_repertoire
from utils.helpers import extract_mp3_duration
from datetime import datetime
import os
import shutil

try:
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

songs_bp = Blueprint('songs', __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTS = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}
ALLOWED_CHART_EXTS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.doc', '.docx', '.odt'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==================== HELPER FUNCTIONS ====================

def windows_path_to_wsl(win_path):
    """Convert Windows path to WSL path"""
    if not win_path:
        return None
    # Convert e:\ to /mnt/e/ and backslashes to forward slashes
    wsl_path = win_path.replace('e:\\', '/mnt/e/').replace('E:\\', '/mnt/e/')
    wsl_path = wsl_path.replace('\\', '/')
    return wsl_path

def resolve_chart_path(chart_path):
    """
    Resolve a chart path to work on any platform (Windows/WSL/Linux/Ubuntu).
    Handles Windows paths (e:\...), WSL paths (/mnt/e/...), and native Linux paths.
    """
    if not chart_path:
        return None
    
    # Normalize backslashes to forward slashes
    normalized = chart_path.replace('\\', '/')
    
    # If it's a Windows path (e.g., "e:/Drive/..."), convert to WSL
    if ':' in normalized and not normalized.startswith('/'):
        # Windows path like "e:/Drive/..." - convert to /mnt/e/Drive/...
        drive_letter = normalized[0].lower()
        rest = normalized[2:]  # Skip "e:/"
        return f'/mnt/{drive_letter}{rest}'
    
    # Otherwise return as-is (could be WSL /mnt/e/... or native /home/... or /root/...)
    return normalized

# ==================== SONGS API ====================

@songs_bp.route('/api/songs', methods=['GET'])
@login_required
def get_songs():
    """Get all songs for the scoped user, optionally filtered by repertoire"""
    repertoire_id = request.args.get('repertoire_id', type=int)
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)

    # Auto-bump targets for full bars that have aged past difficulty-based thresholds
    now = datetime.now()

    with get_db() as conn:
        cursor = conn.cursor()

        # Load difficulty thresholds from settings table (admin configurable)
        try:
            rows = cursor.execute(
                'SELECT key, value FROM settings WHERE key IN (?, ?, ?)',
                ('threshold_easy_days', 'threshold_normal_days', 'threshold_hard_days')
            ).fetchall()
            settings_map = {row['key']: int(row['value']) for row in rows}
        except Exception:
            settings_map = {}

        difficulty_threshold_days = {
            'easy': settings_map.get('threshold_easy_days', 90),
            'normal': settings_map.get('threshold_normal_days', 60),
            'hard': settings_map.get('threshold_hard_days', 30),
        }

        if repertoire_id:
            require_repertoire(cursor, repertoire_id, scope_user_id)
            songs = cursor.execute(
                '''SELECT * FROM songs WHERE user_id = ? AND repertoire_id = ? ORDER BY song_number ASC''',
                (scope_user_id, repertoire_id)
            ).fetchall()
        else:
            songs = cursor.execute(
                '''SELECT * FROM songs WHERE user_id = ? ORDER BY repertoire_id, song_number ASC''',
                (scope_user_id,)
            ).fetchall()

        songs_list = []
        for song in songs:
            song_dict = dict(song)

            practice_target = song_dict.get('practice_target') or 0
            practice_count = song_dict.get('practice_count') or 0
            last_practiced = song_dict.get('last_practiced')
            difficulty = song_dict.get('difficulty') or 'normal'
            threshold_days = difficulty_threshold_days.get(difficulty, difficulty_threshold_days['normal'])

            if practice_target > 0 and practice_count >= practice_target and last_practiced:
                try:
                    last_practiced_dt = datetime.fromisoformat(last_practiced)
                    days_since = (now - last_practiced_dt).days
                    if days_since >= threshold_days:
                        new_target = practice_target + 1
                        cursor.execute('UPDATE songs SET practice_target = ? WHERE id = ?', (new_target, song_dict['id']))
                        song_dict['practice_target'] = new_target
                except Exception:
                    pass

            skills = cursor.execute('''
                SELECT s.id, s.name, ss.is_mastered
                FROM skills s
                LEFT JOIN song_skills ss ON s.id = ss.skill_id AND ss.song_id = ?
                ORDER BY s.id
            ''', (song['id'],)).fetchall()

            song_dict['skills'] = [dict(skill) for skill in skills]

            total_skills = len([s for s in skills if s['is_mastered'] is not None])
            mastered_skills = len([s for s in skills if s['is_mastered'] == 1])
            song_dict['skills_progress'] = (mastered_skills / total_skills * 100) if total_skills > 0 else 0
            song_dict['practice_progress'] = (song_dict['practice_count'] / song_dict['practice_target'] * 100) if song_dict['practice_target'] > 0 else 0

            songs_list.append(song_dict)

        return jsonify(songs_list)

@songs_bp.route('/api/songs', methods=['POST'])
@login_required
def create_song():
    """Create a new song"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()
        repertoire = require_repertoire(cursor, data.get('repertoire_id'), g.current_user['id'])
        user_id = repertoire['user_id']

        # Determine initial practice target: number of skills to learn + 1
        initial_target = None
        try:
            if 'skill_ids' in data and isinstance(data['skill_ids'], list):
                initial_target = max(1, len(data['skill_ids']) + 1)
            else:
                row = cursor.execute(
                    'SELECT COUNT(*) AS c FROM repertoire_skills WHERE repertoire_id = ?',
                    (repertoire['id'],)
                ).fetchone()
                default_skill_count = row['c'] if row else 0
                initial_target = max(1, default_skill_count + 1)
        except Exception:
            initial_target = data.get('practice_target', 0) or 1

        cursor.execute('''
            INSERT INTO songs (title, artist, song_number, repertoire_id, user_id, priority, practice_target, date_added, release_date, notes, performance_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['title'],
            data['artist'],
            data.get('song_number', 1),
            repertoire['id'],
            user_id,
            data.get('priority', 'mid'),
            initial_target,
            datetime.now().isoformat(),
            data.get('release_date'),
            data.get('notes', ''),
            data.get('performance_hints', '')
        ))

        song_id = cursor.lastrowid

        if 'skill_ids' in data:
            for skill_id in data['skill_ids']:
                cursor.execute(
                    'INSERT INTO song_skills (song_id, skill_id, is_mastered) VALUES (?, ?, 0)',
                    (song_id, skill_id)
                )

        return jsonify({'id': song_id, 'message': 'Song created successfully'}), 201

@songs_bp.route('/api/songs/<int:song_id>/archive', methods=['POST'])
@login_required
def archive_song(song_id):
    """Move a song to the Archive repertoire"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify song ownership
        song = require_song(cursor, song_id, g.current_user['id'])
        
        # Find the Archive repertoire for this user
        archive = cursor.execute(
            'SELECT id FROM repertoires WHERE user_id = ? AND name = ?',
            (g.current_user['id'], 'Archive')
        ).fetchone()
        
        if not archive:
            return jsonify({'error': 'Archive repertoire not found'}), 404
        
        archive_id = archive['id']
        
        # Don't move if already in Archive
        if song['repertoire_id'] == archive_id:
            return jsonify({'message': 'Song is already in Archive'}), 200
        
        # Move the song to Archive
        cursor.execute(
            'UPDATE songs SET repertoire_id = ? WHERE id = ?',
            (archive_id, song_id)
        )
        
        return jsonify({'message': 'Song moved to Archive'}), 200

@songs_bp.route('/api/songs/<int:song_id>', methods=['PUT'])
@login_required
def update_song(song_id):
    """Update a song"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()

        song_row = require_song(cursor, song_id, g.current_user['id'])
        old_number = song_row['song_number']
        old_repertoire_id = song_row['repertoire_id']
        
        # Check if repertoire_id is being changed
        new_repertoire_id = data.get('repertoire_id', old_repertoire_id)
        if new_repertoire_id != old_repertoire_id:
            # Verify user owns the new repertoire
            new_rep = cursor.execute(
                'SELECT id FROM repertoires WHERE id = ? AND user_id = ?',
                (new_repertoire_id, g.current_user['id'])
            ).fetchone()
            if not new_rep:
                return jsonify({'error': 'Repertoire not found'}), 404
            
            # Get the max song_number in the target repertoire and append
            max_number_row = cursor.execute(
                'SELECT MAX(song_number) as max_num FROM songs WHERE repertoire_id = ?',
                (new_repertoire_id,)
            ).fetchone()
            new_number = (max_number_row['max_num'] or 0) + 1
            
            # Update the repertoire_id and song_number
            cursor.execute(
                'UPDATE songs SET repertoire_id = ?, song_number = ? WHERE id = ?',
                (new_repertoire_id, new_number, song_id)
            )
            
            # Return early - moving between repertoires is a complete operation
            return jsonify({'message': 'Song moved successfully'}), 200
        
        # Normal update within same repertoire
        repertoire_id = old_repertoire_id
        new_number = data.get('song_number', old_number)
        if not isinstance(new_number, int):
            try:
                new_number = int(new_number)
            except Exception:
                new_number = old_number

        if old_number != new_number:
            rows = cursor.execute(
                'SELECT id FROM songs WHERE repertoire_id = ? ORDER BY song_number ASC, id ASC',
                (repertoire_id,)
            ).fetchall()
            ids = [r['id'] for r in rows if r['id'] != song_id]
            max_count = len(ids) + 1
            new_number = max(1, min(new_number, max_count))
            ids.insert(new_number - 1, song_id)

            base = 100000
            for i, sid in enumerate(ids, start=1):
                cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (base + i, sid))
            for i, sid in enumerate(ids, start=1):
                cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, sid))

        target = data.get('practice_target', 0)
        target = max(1, target) if target else 1  # Enforce minimum of 1
        
        cursor.execute('''
            UPDATE songs
            SET title = ?, artist = ?, song_number = ?, priority = ?, 
                practice_target = ?, release_date = ?, notes = ?, performance_hints = ?
            WHERE id = ?
        ''', (
            data.get('title'),
            data.get('artist'),
            new_number,
            data.get('priority', 'mid'),
            target,
            data.get('release_date'),
            data.get('notes', ''),
            data.get('performance_hints', ''),
            song_id
        ))

        if 'skill_ids' in data:
            current_skills = cursor.execute(
                'SELECT skill_id, is_mastered FROM song_skills WHERE song_id = ?',
                (song_id,)
            ).fetchall()
            current_skills_dict = {row['skill_id']: row['is_mastered'] for row in current_skills}

            selected_ids = set(data['skill_ids'])
            
            # Calculate number of new skills being added
            new_skills_count = len(selected_ids - set(current_skills_dict.keys()))
            
            cursor.execute('DELETE FROM song_skills WHERE song_id = ? AND skill_id NOT IN ({})'.format(
                ','.join('?' * len(selected_ids)) if selected_ids else 'NULL'
            ), [song_id] + list(selected_ids) if selected_ids else [song_id])

            for skill_id in selected_ids:
                is_mastered = current_skills_dict.get(skill_id, 0)
                cursor.execute(
                    'INSERT OR REPLACE INTO song_skills (song_id, skill_id, is_mastered) VALUES (?, ?, ?)',
                    (song_id, skill_id, is_mastered)
                )
            
            # Increment practice_target by the number of new skills added
            if new_skills_count > 0:
                cursor.execute(
                    'UPDATE songs SET practice_target = practice_target + ? WHERE id = ?',
                    (new_skills_count, song_id)
                )

        return jsonify({'message': 'Song updated successfully'})

@songs_bp.route('/api/songs/<int:song_id>', methods=['DELETE'])
@login_required
def delete_song(song_id):
    """Delete a song"""
    with get_db() as conn:
        cursor = conn.cursor()
        require_song(cursor, song_id, g.current_user['id'])
        cursor.execute('DELETE FROM songs WHERE id = ?', (song_id,))

        return jsonify({'message': 'Song deleted successfully'})

# ==================== PRACTICE API ====================

@songs_bp.route('/api/songs/<int:song_id>/practice', methods=['POST'])
@login_required
def practice_song(song_id):
    """Mark a song as practiced (increment counter and update last practiced)"""
    with get_db() as conn:
        cursor = conn.cursor()
        require_song(cursor, song_id, g.current_user['id'])

        now = datetime.now().isoformat()

        # Increment practice count
        cursor.execute(
            'UPDATE songs SET practice_count = practice_count + 1, last_practiced = ? WHERE id = ?',
            (now, song_id)
        )

        # Fetch updated counts and skill status
        updated = cursor.execute(
            'SELECT practice_count, practice_target FROM songs WHERE id = ?',
            (song_id,)
        ).fetchone()

        # Count not mastered skills for this song
        not_mastered_count = cursor.execute('''
            SELECT COUNT(*) as count FROM song_skills
            WHERE song_id = ? AND is_mastered = 0
        ''', (song_id,)).fetchone()['count']

        # Ensure practice_target never falls behind practice_count
        # This prevents practice progress from exceeding 100%
        if updated:
            new_practice_count = updated['practice_count']
            current_target = updated['practice_target'] or 0
            
            # If count exceeds target, bump target to match count
            if new_practice_count > current_target:
                cursor.execute(
                    'UPDATE songs SET practice_target = ? WHERE id = ?',
                    (new_practice_count, song_id)
                )
            # If there are unmastered skills, ensure target is at least (count + unmastered)
            elif not_mastered_count > 0 and current_target <= (new_practice_count + not_mastered_count):
                new_target = current_target + 1
                cursor.execute(
                    'UPDATE songs SET practice_target = ? WHERE id = ?',
                    (new_target, song_id)
                )

        cursor.execute(
            'INSERT INTO practice_sessions (song_id, practiced_at) VALUES (?, ?)',
            (song_id, now)
        )

        # Log daily practice count for effort tracking
        practice_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO practice_date_log (song_id, user_id, practice_date, practice_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(song_id, user_id, practice_date) DO UPDATE SET practice_count = practice_count + 1
        ''', (song_id, g.current_user['id'], practice_date))

        return jsonify({'message': 'Practice recorded successfully'})

@songs_bp.route('/api/songs/<int:song_id>/target/increase', methods=['POST'])
@login_required
def increase_target(song_id):
    """Increase practice target by one to extend the goal incrementally."""
    with get_db() as conn:
        cursor = conn.cursor()
        require_song(cursor, song_id, g.current_user['id'])

        result = cursor.execute(
            'SELECT practice_count, practice_target FROM songs WHERE id = ?',
            (song_id,)
        ).fetchone()

        if not result:
            return jsonify({'error': 'Song not found'}), 404

        current_target = result['practice_target'] or 0
        new_target = current_target + 1

        cursor.execute('UPDATE songs SET practice_target = ? WHERE id = ?', (new_target, song_id))

        return jsonify({'message': 'Target increased', 'new_target': new_target})

@songs_bp.route('/api/songs/<int:song_id>/skills/<int:skill_id>/toggle', methods=['POST'])
@login_required
def toggle_skill(song_id, skill_id):
    """Toggle skill mastery status"""
    with get_db() as conn:
        cursor = conn.cursor()
        require_song(cursor, song_id, g.current_user['id'])

        result = cursor.execute(
            'SELECT is_mastered FROM song_skills WHERE song_id = ? AND skill_id = ?',
            (song_id, skill_id)
        ).fetchone()

        if result is None:
            return jsonify({'error': 'Skill not assigned to this song'}), 404

        new_status = 0 if result['is_mastered'] == 1 else 1

        cursor.execute(
            'UPDATE song_skills SET is_mastered = ? WHERE song_id = ? AND skill_id = ?',
            (new_status, song_id, skill_id)
        )

        # If skill has just been mastered, reduce practice_target by 1,
        # but never below current practice_count or minimum of 1
        if new_status == 1:
            row = cursor.execute(
                'SELECT practice_count, practice_target FROM songs WHERE id = ?',
                (song_id,)
            ).fetchone()
            if row is not None:
                pc = row['practice_count'] or 0
                pt = row['practice_target'] or 0
                new_target = max(1, max(pc, pt - 1))  # Enforce minimum of 1
                if new_target != pt:
                    cursor.execute(
                        'UPDATE songs SET practice_target = ? WHERE id = ?',
                        (new_target, song_id)
                    )
        # If skill was unmastered, increase practice_target by 1.
        elif new_status == 0:
            row = cursor.execute(
                'SELECT practice_count, practice_target FROM songs WHERE id = ?',
                (song_id,)
            ).fetchone()
            if row is not None:
                pc = row['practice_count'] or 0
                pt = row['practice_target'] or 0
                new_target = max(1, pt + 1)
                # Keep target not below actual progress just in case
                new_target = max(new_target, pc)
                if new_target != pt:
                    cursor.execute(
                        'UPDATE songs SET practice_target = ? WHERE id = ?',
                        (new_target, song_id)
                    )

        return jsonify({'is_mastered': new_status})

@songs_bp.route('/api/songs/<int:song_id>/priority/toggle', methods=['POST'])
@login_required
def toggle_priority(song_id):
    """Toggle priority: mid -> high -> low -> mid"""
    with get_db() as conn:
        cursor = conn.cursor()
        require_song(cursor, song_id, g.current_user['id'])

        result = cursor.execute('SELECT priority FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not result:
            return jsonify({'error': 'Song not found'}), 404

        priority_cycle = {'mid': 'high', 'high': 'low', 'low': 'mid'}
        new_priority = priority_cycle.get(result['priority'], 'mid')

        cursor.execute('UPDATE songs SET priority = ? WHERE id = ?', (new_priority, song_id))

        return jsonify({'priority': new_priority})

@songs_bp.route('/api/songs/<int:song_id>/difficulty/toggle', methods=['POST'])
@login_required
def toggle_difficulty(song_id):
    """Toggle difficulty: normal -> easy -> hard -> normal"""
    with get_db() as conn:
        cursor = conn.cursor()
        require_song(cursor, song_id, g.current_user['id'])

        result = cursor.execute('SELECT difficulty FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not result:
            return jsonify({'error': 'Song not found'}), 404

        difficulty_cycle = {'normal': 'easy', 'easy': 'hard', 'hard': 'normal'}
        new_difficulty = difficulty_cycle.get(result['difficulty'], 'normal')

        cursor.execute('UPDATE songs SET difficulty = ? WHERE id = ?', (new_difficulty, song_id))

        return jsonify({'difficulty': new_difficulty})

# ==================== ORDERING API ====================

@songs_bp.route('/api/songs/reorder', methods=['POST'])
@login_required
def reorder_songs():
    """Reorder songs by array of song IDs in desired order; song_number becomes 1..N within repertoire."""
    data = request.json or {}
    ordered_ids = data.get('ordered_ids', [])
    repertoire_id = data.get('repertoire_id')

    if not isinstance(ordered_ids, list) or not all(isinstance(x, int) for x in ordered_ids):
        return jsonify({'error': 'ordered_ids must be an array of integers'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        scope_user_id = g.current_user['id']

        if repertoire_id:
            require_repertoire(cursor, repertoire_id, scope_user_id)
            existing = cursor.execute(
                'SELECT id FROM songs WHERE repertoire_id = ? AND user_id = ? ORDER BY song_number ASC, id ASC',
                (repertoire_id, scope_user_id)
            ).fetchall()
        else:
            existing = cursor.execute(
                'SELECT id FROM songs WHERE user_id = ? ORDER BY song_number ASC, id ASC',
                (scope_user_id,)
            ).fetchall()
        
        existing_ids = [row['id'] for row in existing]
        if not existing_ids:
            return jsonify({'error': 'No songs available to reorder'}), 400

        seen = set(ordered_ids)
        remaining = [sid for sid in existing_ids if sid not in seen]
        full_order = ordered_ids + remaining

        base = 100000
        for i, sid in enumerate(full_order, start=1):
            if sid not in existing_ids:
                return jsonify({'error': 'Invalid song id in ordered_ids'}), 400
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (base + i, sid))
        for i, sid in enumerate(full_order, start=1):
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, sid))

        return jsonify({'message': 'Order updated', 'count': len(full_order)})

# ==================== MEDIA SERVING ====================

@songs_bp.route('/media/<int:song_id>')
@login_required
def media(song_id):
    """Serve the linked audio file for a song, if present."""
    with get_db() as conn:
        cur = conn.cursor()
        song = require_song(cur, song_id, g.current_user['id'])
        path = song['audio_path']
        if not path:
            abort(404)
        wsl_path = windows_path_to_wsl(path)
        if not os.path.isfile(wsl_path):
            abort(404)
        with open(wsl_path, 'rb') as f:
            data = f.read()
        response = Response(data, mimetype='audio/mpeg')
        response.headers['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
        return response

@songs_bp.route('/chart/<int:song_id>')
@login_required
def chart(song_id):
    """Serve the linked chart file for a song, if present."""
    with get_db() as conn:
        cur = conn.cursor()
        song = require_song(cur, song_id, g.current_user['id'])
        path = song['chart_path']
        if not path:
            abort(404)
        wsl_path = windows_path_to_wsl(path)
        if not os.path.isfile(wsl_path):
            abort(404)
        return send_file(wsl_path, as_attachment=False, download_name=os.path.basename(path))

@songs_bp.route('/api/songs/<int:song_id>/audio', methods=['POST', 'DELETE'])
@login_required
def manage_audio(song_id):
    """Attach or remove audio for a song.
    POST with JSON field 'file_path' to link to existing file.
    DELETE to unlink existing audio_path.
    """
    with get_db() as conn:
        cur = conn.cursor()
        exist = require_song(cur, song_id, g.current_user['id'])

        if request.method == 'DELETE':
            cur.execute('UPDATE songs SET audio_path = NULL, duration = NULL WHERE id = ?', (song_id,))
            return jsonify({'message': 'Audio link removed'})

        # POST - link to file path
        data = request.json
        if not data or 'file_path' not in data:
            return jsonify({'error': 'No file_path provided'}), 400
        
        file_path = data['file_path']
        
        # Validate file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ALLOWED_EXTS:
            return jsonify({'error': f'Unsupported file type {ext}'}), 400
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found at specified path'}), 404
        
        # Extract duration from MP3 if possible
        duration = extract_mp3_duration(file_path) if ext in {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'} else None
        
        cur.execute('UPDATE songs SET audio_path = ?, duration = ? WHERE id = ?', (file_path, duration, song_id))
        response = {'message': 'Audio linked', 'audio_path': file_path}
        if duration:
            response['duration'] = duration
        return jsonify(response)

@songs_bp.route('/api/songs/<int:song_id>/chart', methods=['POST', 'DELETE'])
@login_required
def manage_chart(song_id):
    """Attach or remove chart for a song.
    POST with JSON field 'file_path' to copy file to charts/ folder.
    DELETE to unlink existing chart_path.
    """
    with get_db() as conn:
        cur = conn.cursor()
        exist = require_song(cur, song_id, g.current_user['id'])

        if request.method == 'DELETE':
            cur.execute('UPDATE songs SET chart_path = NULL WHERE id = ?', (song_id,))
            return jsonify({'message': 'Chart link removed'})

        # POST - copy file to charts folder
        data = request.json
        if not data or 'file_path' not in data:
            return jsonify({'error': 'No file_path provided'}), 400
        
        file_path = data['file_path']
        
        # Validate file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ALLOWED_CHART_EXTS:
            return jsonify({'error': f'Unsupported file type {ext}'}), 400
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found at specified path'}), 404
        
        # Copy file to charts folder
        charts_folder = os.path.join(os.getcwd(), 'charts')
        os.makedirs(charts_folder, exist_ok=True)
        
        # Get song title for filename
        song = cur.execute('SELECT title FROM songs WHERE id = ?', (song_id,)).fetchone()
        safe_title = ''.join(c for c in song['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
        dest_filename = f'{song_id}_{safe_title}{ext}'
        dest_path = os.path.join(charts_folder, dest_filename)
        
        # Copy the file
        shutil.copy2(file_path, dest_path)
        
        # Update database with local path
        cur.execute('UPDATE songs SET chart_path = ? WHERE id = ?', (dest_path, song_id))
        return jsonify({'message': 'Chart uploaded', 'chart_path': dest_path})
