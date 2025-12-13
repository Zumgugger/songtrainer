from flask import Flask, render_template, request, jsonify, send_file, abort, Response
from werkzeug.utils import secure_filename
from database import get_db, init_db, ensure_indexes_and_normalize, ensure_audio_path_column, ensure_chart_path_column, ensure_repertoire_id_column, ensure_release_date_column, ensure_repertoire_sort_order_column, ensure_repertoire_folder_columns, ensure_sync_history_table
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
import sqlite3
import os
import glob
import urllib.request
import urllib.parse
import json
import time
import re

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
    ensure_repertoire_folder_columns()
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
        ensure_repertoire_folder_columns()
    except Exception:
        pass
    try:
        ensure_sync_history_table()
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
            INSERT INTO songs (title, artist, song_number, repertoire_id, priority, practice_target, date_added, release_date, notes, performance_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['title'],
            data['artist'],
            data.get('song_number', 1),
            data['repertoire_id'],
            data.get('priority', 'mid'),
            data.get('practice_target', 0),
            datetime.now().isoformat(),
            data.get('release_date'),
            data.get('notes', ''),
            data.get('performance_hints', '')
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
            # Build canonical new order list using two-phase update to avoid UNIQUE conflicts
            rows = cursor.execute(
                'SELECT id FROM songs WHERE repertoire_id = ? ORDER BY song_number ASC, id ASC',
                (repertoire_id,)
            ).fetchall()
            ids = [r['id'] for r in rows]
            # Remove the target song id
            ids = [sid for sid in ids if sid != song_id]
            # Clamp to bounds 1..N
            max_count = len(ids) + 1
            if new_number < 1:
                new_number = 1
            if new_number > max_count:
                new_number = max_count
            # Insert target at desired position (new_number is 1-based)
            ids.insert(new_number - 1, song_id)

            # Phase 1: assign high temporary numbers to avoid UNIQUE collisions
            base = 100000
            for i, sid in enumerate(ids, start=1):
                cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (base + i, sid))
            # Phase 2: normalize to 1..N
            for i, sid in enumerate(ids, start=1):
                cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, sid))
        
        # Update the song itself
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
            data.get('practice_target', 0),
            data.get('release_date'),
            data.get('notes', ''),
            data.get('performance_hints', ''),
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
    """Attach or remove audio for a song.
    POST with JSON field 'file_path' to link to existing file.
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
        
        cur.execute('UPDATE songs SET audio_path = ? WHERE id = ?', (file_path, song_id))
        return jsonify({'message': 'Audio linked', 'audio_path': file_path})

@app.route('/api/songs/<int:song_id>/chart', methods=['POST', 'DELETE'])
def manage_chart(song_id):
    """Attach or remove chart for a song.
    POST with JSON field 'file_path' to link to existing file.
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

        # POST - link to file path
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
        
        cur.execute('UPDATE songs SET chart_path = ? WHERE id = ?', (file_path, song_id))
        return jsonify({'message': 'Chart linked', 'chart_path': file_path})

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
    """Update a repertoire's name, folder paths, and default skills"""
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
        
        # Update folder paths
        if 'songlist_folder' in data:
            cursor.execute(
                'UPDATE repertoires SET songlist_folder = ? WHERE id = ?',
                (data['songlist_folder'] or None, repertoire_id)
            )
        if 'mp3_folder' in data:
            cursor.execute(
                'UPDATE repertoires SET mp3_folder = ? WHERE id = ?',
                (data['mp3_folder'] or None, repertoire_id)
            )
        if 'sheet_folder' in data:
            cursor.execute(
                'UPDATE repertoires SET sheet_folder = ? WHERE id = ?',
                (data['sheet_folder'] or None, repertoire_id)
            )
        
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

