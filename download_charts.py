#!/usr/bin/env python3
"""
Download all linked charts from songs to the local charts/ folder.
This allows easy deployment and portability of the app.
"""

import os
import shutil
from pathlib import Path
from database import get_db

CHARTS_FOLDER = os.path.join(os.getcwd(), 'charts')

def download_charts():
    """Download all linked chart files to local charts folder"""
    
    # Ensure charts folder exists
    os.makedirs(CHARTS_FOLDER, exist_ok=True)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get all songs with chart paths
        songs = cursor.execute(
            'SELECT id, title, chart_path FROM songs WHERE chart_path IS NOT NULL'
        ).fetchall()
        
        if not songs:
            print('No charts to download.')
            return
        
        downloaded = 0
        skipped = 0
        errors = 0
        
        for song in songs:
            song_id = song['id']
            title = song['title']
            chart_path = song['chart_path']
            
            # Skip if file doesn't exist
            if not os.path.exists(chart_path):
                print(f'❌ SKIP: {title} - File not found: {chart_path}')
                skipped += 1
                continue
            
            try:
                # Get file extension
                _, ext = os.path.splitext(chart_path)
                
                # Create destination filename: song_id_title.extension
                # Replace problematic characters
                safe_title = ''.join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                dest_filename = f'{song_id}_{safe_title}{ext}'
                dest_path = os.path.join(CHARTS_FOLDER, dest_filename)
                
                # Copy file
                shutil.copy2(chart_path, dest_path)
                
                # Update database to point to local chart
                cursor.execute(
                    'UPDATE songs SET chart_path = ? WHERE id = ?',
                    (dest_path, song_id)
                )
                
                print(f'✅ Downloaded: {title} -> {dest_filename}')
                downloaded += 1
                
            except Exception as e:
                print(f'⚠️ ERROR: {title} - {str(e)}')
                errors += 1
        
        print(f'\n--- Summary ---')
        print(f'Downloaded: {downloaded}')
        print(f'Skipped: {skipped}')
        print(f'Errors: {errors}')
        print(f'Total: {downloaded + skipped + errors}')

if __name__ == '__main__':
    print('Downloading all linked charts to local charts/ folder...\n')
    download_charts()
    print('\nDone!')
