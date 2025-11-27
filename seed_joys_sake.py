#!/usr/bin/env python3
"""
Seed Joy's sake repertoire with songs
"""
import os
import re
from database import get_db
from datetime import datetime

# Song list with file paths
SONG_FILES = [
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\when it rains it pours - luke combs in G.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\bulletproof - nate smith.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\can't you see - black stone cherry.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\down by the river - the new roses.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\drinking it wrong - adam doleac.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\Every little bit helps in A.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\fade away - black stone cherry.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\hot tin roof - brian howe in G.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\I'll bring the music - parmalee in E.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\I'll take the chevy in A.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\Intro in E .mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\killing floor - black stone cherry.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\like i roll - black stone cherry.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\loud love in C.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\meet me half way - the new roses.mp3",
    r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\mp3\such a shame - black stone cherry in hph.mp3",
]

CHARTS_DIR = r"e:\Drive\Music Sync\Projekte\Joy's sake\Joy's sake Google Cloud\Leadsheets"

def parse_filename(filepath):
    """Extract title and artist from filename"""
    # Handle both Windows and Unix paths - extract just the filename
    if '\\' in filepath:
        basename = filepath.split('\\')[-1]
    else:
        basename = os.path.basename(filepath)
    
    # Remove .mp3 extension
    basename = basename.replace('.mp3', '')
    
    # Remove key annotations like "in G", "in A", "in E", "in hph", etc.
    basename = re.sub(r'\s+in\s+[A-G](?:ph)?(?:m)?(?:aj)?(?:h)?(?:ph)?\s*$', '', basename, flags=re.IGNORECASE)
    basename = re.sub(r'\s+in\s+[A-G](?:ph)?(?:m)?(?:aj)?(?:h)?(?:ph)?\s*$', '', basename, flags=re.IGNORECASE)
    
    # Pattern: TITLE - ARTIST
    if ' - ' in basename:
        parts = basename.split(' - ')
        title = parts[0].strip()
        artist = ' - '.join(parts[1:]).strip() if len(parts) > 1 else 'Unknown'
    else:
        # No artist separator, treat as title only
        title = basename.strip()
        artist = 'Unknown'
    
    # Capitalize properly
    title = title.title()
    artist = artist.title()
    
    return title, artist

def normalize_for_matching(text):
    """Normalize text for fuzzy matching"""
    text = text.lower()
    text = re.sub(r"['\"]", "", text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def find_chart_file(title, artist, chart_files):
    """Try to find matching chart file for a song"""
    norm_title = normalize_for_matching(title)
    norm_artist = normalize_for_matching(artist)
    
    for chart_file in chart_files:
        norm_chart = normalize_for_matching(chart_file)
        
        # Match by title
        if norm_title in norm_chart:
            return chart_file
        
        # Match by partial title (first few words)
        title_words = norm_title.split()[:3]
        if all(word in norm_chart for word in title_words):
            return chart_file
    
    return None

def main():
    # Convert Windows path to WSL for listing chart files
    charts_dir_wsl = CHARTS_DIR.replace('e:\\', '/mnt/e/').replace('E:\\', '/mnt/e/').replace('\\', '/')
    
    chart_files = []
    if os.path.exists(charts_dir_wsl):
        chart_files = [f for f in os.listdir(charts_dir_wsl) if f.endswith(('.pdf', '.odt', '.doc', '.docx'))]
        print(f"Found {len(chart_files)} chart files")
    else:
        print(f"Warning: Charts directory not found: {charts_dir_wsl}")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get Joy's sake repertoire ID
        rep = cursor.execute("SELECT id FROM repertoires WHERE name = 'Joy''s sake'").fetchone()
        if not rep:
            print("Error: Joy's sake repertoire not found. Please create it first.")
            return
        
        repertoire_id = rep['id']
        
        # Get current max song_number for this repertoire
        max_num = cursor.execute(
            'SELECT COALESCE(MAX(song_number), 0) as max FROM songs WHERE repertoire_id = ?',
            (repertoire_id,)
        ).fetchone()
        current_number = max_num['max']
        
        added = 0
        skipped = 0
        
        for song_file in SONG_FILES:
            title, artist = parse_filename(song_file)
            
            if not title:
                print(f"⚠️  Could not parse: {os.path.basename(song_file)}")
                skipped += 1
                continue
            
            # Check if song already exists (by title + artist)
            existing = cursor.execute(
                'SELECT id FROM songs WHERE LOWER(title) = LOWER(?) AND LOWER(artist) = LOWER(?) AND repertoire_id = ?',
                (title, artist, repertoire_id)
            ).fetchone()
            
            if existing:
                print(f"⏭️  Already exists: {title} - {artist}")
                skipped += 1
                continue
            
            # Find matching chart file
            chart_path = None
            if chart_files:
                chart_file = find_chart_file(title, artist, chart_files)
                if chart_file:
                    chart_path = os.path.join(CHARTS_DIR, chart_file)
            
            current_number += 1
            
            # Insert song
            cursor.execute('''
                INSERT INTO songs (title, artist, repertoire_id, song_number, practice_target, 
                                 last_practiced, audio_path, chart_path, priority, date_added)
                VALUES (?, ?, ?, ?, 0, NULL, ?, ?, 'low', ?)
            ''', (title, artist, repertoire_id, current_number, song_file, chart_path, datetime.now().isoformat()))
            
            chart_status = f" + chart: {os.path.basename(chart_path)}" if chart_path else ""
            print(f"✅ Added: {title} - {artist}{chart_status}")
            added += 1
        
        conn.commit()
        print(f"\n🎵 Summary: {added} songs added, {skipped} skipped")

if __name__ == '__main__':
    main()