@app.route('/api/repertoires/<int:repertoire_id>/sync', methods=['POST'])
def sync_repertoire_folders(repertoire_id):
    """Scan MP3 folder, create songs from filenames, then link MP3s and sheets"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get repertoire with folder paths
        rep = cursor.execute(
            'SELECT * FROM repertoires WHERE id = ?',
            (repertoire_id,)
        ).fetchone()
        
        if not rep:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Delete previous sync history for this repertoire
        cursor.execute('DELETE FROM sync_history WHERE repertoire_id = ?', (repertoire_id,))
        
        sync_timestamp = datetime.now().isoformat()
        
        stats = {
            'songs_added': 0,
            'mp3_linked': 0,
            'sheets_linked': 0,
            'errors': [],
            'debug': {
                'songs_in_repertoire': 0,
                'mp3_files_found': 0,
                'sheet_files_found': 0,
                'songlist_files_found': 0,
                'songlist_folder_path': rep['songlist_folder'],
                'mp3_folder_path': rep['mp3_folder'],
                'sheet_folder_path': rep['sheet_folder']
            }
        }
        
        # Count existing songs
        existing_songs_count = cursor.execute(
            'SELECT COUNT(*) as cnt FROM songs WHERE repertoire_id = ?',
            (repertoire_id,)
        ).fetchone()['cnt']
        stats['debug']['songs_in_repertoire'] = existing_songs_count
        
        # Step 1: Scan MP3 folder and create songs from MP3 filenames
        if rep['mp3_folder'] and os.path.isdir(rep['mp3_folder']):
            try:
                # Get existing song titles and linked audio paths
                existing_titles = {
                    row['title'].lower() 
                    for row in cursor.execute(
                        'SELECT title FROM songs WHERE repertoire_id = ?',
                        (repertoire_id,)
                    ).fetchall()
                }
                linked_audio_paths = {
                    row['audio_path']
                    for row in cursor.execute(
                        'SELECT audio_path FROM songs WHERE repertoire_id = ? AND audio_path IS NOT NULL',
                        (repertoire_id,)
                    ).fetchall()
                }
                
                # Find all MP3 files
                mp3_files = []
                for ext in ['.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg']:
                    mp3_files.extend(glob.glob(os.path.join(rep['mp3_folder'], f'*{ext}')))
                
                stats['debug']['mp3_files_found'] = len(mp3_files)
                
                # Create songs from MP3 filenames
                for mp3_path in mp3_files:
                    # Skip if this MP3 is already linked to a song
                    if mp3_path in linked_audio_paths:
                        continue
                    
                    filename = os.path.basename(mp3_path)
                    name_no_ext = os.path.splitext(filename)[0]
                    
                    # Parse filename format: "YYYY - Title - Artist" or "Title - Artist" or "Title"
                    release_year = None
                    artist = 'Unknown'
                    title = name_no_ext.strip()
                    
                    if ' - ' in name_no_ext:
                        parts = name_no_ext.split(' - ')
                        
                        # Check if first part is a 4-digit year
                        if len(parts) >= 2 and parts[0].strip().isdigit() and len(parts[0].strip()) == 4:
                            release_year = parts[0].strip()
                            # Format: "YYYY - Title - Artist" or "YYYY - Title"
                            if len(parts) >= 3:
                                title = parts[1].strip()
                                artist = parts[2].strip()
                            else:
                                title = parts[1].strip()
                                artist = 'Unknown'
                        else:
                            # Format: "Title - Artist" or just "Title"
                            if len(parts) >= 2:
                                title = parts[0].strip()
                                artist = parts[1].strip()
                            else:
                                title = parts[0].strip()
                                artist = 'Unknown'
                    
                    # Check if song already exists by title
                    if title.lower() not in existing_titles:
                        # Get next song number
                        max_num = cursor.execute(
                            'SELECT COALESCE(MAX(song_number), 0) as max FROM songs WHERE repertoire_id = ?',
                            (repertoire_id,)
                        ).fetchone()['max']
                        
                        # Create new song with MP3 linked
                        cursor.execute('''
                            INSERT INTO songs (
                                title, artist, song_number, repertoire_id,
                                priority, practice_count, practice_target, date_added, audio_path, release_date
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            title, artist, max_num + 1, repertoire_id,
                            'mid', 0, 5, datetime.now().isoformat(), mp3_path, release_year
                        ))
                        
                        song_id = cursor.lastrowid
                        
                        # Record song creation in sync history
                        cursor.execute('''
                            INSERT INTO sync_history (
                                repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (repertoire_id, sync_timestamp, 'song_created', song_id, None, None, None))
                        
                        # Assign default skills
                        default_skills = cursor.execute(
                            'SELECT skill_id FROM repertoire_skills WHERE repertoire_id = ?',
                            (repertoire_id,)
                        ).fetchall()
                        
                        for skill in default_skills:
                            cursor.execute(
                                'INSERT INTO song_skills (song_id, skill_id, is_mastered) VALUES (?, ?, ?)',
                                (song_id, skill['skill_id'], 0)
                            )
                        
                        stats['songs_added'] += 1
                        stats['mp3_linked'] += 1
                        existing_titles.add(title.lower())
            except Exception as e:
                stats['errors'].append(f'MP3 scan error: {str(e)}')
        
        # Step 2: Link MP3s to existing songs that don't have audio yet
        if rep['mp3_folder'] and os.path.isdir(rep['mp3_folder']):
            try:
                # Get songs without audio
                songs = cursor.execute(
                    'SELECT id, title, artist FROM songs WHERE repertoire_id = ? AND audio_path IS NULL',
                    (repertoire_id,)
                ).fetchall()
                
                if songs:
                    # Find all MP3 files
                    mp3_files = []
                    for ext in ['.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg']:
                        mp3_files.extend(glob.glob(os.path.join(rep['mp3_folder'], f'*{ext}')))
                    
                    for song in songs:
                        song_title = song['title'].lower()
                        song_artist = song['artist'].lower()
                        
                        for mp3_path in mp3_files:
                            filename = os.path.basename(mp3_path).lower()
                            name_no_ext = os.path.splitext(filename)[0]
                            
                            # Match if filename contains title or matches "artist - title" pattern
                            if (song_title in name_no_ext or 
                                name_no_ext in song_title or
                                f'{song_artist} - {song_title}' in name_no_ext):
                                
                                # Record old value before updating
                                cursor.execute('''
                                    INSERT INTO sync_history (
                                        repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (repertoire_id, sync_timestamp, 'field_updated', song['id'], 'audio_path', None, mp3_path))
                                
                                cursor.execute(
                                    'UPDATE songs SET audio_path = ? WHERE id = ?',
                                    (mp3_path, song['id'])
                                )
                                stats['mp3_linked'] += 1
                                break
            except Exception as e:
                stats['errors'].append(f'MP3 linking error: {str(e)}')
        
        # Step 3: Link sheets to songs
        if rep['sheet_folder'] and os.path.isdir(rep['sheet_folder']):
            try:
                # Get all songs without charts
                songs = cursor.execute(
                    'SELECT id, title, artist FROM songs WHERE repertoire_id = ? AND chart_path IS NULL',
                    (repertoire_id,)
                ).fetchall()
                
                sheet_files = []
                for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.doc', '.docx']:
                    sheet_files.extend(glob.glob(os.path.join(rep['sheet_folder'], f'*{ext}')))
                
                stats['debug']['sheet_files_found'] = len(sheet_files)
                
                for song in songs:
                    song_title = song['title'].lower()
                    song_artist = song['artist'].lower()
                    
                    # Find all matching sheets for this song
                    matching_sheets = []
                    for sheet_path in sheet_files:
                        filename = os.path.basename(sheet_path).lower()
                        name_no_ext = os.path.splitext(filename)[0]
                        
                        if (song_title in name_no_ext or 
                            name_no_ext in song_title or
                            f'{song_artist} - {song_title}' in name_no_ext):
                            matching_sheets.append((sheet_path, filename))
                    
                    # Prioritize: "chords" first, then "chart", then any match
                    best_sheet = None
                    if matching_sheets:
                        # First priority: files with "chords" in name
                        chords_sheets = [s for s in matching_sheets if 'chords' in s[1]]
                        if chords_sheets:
                            best_sheet = chords_sheets[0][0]
                        else:
                            # Second priority: files with "chart" in name
                            chart_sheets = [s for s in matching_sheets if 'chart' in s[1]]
                            if chart_sheets:
                                best_sheet = chart_sheets[0][0]
                            else:
                                # Use first match
                                best_sheet = matching_sheets[0][0]
                    
                    if best_sheet:
                        # Record old value before updating
                        cursor.execute('''
                            INSERT INTO sync_history (
                                repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (repertoire_id, sync_timestamp, 'field_updated', song['id'], 'chart_path', None, best_sheet))
                        
                        cursor.execute(
                            'UPDATE songs SET chart_path = ? WHERE id = ?',
                            (best_sheet, song['id'])
                        )
                        stats['sheets_linked'] += 1
            except Exception as e:
                stats['errors'].append(f'Sheet sync error: {str(e)}')
        
        return jsonify(stats)

@app.route('/api/repertoires/<int:repertoire_id>/undo-sync', methods=['POST'])
def undo_sync_repertoire(repertoire_id):
    """Undo the last sync operation for a repertoire"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get repertoire
        rep = cursor.execute(
            'SELECT * FROM repertoires WHERE id = ?',
            (repertoire_id,)
        ).fetchone()
        
        if not rep:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Get sync history for this repertoire
        history = cursor.execute(
            'SELECT * FROM sync_history WHERE repertoire_id = ? ORDER BY id',
            (repertoire_id,)
        ).fetchall()
        
        if not history:
            return jsonify({'error': 'No sync history to undo'}), 400
        
        stats = {
            'songs_deleted': 0,
            'audio_unlinked': 0,
            'charts_unlinked': 0
        }
        
        # Reverse the operations
        for record in history:
            if record['operation_type'] == 'song_created':
                # Delete the song that was created
                cursor.execute('DELETE FROM songs WHERE id = ?', (record['song_id'],))
                stats['songs_deleted'] += 1
            
            elif record['operation_type'] == 'field_updated':
                # Restore the old value
                if record['field_name'] == 'audio_path':
                    cursor.execute(
                        'UPDATE songs SET audio_path = ? WHERE id = ?',
                        (record['old_value'], record['song_id'])
                    )
                    stats['audio_unlinked'] += 1
                
                elif record['field_name'] == 'chart_path':
                    cursor.execute(
                        'UPDATE songs SET chart_path = ? WHERE id = ?',
                        (record['old_value'], record['song_id'])
                    )
                    stats['charts_unlinked'] += 1
        
        # Clear the sync history after undoing
        cursor.execute('DELETE FROM sync_history WHERE repertoire_id = ?', (repertoire_id,))
        
        return jsonify(stats)

