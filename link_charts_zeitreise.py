#!/usr/bin/env python3
"""
Link chart files from textsheets folder to Zumgugger repertoire songs
"""
import os
import re
from database import get_db

CHARTS_DIR = r"e:\Drive\Music Sync\Projekte\Zeitreise\textsheets"

def normalize_for_matching(text):
    """Normalize text for fuzzy matching"""
    # Convert to lowercase
    text = text.lower()
    # Remove apostrophes and special characters
    text = re.sub(r"['\"]", "", text)
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Strip whitespace
    return text.strip()

def find_chart_file(title, artist, year, chart_files):
    """Try to find matching chart file for a song"""
    # Normalize song info
    norm_title = normalize_for_matching(title)
    norm_artist = normalize_for_matching(artist)
    
    # Try different matching strategies
    for chart_file in chart_files:
        norm_chart = normalize_for_matching(chart_file)
        
        # Strategy 1: Match by title
        if norm_title in norm_chart:
            return chart_file
        
        # Strategy 2: Match by year and partial title (first few words)
        title_words = norm_title.split()[:3]  # First 3 words of title
        if year in chart_file and all(word in norm_chart for word in title_words):
            return chart_file
    
    return None

def main():
    # Get list of chart files (convert Windows path to WSL path for listing)
    charts_dir_wsl = CHARTS_DIR.replace('e:\\', '/mnt/e/').replace('\\', '/')
    
    if not os.path.exists(charts_dir_wsl):
        print(f"Error: Charts directory not found: {charts_dir_wsl}")
        return
    
    chart_files = [f for f in os.listdir(charts_dir_wsl) if f.endswith('.odt')]
    print(f"Found {len(chart_files)} chart files")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get Zumgugger repertoire ID
        rep = cursor.execute("SELECT id FROM repertoires WHERE name = 'Zumgugger'").fetchone()
        if not rep:
            print("Error: Zumgugger repertoire not found.")
            return
        
        repertoire_id = rep['id']
        
        # Get all songs in Zumgugger repertoire
        songs = cursor.execute('''
            SELECT id, title, artist, release_date FROM songs 
            WHERE repertoire_id = ?
            ORDER BY song_number
        ''', (repertoire_id,)).fetchall()
        
        linked = 0
        not_found = 0
        
        for song in songs:
            chart_file = find_chart_file(
                song['title'], 
                song['artist'], 
                song['release_date'] or '', 
                chart_files
            )
            
            if chart_file:
                chart_path = os.path.join(CHARTS_DIR, chart_file)
                cursor.execute(
                    'UPDATE songs SET chart_path = ? WHERE id = ?',
                    (chart_path, song['id'])
                )
                print(f"✅ Linked: {song['title']} → {chart_file}")
                linked += 1
            else:
                print(f"⚠️  No chart found for: {song['title']} - {song['artist']}")
                not_found += 1
        
        conn.commit()
        print(f"\n📊 Summary: {linked} charts linked, {not_found} not found")

if __name__ == '__main__':
    main()
