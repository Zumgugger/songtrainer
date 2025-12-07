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
        
        # Create repertoires table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repertoires (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                date_created TEXT NOT NULL
            )
        ''')
        
        # Create songs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                song_number INTEGER NOT NULL,
                repertoire_id INTEGER NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('low', 'mid', 'high')),
                practice_count INTEGER DEFAULT 0,
                practice_target INTEGER DEFAULT 0,
                last_practiced TEXT,
                date_added TEXT NOT NULL,
                release_date TEXT,
                notes TEXT,
                audio_path TEXT,
                chart_path TEXT,
                FOREIGN KEY (repertoire_id) REFERENCES repertoires (id) ON DELETE CASCADE
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
        
        # Create repertoire_skills table (default skills for each repertoire)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repertoire_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repertoire_id INTEGER NOT NULL,
                skill_id INTEGER NOT NULL,
                FOREIGN KEY (repertoire_id) REFERENCES repertoires (id) ON DELETE CASCADE,
                FOREIGN KEY (skill_id) REFERENCES skills (id) ON DELETE CASCADE,
                UNIQUE(repertoire_id, skill_id)
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
        
        # Create default repertoire if none exists
        repertoire_count = cursor.execute('SELECT COUNT(*) FROM repertoires').fetchone()[0]
        if repertoire_count == 0:
            cursor.execute(
                'INSERT INTO repertoires (name, date_created) VALUES (?, ?)',
                ('My Repertoire', datetime.now().isoformat())
            )
            repertoire_id = cursor.lastrowid
            
            # Assign all default skills to the default repertoire
            skill_ids = cursor.execute('SELECT id FROM skills').fetchall()
            for skill in skill_ids:
                cursor.execute(
                    'INSERT INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                    (repertoire_id, skill['id'])
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

def ensure_repertoire_id_column():
    """Ensure songs.repertoire_id column exists and migrate existing songs to default repertoire."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(songs)').fetchall()
        colnames = {c['name'] for c in cols}
        
        if 'repertoire_id' not in colnames:
            # Create default repertoire if it doesn't exist
            default_rep = cursor.execute(
                "SELECT id FROM repertoires WHERE name = 'My Repertoire'"
            ).fetchone()
            
            if not default_rep:
                cursor.execute(
                    'INSERT INTO repertoires (name, date_created) VALUES (?, ?)',
                    ('My Repertoire', datetime.now().isoformat())
                )
                default_rep_id = cursor.lastrowid
                
                # Assign all skills to default repertoire
                skill_ids = cursor.execute('SELECT id FROM skills').fetchall()
                for skill in skill_ids:
                    cursor.execute(
                        'INSERT OR IGNORE INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                        (default_rep_id, skill['id'])
                    )
            else:
                default_rep_id = default_rep['id']
            
            # Add column and set all existing songs to default repertoire
            cursor.execute('ALTER TABLE songs ADD COLUMN repertoire_id INTEGER')
            cursor.execute('UPDATE songs SET repertoire_id = ?', (default_rep_id,))
            print(f'Added repertoire_id column and migrated {cursor.rowcount} songs to default repertoire')
            
            # Drop old unique index and create new one
            cursor.execute('DROP INDEX IF EXISTS idx_songs_song_number')
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_repertoire_song_number
                ON songs (repertoire_id, song_number)
            ''')
            print('Updated song_number index to be per-repertoire')

def ensure_release_date_column():
    """Ensure songs.release_date column exists for optional release date tracking."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(songs)').fetchall()
        colnames = {c['name'] for c in cols}
        if 'release_date' not in colnames:
            cursor.execute('ALTER TABLE songs ADD COLUMN release_date TEXT')
            print('Added release_date column to songs table')

def ensure_repertoire_sort_order_column():
    """Ensure repertoires.sort_order column exists to allow manual ordering of repertoires."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(repertoires)').fetchall()
        colnames = {c['name'] for c in cols}
        if 'sort_order' not in colnames:
            cursor.execute('ALTER TABLE repertoires ADD COLUMN sort_order INTEGER')
            # Initialize sort_order sequentially by id
            rows = cursor.execute('SELECT id FROM repertoires ORDER BY id').fetchall()
            for i, row in enumerate(rows, start=1):
                cursor.execute('UPDATE repertoires SET sort_order = ? WHERE id = ?', (i, row['id']))
            print('Added sort_order column to repertoires and initialized ordering')

def ensure_indexes_and_normalize():
    """Create necessary indexes and normalize song_number to be 1..N sequential per repertoire."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Ensure unique index on (repertoire_id, song_number) for strict ordering per repertoire
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_repertoire_song_number
            ON songs (repertoire_id, song_number)
        ''')

        # Normalize ordering per repertoire: sort by current song_number, then id as tiebreaker
        repertoires = cursor.execute('SELECT id FROM repertoires').fetchall()
        for rep in repertoires:
            rows = cursor.execute(
                'SELECT id FROM songs WHERE repertoire_id = ? ORDER BY song_number ASC, id ASC',
                (rep['id'],)
            ).fetchall()
            for i, row in enumerate(rows, start=1):
                cursor.execute(
                    'UPDATE songs SET song_number = ? WHERE id = ?',
                    (i, row['id'])
                )

        print("Indexes ensured and song numbers normalized per repertoire.")

def ensure_repertoire_folder_columns():
    """Ensure repertoires table has folder path columns for songlist, mp3, and sheet."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(repertoires)').fetchall()
        colnames = {c['name'] for c in cols}
        
        columns_to_add = [
            ('songlist_folder', 'TEXT'),
            ('mp3_folder', 'TEXT'),
            ('sheet_folder', 'TEXT')
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in colnames:
                cursor.execute(f'ALTER TABLE repertoires ADD COLUMN {col_name} {col_type}')
                print(f'Added {col_name} column to repertoires table')

def ensure_performance_hints_column():
    """Ensure songs table has performance_hints column."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(songs)').fetchall()
        colnames = {c['name'] for c in cols}
        
        if 'performance_hints' not in colnames:
            cursor.execute('ALTER TABLE songs ADD COLUMN performance_hints TEXT')
            print('Added performance_hints column to songs table')

def ensure_sync_history_table():
    """Ensure sync_history table exists for undo functionality."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create sync_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repertoire_id INTEGER NOT NULL,
                sync_timestamp TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                song_id INTEGER,
                field_name TEXT,
                old_value TEXT,
                new_value TEXT,
                FOREIGN KEY (repertoire_id) REFERENCES repertoires (id) ON DELETE CASCADE
            )
        ''')
        print('Ensured sync_history table exists')

if __name__ == '__main__':
    init_db()
    ensure_audio_path_column()
    ensure_chart_path_column()
    ensure_repertoire_id_column()
    ensure_release_date_column()
    ensure_repertoire_sort_order_column()
    ensure_indexes_and_normalize()
    ensure_repertoire_folder_columns()
    ensure_performance_hints_column()
    ensure_sync_history_table()
