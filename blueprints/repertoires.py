"""Repertoire management blueprint."""

from flask import Blueprint, request, jsonify, g, send_file, abort
from database import get_db
from utils.decorators import login_required, admin_required
from utils.permissions import resolve_scope_user_id, require_repertoire
from utils.helpers import calculate_time_practiced_since, extract_mp3_duration
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
import os
import glob
import json
import re
import urllib.request
import urllib.parse
import time
import shutil

repertoires_bp = Blueprint('repertoires', __name__)


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


@repertoires_bp.route('/api/repertoires', methods=['GET'])
@login_required
def get_repertoires():
    """Get all repertoires with their default skills for the scoped user"""
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)

    with get_db() as conn:
        cursor = conn.cursor()

        repertoires = cursor.execute(
            'SELECT * FROM repertoires WHERE user_id = ? ORDER BY COALESCE(sort_order, id), id',
            (scope_user_id,)
        ).fetchall()
        repertoires_list = []

        for rep in repertoires:
            rep_dict = dict(rep)

            skills = cursor.execute('''
                SELECT s.id, s.name
                FROM skills s
                INNER JOIN repertoire_skills rs ON s.id = rs.skill_id
                WHERE rs.repertoire_id = ?
                ORDER BY s.id
            ''', (rep['id'],)).fetchall()

            rep_dict['default_skills'] = [dict(skill) for skill in skills]

            song_count = cursor.execute(
                'SELECT COUNT(*) as count FROM songs WHERE repertoire_id = ? AND user_id = ?',
                (rep['id'], scope_user_id)
            ).fetchone()
            rep_dict['song_count'] = song_count['count']
            rep_dict['notes'] = rep['notes'] or ''

            repertoires_list.append(rep_dict)

        return jsonify(repertoires_list)


@repertoires_bp.route('/api/repertoires/<int:repertoire_id>/time-practiced', methods=['GET'])
@login_required
def get_repertoire_time_practiced(repertoire_id):
    """Get time practiced for a repertoire since a per-user start date.
    Current user: start today. Other users: start from their first practice in this repertoire (or today if none)."""
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)
    today = datetime.now().date()
    today_str = today.strftime('%Y-%m-%d')

    with get_db() as conn:
        cursor = conn.cursor()
        # Find earliest practice date for this user in this repertoire
        earliest = cursor.execute(
            '''
            SELECT MIN(pl.practice_date) AS first_date
            FROM practice_date_log pl
            JOIN songs s ON s.id = pl.song_id
            WHERE pl.user_id = ? AND s.repertoire_id = ?
            ''',
            (scope_user_id, repertoire_id)
        ).fetchone()
        first_date = earliest['first_date'] if earliest else None

    # For the current user, always start today (requested behavior)
    if getattr(g, 'current_user', None) and g.current_user['id'] == scope_user_id:
        start_date = today_str
    else:
        start_date = first_date or today_str

    time_data = calculate_time_practiced_since(get_db, start_date, repertoire_id, scope_user_id)
    
    # Format date as DD-MM-YYYY (European format)
    try:
        date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        formatted_date = date_obj.strftime('%d-%m-%Y')
    except:
        formatted_date = start_date
    
    time_data['start_date'] = formatted_date
    return jsonify(time_data)


