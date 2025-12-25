import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from werkzeug.security import generate_password_hash

DATABASE = 'songs.db'

# Defaults for bootstrapping the first admin user when none exist yet.
DEFAULT_ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
DEFAULT_ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

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


def _ensure_admin_user(cursor):
    """Ensure there is at least one admin user; returns (admin_id, created_password)."""
    created_password = None
    admin = cursor.execute('SELECT id FROM users WHERE role = "admin" LIMIT 1').fetchone()
    if admin:
        return admin['id'], created_password

    existing = cursor.execute('SELECT id FROM users LIMIT 1').fetchone()
    if existing:
        cursor.execute('UPDATE users SET role = "admin" WHERE id = ?', (existing['id'],))
        return existing['id'], created_password

    now = datetime.now().isoformat()
    password_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
    cursor.execute(
        'INSERT INTO users (email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
        (DEFAULT_ADMIN_EMAIL, password_hash, 'admin', now, now)
    )
    created_password = DEFAULT_ADMIN_PASSWORD
    return cursor.lastrowid, created_password

def init_db():
    """Initialize the database with tables and default skills"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'admin')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                reset_token TEXT,
                reset_token_expires_at TEXT
            )
        ''')

        # Remember-me tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_remember_tokens_user ON remember_tokens (user_id)')

        # Create repertoires table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repertoires (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_created TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                sort_order INTEGER,
                songlist_folder TEXT,
                mp3_folder TEXT,
                sheet_folder TEXT,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
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
                user_id INTEGER NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('low', 'mid', 'high')),
                practice_count INTEGER DEFAULT 0,
                practice_target INTEGER DEFAULT 0,
                last_practiced TEXT,
                date_added TEXT NOT NULL,
                release_date TEXT,
                notes TEXT,
                audio_path TEXT,
                chart_path TEXT,
                performance_hints TEXT,
                FOREIGN KEY (repertoire_id) REFERENCES repertoires (id) ON DELETE CASCADE
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
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
        
        # Ensure admin user exists
        admin_id, created_admin_password = _ensure_admin_user(cursor)

        # Create default repertoire if none exists
        repertoire_count = cursor.execute('SELECT COUNT(*) FROM repertoires').fetchone()[0]
        if repertoire_count == 0:
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO repertoires (name, date_created, user_id, sort_order) VALUES (?, ?, ?, ?)',
                ('My Repertoire', now, admin_id, 1)
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
        if created_admin_password:
            print(
                f"Created default admin user {DEFAULT_ADMIN_EMAIL} with password {created_admin_password}. "
                "Change this password immediately."
            )


def ensure_users_table():
    """Ensure users table exists with required columns."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
                created_at TEXT,
                updated_at TEXT,
                reset_token TEXT,
                reset_token_expires_at TEXT
            )
        ''')

        cols = {c['name'] for c in cursor.execute('PRAGMA table_info(users)').fetchall()}
        now = datetime.now().isoformat()

        if 'role' not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        if 'created_at' not in cols:
            cursor.execute('ALTER TABLE users ADD COLUMN created_at TEXT')
            cursor.execute('UPDATE users SET created_at = ? WHERE created_at IS NULL', (now,))
        if 'updated_at' not in cols:
            cursor.execute('ALTER TABLE users ADD COLUMN updated_at TEXT')
            cursor.execute('UPDATE users SET updated_at = ? WHERE updated_at IS NULL', (now,))
        if 'reset_token' not in cols:
            cursor.execute('ALTER TABLE users ADD COLUMN reset_token TEXT')
        if 'reset_token_expires_at' not in cols:
            cursor.execute('ALTER TABLE users ADD COLUMN reset_token_expires_at TEXT')


def ensure_remember_tokens_table():
    """Ensure remember_tokens table exists for persistent logins."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_remember_tokens_user ON remember_tokens (user_id)')


def ensure_default_admin():
    """Ensure at least one admin user exists and return its id."""
    ensure_users_table()
    with get_db() as conn:
        cursor = conn.cursor()
        admin_id, created_password = _ensure_admin_user(cursor)
        if created_password:
            print(
                f"Created default admin user {DEFAULT_ADMIN_EMAIL} with password {created_password}. "
                "Change this password immediately."
            )
        return admin_id


def ensure_repertoire_user_column(default_user_id):
    """Ensure repertoires.user_id exists and backfill with default user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(repertoires)').fetchall()
        colnames = {c['name'] for c in cols}
        if 'user_id' not in colnames:
            cursor.execute('ALTER TABLE repertoires ADD COLUMN user_id INTEGER')
            cursor.execute('UPDATE repertoires SET user_id = ?', (default_user_id,))
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_repertoires_user_id ON repertoires (user_id)')


def ensure_song_user_column(default_user_id):
    """Ensure songs.user_id exists and backfill based on repertoire ownership."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(songs)').fetchall()
        colnames = {c['name'] for c in cols}
        if 'user_id' not in colnames:
            cursor.execute('ALTER TABLE songs ADD COLUMN user_id INTEGER')
            # Try to backfill from repertoire ownership when available
            cursor.execute('''
                UPDATE songs
                SET user_id = (
                    SELECT r.user_id FROM repertoires r WHERE r.id = songs.repertoire_id
                )
                WHERE user_id IS NULL
            ''')
            cursor.execute('UPDATE songs SET user_id = ? WHERE user_id IS NULL', (default_user_id,))
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_user_id ON songs (user_id)')

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
            admin_id = ensure_default_admin()
            # Create default repertoire if it doesn't exist
            default_rep = cursor.execute(
                "SELECT id FROM repertoires WHERE name = 'My Repertoire'"
            ).fetchone()
            
            if not default_rep:
                now = datetime.now().isoformat()
                cursor.execute(
                    'INSERT INTO repertoires (name, date_created, user_id, sort_order) VALUES (?, ?, ?, ?)',
                    ('My Repertoire', now, admin_id, 1)
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
        
        if 'difficulty' not in colnames:
            cursor.execute('ALTER TABLE songs ADD COLUMN difficulty TEXT DEFAULT "normal" CHECK(difficulty IN ("easy", "normal", "hard"))')
            # Update all existing songs to have default difficulty
            cursor.execute('UPDATE songs SET difficulty = "normal" WHERE difficulty IS NULL')
            print('Added difficulty column to songs table with default "normal"')


def ensure_practice_targets_not_below_count():
    """Raise practice_target to match practice_count when target is set but behind the count."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE songs
               SET practice_target = practice_count
             WHERE practice_target > 0 AND practice_count > practice_target'''
        )
        updated = cursor.rowcount
        if updated:
            print(f'Normalized practice_target for {updated} song(s)')


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


