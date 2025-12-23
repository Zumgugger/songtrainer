#!/usr/bin/env python3
"""Direct database check to understand data integrity"""

import sqlite3

def check_database():
    conn = sqlite3.connect('songs.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=" * 60)
    print("DATABASE INTEGRITY CHECK")
    print("=" * 60)
    
    # Check users
    users = cursor.execute('SELECT id, email, role FROM users').fetchall()
    print(f"\nUsers: {len(users)}")
    for user in users:
        print(f"  - {user['email']} (role: {user['role']})")
    
    # Check repertoires
    reps = cursor.execute('SELECT id, name, user_id FROM repertoires').fetchall()
    print(f"\nRepertoires: {len(reps)}")
    for rep in reps:
        song_count = cursor.execute('SELECT COUNT(*) as cnt FROM songs WHERE repertoire_id = ?', (rep['id'],)).fetchone()['cnt']
        print(f"  - [{rep['id']}] {rep['name']} (user: {rep['user_id']}, songs: {song_count})")
    
    # Check songs
    songs = cursor.execute('SELECT id, title, repertoire_id, user_id, practice_count, practice_target FROM songs LIMIT 10').fetchall()
    total_songs = cursor.execute('SELECT COUNT(*) as cnt FROM songs').fetchone()['cnt']
    print(f"\nSongs: {total_songs} total (showing first 10)")
    for song in songs:
        print(f"  - [{song['id']}] {song['title']} (rep: {song['repertoire_id']}, user: {song['user_id']}, target: {song['practice_target']})")
    
    # Check if songs have the required user_id
    print("\nSongs grouped by user:")
    user_songs = cursor.execute('SELECT user_id, COUNT(*) as cnt FROM songs GROUP BY user_id').fetchall()
    for row in user_songs:
        print(f"  - user {row['user_id']}: {row['cnt']} songs")
    
    # Check songs in each repertoire
    print("\nSongs per repertoire:")
    rep_songs = cursor.execute('''
        SELECT r.id, r.name, COUNT(s.id) as song_count
        FROM repertoires r
        LEFT JOIN songs s ON r.id = s.repertoire_id
        GROUP BY r.id
    ''').fetchall()
    for row in rep_songs:
        print(f"  - {row['name']}: {row['song_count']} songs")
    
    # Check skills
    skills = cursor.execute('SELECT COUNT(*) as cnt FROM skills').fetchone()
    print(f"\nSkills: {skills['cnt']}")
    
    conn.close()

if __name__ == '__main__':
    check_database()