@app.route('/api/songs/lookup', methods=['POST'])
def lookup_song_metadata():
    """Look up song metadata (artist, release date) from MusicBrainz"""
    data = request.json
    title = data.get('title', '').strip()
    
    if not title:
        return jsonify({'error': 'Title required'}), 400
    
    try:
        # Query MusicBrainz API
        query = urllib.parse.quote(title)
        url = f'https://musicbrainz.org/ws/2/recording/?query=recording:{query}&fmt=json&limit=5'
        
        headers = {
            'User-Agent': 'SongTrainer/1.0 (https://github.com/yourapp)'
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
        
        recordings = result.get('recordings', [])
        if not recordings:
            return jsonify({'found': False})
        
        # Get best match (first result)
        best = recordings[0]
        
        metadata = {
            'found': True,
            'title': best.get('title', title),
            'artist': 'Unknown',
            'release_date': None
        }
        
        # Extract artist
        if 'artist-credit' in best and best['artist-credit']:
            metadata['artist'] = best['artist-credit'][0].get('name', 'Unknown')
        
        # Extract release date from first release
        if 'releases' in best and best['releases']:
            first_release = best['releases'][0]
            if 'date' in first_release:
                metadata['release_date'] = first_release['date']
        
        # Rate limiting (MusicBrainz requires 1 request per second)
        time.sleep(1)
        
        return jsonify(metadata)
        
    except Exception as e:
        return jsonify({'error': str(e), 'found': False}), 500

@app.route('/api/repertoires/<int:repertoire_id>/setlist-pdf', methods=['POST'])
def generate_setlist_pdf(repertoire_id):
    """Generate a PDF setlist for a repertoire"""
    data = request.json
    max_song_number = data.get('max_song_number', None)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get repertoire info
        repertoire = cursor.execute(
            'SELECT name FROM repertoires WHERE id = ?',
            (repertoire_id,)
        ).fetchone()
        
        if not repertoire:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Get songs up to max_song_number
        if max_song_number:
            songs = cursor.execute('''
                SELECT song_number, title, performance_hints
                FROM songs 
                WHERE repertoire_id = ? AND song_number <= ?
                ORDER BY song_number ASC
            ''', (repertoire_id, max_song_number)).fetchall()
        else:
            songs = cursor.execute('''
                SELECT song_number, title, performance_hints
                FROM songs 
                WHERE repertoire_id = ?
                ORDER BY song_number ASC
            ''', (repertoire_id,)).fetchall()
        
        if not songs:
            return jsonify({'error': 'No songs found'}), 404
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
        
        # Container for PDF elements
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Add title
        elements.append(Paragraph(repertoire['name'], title_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Create setlist table data
        table_data = []
        for song in songs:
            song_text = song['title']
            
            # Format performance hints
            if song['performance_hints']:
                # Convert **text** to <b>text</b> for PDF
                hints = song['performance_hints']
                hints = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', hints)
                song_text += f' <font color="#7f8c8d">({hints})</font>'
            
            table_data.append([
                str(song['song_number']),
                Paragraph(song_text, styles['Normal'])
            ])
        
        # Create table
        table = Table(table_data, colWidths=[2*cm, 16*cm])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        filename = f"{repertoire['name']}_setlist.pdf"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(debug=True, host='0.0.0.0', port=port)
