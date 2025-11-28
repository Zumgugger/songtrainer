#!/usr/bin/env python3
"""Fix sync function to scan MP3 files and create songs"""

import re

# Read the file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the sync_repertoire_folders function
old_pattern = r'def sync_repertoire_folders\(repertoire_id\):.*?return jsonify\(stats\)'

new_function = '''def sync_repertoire_folders(repertoire_id):
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
        
        stats = {
            'songs_added': 0,
            'mp3_linked': 0,
            'sheets_linked': 0,
            'errors': [],
            'debug': {
                'mp3_files_found': 0,
                'sheet_files_found': 0
            }
        }
        
        # Step 1: Scan MP3 folder and create songs from MP3 filenames
        if rep['mp3_folder'] and os.path.isdir(rep['mp3_folder']):
            try:
                # Get existing song titles
                existing_titles = {
                    row['title'].lower() 
                    for row in cursor.execute(
                        'SELECT title FROM songs WHERE repertoire_id = ?',
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
                    filename = os.path.basename(mp3_path)
                    name_no_ext = os.path.splitext(filename)[0]
                    
                    # Parse "Artist - Title" format, fallback to just title
                    if ' - ' in name_no_ext:
                        parts = name_no_ext.split(' - ', 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()
                    else:
                        artist = 'Unknown'
                        title = name_no_ext.strip()
                    
                    # Check if song already exists
                    if title.lower() not in existing_titles:
                        # Get next song number
                        max_num = cursor.execute(
                            'SELECT COALESCE(MAX(song_number), 0) as max FROM songs WHERE repertoire_id = ?',
                            (repertoire_id,)
                        ).fetchone()['max']
                        
                        # Create new song with MP3 linked
                        cursor.execute(\'\'\'
                            INSERT INTO songs (
                                title, artist, song_number, repertoire_id,
                                priority, practice_count, practice_target, date_added, audio_path
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        \'\'\', (
                            title, artist, max_num + 1, repertoire_id,
                            'mid', 0, 0, datetime.now().isoformat(), mp3_path
                        ))
                        
                        song_id = cursor.lastrowid
                        
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
                        cursor.execute(
                            'UPDATE songs SET chart_path = ? WHERE id = ?',
                            (best_sheet, song['id'])
                        )
                        stats['sheets_linked'] += 1
            except Exception as e:
                stats['errors'].append(f'Sheet sync error: {str(e)}')
        
        return jsonify(stats)'''

# Replace using regex with DOTALL flag
content = re.sub(old_pattern, new_function, content, flags=re.DOTALL)

# Write back
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Updated sync_repertoire_folders function")