def ensure_archive_repertoires():
    """Ensure each user has an Archive repertoire for unassigned songs."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get all users
        users = cursor.execute('SELECT id FROM users').fetchall()
        
        for user in users:
            user_id = user['id']
            
            # Check if user already has an Archive repertoire
            archive = cursor.execute(
                'SELECT id FROM repertoires WHERE user_id = ? AND name = ?',
                (user_id, 'Archive')
            ).fetchone()
            
            if not archive:
                # Create Archive repertoire for this user
                now = datetime.now().isoformat()
                cursor.execute(
                    '''INSERT INTO repertoires (name, date_created, user_id, sort_order)
                       VALUES (?, ?, ?, ?)''',
                    ('Archive', now, user_id, 0)
                )
                print(f'Created Archive repertoire for user {user_id}')
        
        conn.commit()


def ensure_settings_table():
    """Ensure settings table exists and default difficulty thresholds are populated."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # Seed default thresholds if missing
        defaults = [
            ('threshold_easy_days', '90'),
            ('threshold_normal_days', '60'),
            ('threshold_hard_days', '30'),
        ]
        for k, v in defaults:
            cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))
        conn.commit()


if __name__ == '__main__':
    init_db()
    ensure_users_table()
    ensure_remember_tokens_table()
    admin_id_main = ensure_default_admin()
    ensure_repertoire_user_column(admin_id_main)
    ensure_song_user_column(admin_id_main)
    ensure_audio_path_column()
    ensure_chart_path_column()
    ensure_repertoire_id_column()
    ensure_release_date_column()
    ensure_repertoire_sort_order_column()
    ensure_indexes_and_normalize()
    ensure_repertoire_folder_columns()
    ensure_performance_hints_column()
    ensure_practice_targets_not_below_count()
    ensure_repertoire_notes_column()
    ensure_practice_date_log_table()
    ensure_duration_column()
    ensure_sync_history_table()
    ensure_archive_repertoires()

def ensure_repertoire_notes_column():
    """Ensure repertoires table has notes column for storing repertoire-specific notes."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(repertoires)').fetchall()
        colnames = {c['name'] for c in cols}
        
        if 'notes' not in colnames:
            cursor.execute('ALTER TABLE repertoires ADD COLUMN notes TEXT')
            print('Added notes column to repertoires table')


def ensure_practice_date_log_table():
    """Ensure practice_date_log table exists for tracking daily practice counts per song."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create practice_date_log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS practice_date_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                practice_date TEXT NOT NULL,
                practice_count INTEGER DEFAULT 1,
                FOREIGN KEY (song_id) REFERENCES songs (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(song_id, user_id, practice_date)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_practice_date_log_song ON practice_date_log (song_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_practice_date_log_date ON practice_date_log (practice_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_practice_date_log_user ON practice_date_log (user_id)')
        print('Ensured practice_date_log table exists')


def ensure_duration_column():
    """Ensure songs table has duration column for storing audio duration in seconds."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(songs)').fetchall()
        colnames = {c['name'] for c in cols}
        
        if 'duration' not in colnames:
            cursor.execute('ALTER TABLE songs ADD COLUMN duration INTEGER')
            print('Added duration column to songs table')

def ensure_repertoire_copy_tracking_columns():
    """Ensure repertoires table has columns for tracking repertoire copies."""
    with get_db() as conn:
        cursor = conn.cursor()
        cols = cursor.execute('PRAGMA table_info(repertoires)').fetchall()
        colnames = {c['name'] for c in cols}
        
        if 'copied_from_user_id' not in colnames:
            cursor.execute('ALTER TABLE repertoires ADD COLUMN copied_from_user_id INTEGER')
            print('Added copied_from_user_id column to repertoires table')
        
        if 'copied_date' not in colnames:
            cursor.execute('ALTER TABLE repertoires ADD COLUMN copied_date TEXT')
            print('Added copied_date column to repertoires table')