@repertoires_bp.route('/api/repertoires', methods=['POST'])
@login_required
def create_repertoire():
    """Create a new repertoire"""
    import sqlite3
    data = request.json or {}
    target_user_id = resolve_scope_user_id(get_db, data.get('user_id', None))

    with get_db() as conn:
        cursor = conn.cursor()

        try:
            sort_max = cursor.execute(
                'SELECT COALESCE(MAX(sort_order), 0) as max_order FROM repertoires WHERE user_id = ?',
                (target_user_id,)
            ).fetchone()['max_order']

            cursor.execute(
                'INSERT INTO repertoires (name, date_created, user_id, sort_order) VALUES (?, ?, ?, ?)',
                (data['name'], datetime.now().isoformat(), target_user_id, sort_max + 1)
            )
            repertoire_id = cursor.lastrowid

            if 'skill_ids' in data:
                for skill_id in data['skill_ids']:
                    cursor.execute(
                        'INSERT INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                        (repertoire_id, skill_id)
                    )

            return jsonify({'id': repertoire_id, 'message': 'Repertoire created successfully'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Repertoire name already exists'}), 400


@repertoires_bp.route('/api/repertoires/<int:repertoire_id>', methods=['PUT'])
@login_required
def update_repertoire(repertoire_id):
    """Update a repertoire's name, folder paths, and default skills"""
    import sqlite3
    data = request.json or {}
    with get_db() as conn:
        cursor = conn.cursor()
        rep = require_repertoire(cursor, repertoire_id, g.current_user['id'])

        if 'name' in data:
            try:
                cursor.execute(
                    'UPDATE repertoires SET name = ? WHERE id = ?',
                    (data['name'], repertoire_id)
                )
            except sqlite3.IntegrityError:
                return jsonify({'error': 'Repertoire name already exists'}), 400

        if 'notes' in data:
            cursor.execute(
                'UPDATE repertoires SET notes = ? WHERE id = ?',
                (data['notes'] or None, repertoire_id)
            )

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

        if 'skill_ids' in data:
            cursor.execute('DELETE FROM repertoire_skills WHERE repertoire_id = ?', (repertoire_id,))
            for skill_id in data['skill_ids']:
                cursor.execute(
                    'INSERT INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                    (repertoire_id, skill_id)
                )

        return jsonify({'message': 'Repertoire updated successfully'})


@repertoires_bp.route('/api/repertoires/<int:repertoire_id>', methods=['DELETE'])
@login_required
def delete_repertoire(repertoire_id):
    """Delete a repertoire and cascade delete all songs in it"""
    with get_db() as conn:
        cursor = conn.cursor()
        require_repertoire(cursor, repertoire_id, g.current_user['id'])

        song_count = cursor.execute(
            'SELECT COUNT(*) as count FROM songs WHERE repertoire_id = ?',
            (repertoire_id,)
        ).fetchone()

        cursor.execute('DELETE FROM songs WHERE repertoire_id = ?', (repertoire_id,))
        cursor.execute('DELETE FROM repertoires WHERE id = ?', (repertoire_id,))

        return jsonify({
            'message': 'Repertoire deleted successfully',
            'songs_deleted': song_count['count']
        })


@repertoires_bp.route('/api/repertoires/<int:repertoire_id>/share', methods=['POST'])
@login_required
def share_repertoire(repertoire_id):
    """Share/copy a repertoire to another user"""
    data = request.json or {}
    target_user_id = data.get('target_user_id')
    
    if not target_user_id:
        return jsonify({'error': 'target_user_id is required'}), 400
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify source repertoire ownership
        source_rep = require_repertoire(cursor, repertoire_id, g.current_user['id'])
        
        # Verify target user exists
        target_user = cursor.execute(
            'SELECT id, email FROM users WHERE id = ?',
            (target_user_id,)
        ).fetchone()
        if not target_user:
            return jsonify({'error': 'Target user not found'}), 404
        
        # Create new repertoire for target user
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO repertoires (
                name, date_created, user_id, sort_order,
                songlist_folder, mp3_folder, sheet_folder, notes,
                copied_from_user_id, copied_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            source_rep['name'],
            now,
            target_user_id,
            0,  # Place at top
            source_rep['songlist_folder'],
            source_rep['mp3_folder'],
            source_rep['sheet_folder'],
            source_rep['notes'],
            g.current_user['id'],
            now
        ))
        new_rep_id = cursor.lastrowid
        
        # Copy songs (excluding performance_hints, practice data)
        songs = cursor.execute(
            'SELECT * FROM songs WHERE repertoire_id = ? AND user_id = ?',
            (repertoire_id, g.current_user['id'])
        ).fetchall()
        
        song_id_map = {}  # Map old song ID to new song ID
        for song in songs:
            cursor.execute('''
                INSERT INTO songs (
                    title, artist, repertoire_id, user_id, song_number,
                    audio_path, chart_path, priority, practice_target,
                    release_date, notes, difficulty
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                song['title'],
                song['artist'],
                new_rep_id,
                target_user_id,
                song['song_number'],
                song['audio_path'],
                song['chart_path'],
                song['priority'],
                song['practice_target'] or 1,
                song['release_date'],
                song['notes'],
                song['difficulty']
            ))
            new_song_id = cursor.lastrowid
            song_id_map[song['id']] = new_song_id
        
        # Copy song skills (individual song skills, not repertoire skills)
        for old_song_id, new_song_id in song_id_map.items():
            song_skills = cursor.execute(
                'SELECT skill_id FROM song_skills WHERE song_id = ?',
                (old_song_id,)
            ).fetchall()
            
            for sk in song_skills:
                cursor.execute(
                    'INSERT INTO song_skills (song_id, skill_id, is_mastered) VALUES (?, ?, 0)',
                    (new_song_id, sk['skill_id'])
                )
        
        return jsonify({
            'message': f'Repertoire shared with {target_user["email"]}',
            'new_repertoire_id': new_rep_id,
            'songs_copied': len(songs)
        }), 201


@repertoires_bp.route('/api/repertoires/reorder', methods=['POST'])
@login_required
def reorder_repertoires():
    """Persist a new ordering of repertoires given an array of repertoire IDs."""
    data = request.json or {}
    order = data.get('order')
    if not isinstance(order, list) or not all(isinstance(i, int) for i in order):
        return jsonify({'error': 'Invalid order payload'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        scope_user_id = g.current_user['id']
        existing_ids = {row['id'] for row in cursor.execute('SELECT id FROM repertoires WHERE user_id = ?', (scope_user_id,)).fetchall()}
        if set(order) - existing_ids:
            return jsonify({'error': 'Unknown repertoire id(s) in order'}), 400

        for position, rep_id in enumerate(order, start=1):
            cursor.execute('UPDATE repertoires SET sort_order = ? WHERE id = ?', (position, rep_id))

    return jsonify({'message': 'Repertoires reordered successfully'})


@repertoires_bp.route('/api/repertoires/<int:repertoire_id>/sync', methods=['POST'])
@login_required
def sync_repertoire_folders(repertoire_id):
    """Scan MP3 folder, create songs from filenames, then link MP3s and sheets"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        rep = require_repertoire(cursor, repertoire_id, g.current_user['id'])
        
        # Delete previous sync history for this repertoire
        cursor.execute('DELETE FROM sync_history WHERE repertoire_id = ?', (repertoire_id,))
        
        sync_timestamp = datetime.now().isoformat()
        
        stats = {
            'songs_added': 0,
            'mp3_linked': 0,
            'sheets_linked': 0,
            'charts_migrated': 0,
            'errors': [],
            'debug': {
                'songs_in_repertoire': 0,
                'mp3_files_found': 0,
                'sheet_files_found': 0,
                'songlist_files_found': 0,
                'external_charts_found': 0,
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
                        
                        # Extract duration from MP3
                        duration = extract_mp3_duration(mp3_path)
                        
                        # Determine initial target based on default skills (+1)
                        default_count_row = cursor.execute(
                            'SELECT COUNT(*) AS c FROM repertoire_skills WHERE repertoire_id = ?',
                            (repertoire_id,)
                        ).fetchone()
                        default_skill_count = default_count_row['c'] if default_count_row else 0
                        initial_target = max(1, default_skill_count + 1)

                        # Create new song with MP3 linked
                        cursor.execute('''
                            INSERT INTO songs (
                                title, artist, song_number, repertoire_id, user_id,
                                priority, practice_count, practice_target, date_added, audio_path, release_date, duration
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            title, artist, max_num + 1, repertoire_id, rep['user_id'],
                            'mid', 0, initial_target, datetime.now().isoformat(), mp3_path, release_year, duration
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
                                
                                # Extract duration from MP3
                                duration = extract_mp3_duration(mp3_path)
                                
                                # Record old value before updating
                                cursor.execute('''
                                    INSERT INTO sync_history (
                                        repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (repertoire_id, sync_timestamp, 'field_updated', song['id'], 'audio_path', None, mp3_path))
                                
                                cursor.execute(
                                    'UPDATE songs SET audio_path = ?, duration = ? WHERE id = ?',
                                    (mp3_path, duration, song['id'])
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
                for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.doc', '.docx', '.odt']:
                    sheet_files.extend(glob.glob(os.path.join(rep['sheet_folder'], f'*{ext}')))
                
                stats['debug']['sheet_files_found'] = len(sheet_files)
                
                # Ensure charts folder exists
                charts_folder = os.path.join(os.getcwd(), 'charts')
                os.makedirs(charts_folder, exist_ok=True)
                
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
                        # Copy chart to local charts folder
                        ext = os.path.splitext(best_sheet)[1]
                        safe_title = ''.join(c for c in song['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                        dest_filename = f'{song["id"]}_{safe_title}{ext}'
                        dest_path = os.path.join(charts_folder, dest_filename)
                        
                        # Copy the file
                        shutil.copy2(best_sheet, dest_path)
                        
                        # Record old value before updating (None since chart_path was NULL)
                        cursor.execute('''
                            INSERT INTO sync_history (
                                repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (repertoire_id, sync_timestamp, 'field_updated', song['id'], 'chart_path', None, dest_path))
                        
                        cursor.execute(
                            'UPDATE songs SET chart_path = ? WHERE id = ?',
                            (dest_path, song['id'])
                        )
                        stats['sheets_linked'] += 1
            except Exception as e:
                stats['errors'].append(f'Sheet sync error: {str(e)}')
        
        # Step 4: Check existing charts and copy to local folder if needed
        try:
            # Get all songs with charts that are NOT in the charts folder
            charts_folder = os.path.join(os.getcwd(), 'charts')
            charts_folder_pattern = charts_folder + '%'
            
            songs_with_external_charts = cursor.execute('''
                SELECT id, title, chart_path 
                FROM songs 
                WHERE repertoire_id = ? 
                AND chart_path IS NOT NULL 
                AND chart_path NOT LIKE ?
            ''', (repertoire_id, charts_folder_pattern)).fetchall()
            
            stats['debug']['external_charts_found'] = len(songs_with_external_charts)
            
            os.makedirs(charts_folder, exist_ok=True)
            
            for song in songs_with_external_charts:
                old_chart_path = song['chart_path']
                
                # Resolve the path to work on any platform (Windows/WSL/Linux/Ubuntu)
                resolved_chart_path = resolve_chart_path(old_chart_path)
                
                # Check if the file exists
                if not os.path.exists(resolved_chart_path):
                    continue
                
                # Copy to charts folder
                ext = os.path.splitext(resolved_chart_path)[1]
                safe_title = ''.join(c for c in song['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                dest_filename = f'{song["id"]}_{safe_title}{ext}'
                dest_path = os.path.join(charts_folder, dest_filename)
                
                # Copy the file
                shutil.copy2(resolved_chart_path, dest_path)
                
                # Record the change
                cursor.execute('''
                    INSERT INTO sync_history (
                        repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (repertoire_id, sync_timestamp, 'chart_moved', song['id'], 'chart_path', old_chart_path, dest_path))
                
                # Update the database
                cursor.execute(
                    'UPDATE songs SET chart_path = ? WHERE id = ?',
                    (dest_path, song['id'])
                )
                stats['charts_migrated'] += 1
                
        except Exception as e:
            stats['errors'].append(f'Chart migration error: {str(e)}')
        
        return jsonify(stats)


@repertoires_bp.route('/api/repertoires/<int:repertoire_id>/undo-sync', methods=['POST'])
@login_required
def undo_sync_repertoire(repertoire_id):
    """Undo the last sync operation for a repertoire"""
    with get_db() as conn:
        cursor = conn.cursor()
        rep = require_repertoire(cursor, repertoire_id, g.current_user['id'])
        
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
            'charts_unlinked': 0,
            'charts_restored': 0,
            'files_deleted': 0
        }
        
        charts_folder = os.path.join(os.getcwd(), 'charts')
        
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
                    # Delete the file from charts folder if it was created during sync
                    if record['new_value'] and record['new_value'].startswith(charts_folder):
                        try:
                            if os.path.exists(record['new_value']):
                                os.remove(record['new_value'])
                                stats['files_deleted'] += 1
                        except Exception as e:
                            print(f"Error deleting file {record['new_value']}: {e}")
                    
                    cursor.execute(
                        'UPDATE songs SET chart_path = ? WHERE id = ?',
                        (record['old_value'], record['song_id'])
                    )
                    stats['charts_unlinked'] += 1
            
            elif record['operation_type'] == 'chart_moved':
                # Restore original chart path and delete copied file
                if record['new_value'] and os.path.exists(record['new_value']):
                    try:
                        os.remove(record['new_value'])
                        stats['files_deleted'] += 1
                    except Exception as e:
                        print(f"Error deleting file {record['new_value']}: {e}")
                
                cursor.execute(
                    'UPDATE songs SET chart_path = ? WHERE id = ?',
                    (record['old_value'], record['song_id'])
                )
                stats['charts_restored'] += 1
        
        # Clear the sync history after undoing
        cursor.execute('DELETE FROM sync_history WHERE repertoire_id = ?', (repertoire_id,))
        
        return jsonify(stats)


@repertoires_bp.route('/api/songs/lookup', methods=['POST'])
@login_required
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


@repertoires_bp.route('/api/repertoires/<int:repertoire_id>/setlist-pdf', methods=['POST'])
@login_required
def generate_setlist_pdf(repertoire_id):
    """Generate a PDF setlist for a repertoire"""
    data = request.json
    max_song_number = data.get('max_song_number', None)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get repertoire info
        repertoire = cursor.execute(
            'SELECT name, user_id FROM repertoires WHERE id = ?',
            (repertoire_id,)
        ).fetchone()
        
        if not repertoire or (g.current_user['role'] != 'admin' and repertoire['user_id'] != g.current_user['id']):
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
