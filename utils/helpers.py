"""Helper functions for MP3 extraction and time calculations."""

import os
from datetime import datetime
try:
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


def extract_mp3_duration(file_path):
    """Extract duration in seconds from an MP3 file. Returns None if extraction fails."""
    if not MUTAGEN_AVAILABLE or not file_path:
        return None
    try:
        if not os.path.isfile(file_path):
            return None
        audio = MP3(file_path)
        if audio.info.length:
            return int(audio.info.length)
    except Exception:
        pass
    return None


def calculate_time_practiced_since(get_db, start_date_str, repertoire_id=None, user_id=None):
    """
    Calculate total practice time since a given date.
    Returns dict with 'seconds', 'hours', 'minutes', 'formatted' keys.
    If repertoire_id is provided, only count songs in that repertoire.
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except:
        return {'seconds': 0, 'hours': 0, 'minutes': 0, 'formatted': '0h 0m'}
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        if repertoire_id:
            # Time for specific repertoire
            query = '''
                SELECT SUM(s.duration * pl.practice_count) as total_seconds
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE s.repertoire_id = ?
                AND pl.user_id = ?
                AND pl.practice_date >= ?
                AND s.duration IS NOT NULL
            '''
            result = cursor.execute(query, (repertoire_id, user_id, start_date_str)).fetchone()
        else:
            # Total time across all repertoires
            query = '''
                SELECT SUM(s.duration * pl.practice_count) as total_seconds
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                AND s.duration IS NOT NULL
            '''
            result = cursor.execute(query, (user_id, start_date_str)).fetchone()
        
        total_seconds = result['total_seconds'] or 0
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        formatted = f"{hours}h {minutes}m" if hours > 0 or minutes > 0 else "0h 0m"
        
        return {
            'seconds': total_seconds,
            'hours': hours,
            'minutes': minutes,
            'formatted': formatted
        }
