import sqlite3
from datetime import datetime
from contextlib import contextmanager

DATABASE = 'songs.db'

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize the database with tables and default skills"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create songs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                song_number INTEGER NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('low', 'mid', 'high')),
                practice_count INTEGER DEFAULT 0,
                practice_target INTEGER DEFAULT 0,
                last_practiced TEXT,
                date_added TEXT NOT NULL,
                notes TEXT,
                audio_path TEXT,
                chart_path TEXT
            )
        ''')
        
        # Create skills table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')
        
        # Create song_skills junction table (many-to-many with mastery status)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS song_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                skill_id INTEGER NOT NULL,
                is_mastered INTEGER DEFAULT 0,
                FOREIGN KEY (song_id) REFERENCES songs (id) ON DELETE CASCADE,
                FOREIGN KEY (skill_id) REFERENCES skills (id) ON DELETE CASCADE,
                UNIQUE(song_id, skill_id)
            )
        ''')
        
        # Create practice_sessions table (for tracking history)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS practice_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                practiced_at TEXT NOT NULL,
                FOREIGN KEY (song_id) REFERENCES songs (id) ON DELETE CASCADE
            )
        ''')
        
        # Insert default skills if they don't exist
        default_skills = [
            'Knowing the song',
            'Playing the bassline',
            'Singing backing vocals while playing',
            'Knowing by heart'
        ]
        
        for skill in default_skills:
            cursor.execute(
                'INSERT OR IGNORE INTO skills (name) VALUES (?)',
                (skill,)
            )
        
        print("Database initialized successfully!")

def ensure_audio_path_column():
    """Ensure songs.audio_path column exists for linking audio files."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(songs)').fetchall()
        colnames = {c['name'] for c in cols}
        if 'audio_path' not in colnames:
            cursor.execute('ALTER TABLE songs ADD COLUMN audio_path TEXT')
            print('Added audio_path column to songs table')

def ensure_chart_path_column():
    """Ensure songs.chart_path column exists for linking chart files."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(songs)').fetchall()
        colnames = {c['name'] for c in cols}
        if 'chart_path' not in colnames:
            cursor.execute('ALTER TABLE songs ADD COLUMN chart_path TEXT')
            print('Added chart_path column to songs table')

def ensure_indexes_and_normalize():
    """Create necessary indexes and normalize song_number to be 1..N sequential."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Ensure unique index on song_number for strict ordering
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_song_number
            ON songs (song_number)
        ''')

        # Normalize ordering: sort by current song_number, then id as tiebreaker
        rows = cursor.execute('SELECT id FROM songs ORDER BY song_number ASC, id ASC').fetchall()
        for i, row in enumerate(rows, start=1):
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, row['id']))

        print("Indexes ensured and song numbers normalized.")

if __name__ == '__main__':
    init_db()
    ensure_indexes_and_normalize()
    ensure_audio_path_column()
    ensure_chart_path_column()
