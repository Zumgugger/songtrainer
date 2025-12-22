#!/usr/bin/env python3
"""
Script to backfill song durations for existing linked audio files.
Usage: python update_song_durations.py [repertoire_name]
If no repertoire_name provided, updates all songs with linked audio.
"""

import sqlite3
import os
import sys
import json
import subprocess

# Ensure UTF-8 handling
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("ERROR: mutagen not installed. Run: pip install mutagen")
    sys.exit(1)


def extract_duration_mutagen(file_path):
    """Extract duration using mutagen."""
    if not file_path or not os.path.isfile(file_path):
        return None
    try:
        audio = MP3(file_path)
        if audio.info.length:
            return int(audio.info.length)
    except Exception:
        return None

def extract_duration_ffprobe(file_path):
    """Extract duration using ffprobe (fallback for problematic MP3s)."""
    if not file_path or not os.path.isfile(file_path):
        return None
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', file_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = int(float(data['format']['duration']))
            return duration if duration > 0 else None
    except Exception:
        pass
    return None

def extract_duration(file_path):
    """Extract duration in seconds from an MP3 file. Tries mutagen first, then ffprobe."""
    duration = extract_duration_mutagen(file_path)
    if duration:
        return duration
    # Fallback to ffprobe for problematic MP3s
    return extract_duration_ffprobe(file_path)


def convert_windows_path_to_wsl(win_path):
    """Convert Windows path to WSL path.
    e.g., 'e:\\path\\to\\file' -> '/mnt/e/path/to/file'
    """
    if not win_path:
        return None
    
    # Already a Unix path
    if win_path.startswith('/mnt/'):
        return win_path
    
    # Convert Windows drive letter and path
    # e.g., e:\path -> /mnt/e/path
    if len(win_path) >= 2 and win_path[1] == ':':
        drive_letter = win_path[0].lower()
        rest = win_path[2:].replace('\\', '/')
        return f'/mnt/{drive_letter}{rest}'
    
    return None


def find_mp3_by_title(title, folder_path):
    """Search folder for an MP3 matching the song title (fuzzy match).
    Returns the first matching file path or None.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return None
    
    title_lower = title.lower()
    
    try:
        for file in os.listdir(folder_path):
            if file.lower().endswith('.mp3'):
                file_lower = file.lower()
                # Match if title is in filename or filename is in title
                if title_lower in file_lower or file_lower.replace('.mp3', '') in title_lower:
                    full_path = os.path.join(folder_path, file)
                    if os.path.isfile(full_path):
                        return full_path
    except Exception:
        pass
    
    return None


def update_durations(repertoire_name=None):
    """Update durations for songs with linked audio."""
    conn = sqlite3.connect('songs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query based on repertoire_name
    if repertoire_name:
        songs = cursor.execute('''
            SELECT s.id, s.title, s.audio_path
            FROM songs s
            JOIN repertoires r ON r.id = s.repertoire_id
            WHERE r.name = ? AND s.audio_path IS NOT NULL AND (s.duration IS NULL OR s.duration = 0)
            ORDER BY s.song_number
        ''', (repertoire_name,)).fetchall()
        print(f"Updating durations for repertoire: {repertoire_name}")
    else:
        songs = cursor.execute('''
            SELECT s.id, s.title, s.audio_path
            FROM songs
            WHERE s.audio_path IS NOT NULL AND (s.duration IS NULL OR s.duration = 0)
            ORDER BY s.id
        ''').fetchall()
        print("Updating durations for all songs with linked audio")
    
    if not songs:
        print("No songs found needing duration updates.")
        conn.close()
        return
    
    print(f"Found {len(songs)} songs to process.\n")
    
    updated = 0
    failed = 0
    
    for i, song in enumerate(songs, 1):
        song_id = song['id']
        title = song['title']
        audio_path = song['audio_path']
        
        # Convert Windows path to WSL if needed
        wsl_path = convert_windows_path_to_wsl(audio_path)
        if not wsl_path:
            wsl_path = audio_path
        
        print(f"[{i}/{len(songs)}] {title}...", end=' ', flush=True)
        
        duration = extract_duration(wsl_path)
        
        # Fallback: search by title if exact path failed
        if duration is None:
            # Extract folder from original path
            folder = None
            if wsl_path:
                folder = os.path.dirname(wsl_path)
            
            if folder and os.path.isdir(folder):
                fallback_path = find_mp3_by_title(title, folder)
                if fallback_path:
                    duration = extract_duration(fallback_path)
        
        if duration is not None:
            cursor.execute('UPDATE songs SET duration = ? WHERE id = ?', (duration, song_id))
            conn.commit()
            print(f"✓ ({duration}s)")
            updated += 1
        else:
            print("✗ (failed to extract)")
            failed += 1
    
    conn.close()
    
    print(f"\n\nSummary:")
    print(f"  Updated: {updated}")
    print(f"  Failed:  {failed}")
    print(f"  Total:   {len(songs)}")


if __name__ == '__main__':
    repertoire_name = sys.argv[1] if len(sys.argv) > 1 else None
    update_durations(repertoire_name)
