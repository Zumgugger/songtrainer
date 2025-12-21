from flask import Flask, render_template, request, jsonify, send_file, abort, Response, session, redirect, url_for, g, make_response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from database import (
    get_db,
    init_db,
    ensure_indexes_and_normalize,
    ensure_audio_path_column,
    ensure_chart_path_column,
    ensure_repertoire_id_column,
    ensure_release_date_column,
    ensure_repertoire_sort_order_column,
    ensure_repertoire_folder_columns,
    ensure_sync_history_table,
    ensure_repertoire_notes_column,
    ensure_users_table,
    ensure_remember_tokens_table,
    ensure_default_admin,
    ensure_repertoire_user_column,
    ensure_song_user_column,
)
from datetime import datetime, timedelta
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
import sqlite3
import os
import glob
import urllib.request
import urllib.parse
import json
import time
import re
import secrets
import hashlib

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_COOKIE_SECURE', 'false').lower() == 'true'
app.permanent_session_lifetime = timedelta(hours=12)

REMEMBER_COOKIE_NAME = 'songtrainer_remember'
REMEMBER_TOKEN_DAYS = 30
RESET_TOKEN_HOURS = 2

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTS = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}
ALLOWED_CHART_EXTS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.doc', '.docx', '.odt'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database on first run
if not os.path.exists('songs.db'):
    init_db()

# Ensure constraints exist and ordering is normalized on startup
admin_user_id = None
try:
    ensure_users_table()
except Exception:
    pass

try:
    ensure_remember_tokens_table()
except Exception:
    pass

try:
    admin_user_id = ensure_default_admin()
except Exception:
    admin_user_id = None

try:
    ensure_repertoire_user_column(admin_user_id or ensure_default_admin())
except Exception:
    pass

try:
    ensure_song_user_column(admin_user_id or ensure_default_admin())
except Exception:
    pass

try:
    ensure_audio_path_column()
except Exception:
    pass
try:
    ensure_chart_path_column()
except Exception:
    pass
try:
    ensure_repertoire_id_column()
except Exception:
    pass
try:
    ensure_release_date_column()
except Exception:
    pass
try:
    ensure_repertoire_sort_order_column()
except Exception:
    pass
try:
    ensure_repertoire_folder_columns()
except Exception:
    pass
try:
    ensure_sync_history_table()
except Exception:
    pass
try:
    ensure_repertoire_notes_column()
except Exception:
    pass
try:
    ensure_indexes_and_normalize()
except Exception:
    pass

# ==================== AUTH HELPERS ====================


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _serialize_user(row):
    return {'id': row['id'], 'email': row['email'], 'role': row['role']}


def _load_user(user_id):
    if not user_id:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        return cursor.execute(
            'SELECT id, email, role FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()


def _clear_remember_token(token_cookie_value):
    if not token_cookie_value:
        return
    try:
        token_id_str, raw_token = token_cookie_value.split(':', 1)
        token_id = int(token_id_str)
    except Exception:
        return

    token_hash = _hash_token(raw_token)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM remember_tokens WHERE id = ? AND token_hash = ?',
            (token_id, token_hash)
        )


def _login_user(user_id, remember_me=False):
    """Set session and optional remember-me cookie value (token string)."""
    session['user_id'] = user_id
    session.permanent = True

    if not remember_me:
        return None

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    issued_at = datetime.now().isoformat()
    expires_at = (datetime.now() + timedelta(days=REMEMBER_TOKEN_DAYS)).isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO remember_tokens (user_id, token_hash, issued_at, expires_at) VALUES (?, ?, ?, ?)',
            (user_id, token_hash, issued_at, expires_at)
        )
        token_id = cursor.lastrowid

    return f"{token_id}:{raw_token}"


def _logout_user():
    token_cookie = request.cookies.get(REMEMBER_COOKIE_NAME)
    _clear_remember_token(token_cookie)
    session.pop('user_id', None)


def _set_remember_cookie(response, token_value):
    if token_value:
        response.set_cookie(
            REMEMBER_COOKIE_NAME,
            token_value,
            max_age=REMEMBER_TOKEN_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite='Lax',
            secure=app.config['SESSION_COOKIE_SECURE'],
            path='/'
        )
    else:
        response.delete_cookie(REMEMBER_COOKIE_NAME, path='/')
    return response


@app.before_request
def attach_current_user():
    g.current_user = None

    # Load from session first
    user_id = session.get('user_id')
    if user_id:
        user = _load_user(user_id)
        if user:
            g.current_user = user
            return
        session.pop('user_id', None)

    # Fallback to remember-me cookie
    remember_value = request.cookies.get(REMEMBER_COOKIE_NAME)
    if not remember_value:
        return

    try:
        token_id_str, raw_token = remember_value.split(':', 1)
        token_id = int(token_id_str)
    except Exception:
        return

    with get_db() as conn:
        cursor = conn.cursor()
        token_row = cursor.execute(
            'SELECT user_id, token_hash, expires_at FROM remember_tokens WHERE id = ?',
            (token_id,)
        ).fetchone()

    if not token_row:
        return

    try:
        expires_at = datetime.fromisoformat(token_row['expires_at'])
    except Exception:
        _clear_remember_token(remember_value)
        return

    if expires_at < datetime.now():
        _clear_remember_token(remember_value)
        return

    if token_row['token_hash'] != _hash_token(raw_token):
        _clear_remember_token(remember_value)
        return

    user = _load_user(token_row['user_id'])
    if user:
        session['user_id'] = user['id']
        g.current_user = user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(g, 'current_user', None):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = getattr(g, 'current_user', None)
        if not user:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login', next=request.path))
        if user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


def _resolve_scope_user_id(requested_user_id):
    """Admin can request another user_id; others stay on their own."""
    current = getattr(g, 'current_user', None)
    if not current:
        return None
    if current['role'] == 'admin' and requested_user_id:
        with get_db() as conn:
            cursor = conn.cursor()
            exists = cursor.execute('SELECT id FROM users WHERE id = ?', (requested_user_id,)).fetchone()
            if exists:
                return requested_user_id
    return current['id']


def _require_repertoire(cursor, repertoire_id, scope_user_id=None):
    scope = scope_user_id or (g.current_user['id'] if g.current_user else None)
    rep = cursor.execute('SELECT * FROM repertoires WHERE id = ?', (repertoire_id,)).fetchone()
    if not rep:
        abort(404)
    if g.current_user['role'] != 'admin' and rep['user_id'] != scope:
        abort(403)
    return rep


def _require_song(cursor, song_id, scope_user_id=None):
    scope = scope_user_id or (g.current_user['id'] if g.current_user else None)
    song = cursor.execute(
        '''
        SELECT s.*, r.user_id AS owner_id
        FROM songs s
        JOIN repertoires r ON r.id = s.repertoire_id
        WHERE s.id = ?
        ''',
        (song_id,)
    ).fetchone()
    if not song:
        abort(404)
    if g.current_user['role'] != 'admin' and song['owner_id'] != scope:
        abort(403)
    return song

# ==================== ROUTES ====================


@app.route('/login')
def login():
    if getattr(g, 'current_user', None):
        return redirect(url_for('index'))
    next_url = request.args.get('next', url_for('index'))
    return render_template('login.html', next_url=next_url)


@app.route('/logout', methods=['GET'])
def logout_page():
    _logout_user()
    resp = redirect(url_for('login'))
    _set_remember_cookie(resp, None)
    return resp


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    remember_me = bool(data.get('remember'))

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        user = cursor.execute(
            'SELECT id, email, password_hash, role FROM users WHERE lower(email) = ?',
            (email,)
        ).fetchone()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    remember_value = _login_user(user['id'], remember_me=remember_me)
    resp = jsonify({'user': _serialize_user(user)})
    _set_remember_cookie(resp, remember_value)
    return resp


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    _logout_user()
    resp = jsonify({'message': 'Logged out'})
    _set_remember_cookie(resp, None)
    return resp


@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    return jsonify({'user': _serialize_user(g.current_user)})


@app.route('/api/auth/reset/request', methods=['POST'])
def api_reset_request():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        user = cursor.execute(
            'SELECT id, email FROM users WHERE lower(email) = ?',
            (email,)
        ).fetchone()

        if not user:
            # Do not leak existence
            return jsonify({'message': 'If an account exists, a reset token was generated.'})

        reset_token = secrets.token_urlsafe(32)
        reset_hash = _hash_token(reset_token)
        expires_at = (datetime.now() + timedelta(hours=RESET_TOKEN_HOURS)).isoformat()
        cursor.execute(
            'UPDATE users SET reset_token = ?, reset_token_expires_at = ?, updated_at = ? WHERE id = ?',
            (reset_hash, expires_at, datetime.now().isoformat(), user['id'])
        )

    # Email sending is skipped; surface token for local testing
    return jsonify({
        'message': 'Reset token generated (email delivery disabled in this environment).',
        'reset_token': reset_token,
        'expires_at': expires_at,
    })


@app.route('/api/auth/reset/confirm', methods=['POST'])
def api_reset_confirm():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    token = data.get('token') or ''
    new_password = data.get('new_password') or ''

    if not email or not token or not new_password:
        return jsonify({'error': 'Email, token, and new password are required'}), 400
    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        user = cursor.execute(
            'SELECT id, reset_token, reset_token_expires_at FROM users WHERE lower(email) = ?',
            (email,)
        ).fetchone()

        if not user or not user['reset_token'] or not user['reset_token_expires_at']:
            return jsonify({'error': 'Invalid or expired token'}), 400

        try:
            expires_at = datetime.fromisoformat(user['reset_token_expires_at'])
        except Exception:
            return jsonify({'error': 'Invalid or expired token'}), 400

        if expires_at < datetime.now():
            return jsonify({'error': 'Invalid or expired token'}), 400

        if user['reset_token'] != _hash_token(token):
            return jsonify({'error': 'Invalid or expired token'}), 400

        new_hash = generate_password_hash(new_password)
        now = datetime.now().isoformat()
        cursor.execute(
            'UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires_at = NULL, updated_at = ? WHERE id = ?',
            (new_hash, now, user['id'])
        )
        cursor.execute('DELETE FROM remember_tokens WHERE user_id = ?', (user['id'],))

    resp = jsonify({'message': 'Password reset successful. Please log in.'})
    _set_remember_cookie(resp, None)
    return resp


# ==================== USERS API (ADMIN) ====================


@app.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    with get_db() as conn:
        cursor = conn.cursor()
        users = cursor.execute(
            'SELECT id, email, role, created_at, updated_at FROM users ORDER BY id'
        ).fetchall()
        return jsonify({'users': [dict(_serialize_user(u), created_at=u['created_at'], updated_at=u['updated_at']) for u in users]})


@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role', 'user')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    if role not in ('user', 'admin'):
        return jsonify({'error': 'Invalid role'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO users (email, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                (email, generate_password_hash(password), role, now, now)
            )
            user_id = cursor.lastrowid
            return jsonify({'id': user_id, 'message': 'User created'})
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Email already exists'}), 400


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    data = request.json or {}
    email = (data.get('email') or '').strip().lower() if data.get('email') is not None else None
    password = data.get('password')
    role = data.get('role')

    if password is not None and len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    if role is not None and role not in ('user', 'admin'):
        return jsonify({'error': 'Invalid role'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        existing = cursor.execute('SELECT id, role FROM users WHERE id = ?', (user_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'User not found'}), 404

        if role == 'user' and user_id == g.current_user['id']:
            return jsonify({'error': 'You cannot demote your own admin role'}), 400

        fields = []
        values = []
        if email is not None:
            fields.append('email = ?')
            values.append(email)
        if role is not None:
            fields.append('role = ?')
            values.append(role)
        if password is not None:
            fields.append('password_hash = ?')
            values.append(generate_password_hash(password))
        if not fields:
            return jsonify({'message': 'No changes applied'})
        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(user_id)

        try:
            cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Email already exists'}), 400

    return jsonify({'message': 'User updated'})


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == g.current_user['id']:
        return jsonify({'error': 'You cannot delete your own account'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        deleted = cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        if deleted.rowcount == 0:
            return jsonify({'error': 'User not found'}), 404
    return jsonify({'message': 'User deleted'})


@app.route('/api/users/<int:user_id>/progress', methods=['GET'])
@admin_required
def user_progress(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        user = cursor.execute('SELECT id, email FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        songs = cursor.execute(
            'SELECT id, practice_count, practice_target FROM songs WHERE user_id = ?',
            (user_id,)
        ).fetchall()
        song_ids = [s['id'] for s in songs]

        mastered = 0
        total_skills = 0
        if song_ids:
            placeholders = ','.join('?' for _ in song_ids)
            rows = cursor.execute(
                f'''SELECT is_mastered FROM song_skills WHERE song_id IN ({placeholders})''',
                song_ids
            ).fetchall()
            total_skills = len(rows)
            mastered = len([r for r in rows if r['is_mastered'] == 1])

        practiced_songs = len([s for s in songs if s['practice_count'] > 0])
        total_practice = sum(s['practice_count'] for s in songs)

        return jsonify({
            'user': _serialize_user(user),
            'songs_total': len(songs),
            'songs_practiced': practiced_songs,
            'practice_events': total_practice,
            'skills_total': total_skills,
            'skills_mastered': mastered
        })

@app.route('/')
@login_required
def index():
    """Main song list page"""
    return render_template('index.html')

@app.route('/admin')
@admin_required
def admin():
    """Admin page for managing skills"""
    return render_template('admin.html')

# ==================== SONGS API ====================

@app.route('/api/songs', methods=['GET'])
@login_required
def get_songs():
    """Get all songs for the scoped user, optionally filtered by repertoire"""
    repertoire_id = request.args.get('repertoire_id', type=int)
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = _resolve_scope_user_id(requested_user_id)

    with get_db() as conn:
        cursor = conn.cursor()

        if repertoire_id:
            _require_repertoire(cursor, repertoire_id, scope_user_id)
            songs = cursor.execute(
                '''SELECT * FROM songs WHERE user_id = ? AND repertoire_id = ? ORDER BY song_number ASC''',
                (scope_user_id, repertoire_id)
            ).fetchall()
        else:
            songs = cursor.execute(
                '''SELECT * FROM songs WHERE user_id = ? ORDER BY repertoire_id, song_number ASC''',
                (scope_user_id,)
            ).fetchall()

        songs_list = []
        for song in songs:
            skills = cursor.execute('''
                SELECT s.id, s.name, ss.is_mastered
                FROM skills s
                LEFT JOIN song_skills ss ON s.id = ss.skill_id AND ss.song_id = ?
                ORDER BY s.id
            ''', (song['id'],)).fetchall()

            song_dict = dict(song)
            song_dict['skills'] = [dict(skill) for skill in skills]

            total_skills = len([s for s in skills if s['is_mastered'] is not None])
            mastered_skills = len([s for s in skills if s['is_mastered'] == 1])
            song_dict['skills_progress'] = (mastered_skills / total_skills * 100) if total_skills > 0 else 0
            song_dict['practice_progress'] = (song['practice_count'] / song['practice_target'] * 100) if song['practice_target'] > 0 else 0

            songs_list.append(song_dict)

        return jsonify(songs_list)

@app.route('/api/songs', methods=['POST'])
@login_required
def create_song():
    """Create a new song"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()
        repertoire = _require_repertoire(cursor, data.get('repertoire_id'), g.current_user['id'])
        user_id = repertoire['user_id']

        cursor.execute('''
            INSERT INTO songs (title, artist, song_number, repertoire_id, user_id, priority, practice_target, date_added, release_date, notes, performance_hints)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['title'],
            data['artist'],
            data.get('song_number', 1),
            repertoire['id'],
            user_id,
            data.get('priority', 'mid'),
            data.get('practice_target', 0),
            datetime.now().isoformat(),
            data.get('release_date'),
            data.get('notes', ''),
            data.get('performance_hints', '')
        ))

        song_id = cursor.lastrowid

        if 'skill_ids' in data:
            for skill_id in data['skill_ids']:
                cursor.execute(
                    'INSERT INTO song_skills (song_id, skill_id, is_mastered) VALUES (?, ?, 0)',
                    (song_id, skill_id)
                )

        return jsonify({'id': song_id, 'message': 'Song created successfully'}), 201

@app.route('/api/songs/<int:song_id>', methods=['PUT'])
@login_required
def update_song(song_id):
    """Update a song"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()

        song_row = _require_song(cursor, song_id, g.current_user['id'])
        old_number = song_row['song_number']
        repertoire_id = song_row['repertoire_id']

        new_number = data.get('song_number', old_number)
        if not isinstance(new_number, int):
            try:
                new_number = int(new_number)
            except Exception:
                new_number = old_number

        if old_number != new_number:
            rows = cursor.execute(
                'SELECT id FROM songs WHERE repertoire_id = ? ORDER BY song_number ASC, id ASC',
                (repertoire_id,)
            ).fetchall()
            ids = [r['id'] for r in rows if r['id'] != song_id]
            max_count = len(ids) + 1
            new_number = max(1, min(new_number, max_count))
            ids.insert(new_number - 1, song_id)

            base = 100000
            for i, sid in enumerate(ids, start=1):
                cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (base + i, sid))
            for i, sid in enumerate(ids, start=1):
                cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, sid))

        cursor.execute('''
            UPDATE songs
            SET title = ?, artist = ?, song_number = ?, priority = ?, 
                practice_target = ?, release_date = ?, notes = ?, performance_hints = ?
            WHERE id = ?
        ''', (
            data.get('title'),
            data.get('artist'),
            new_number,
            data.get('priority', 'mid'),
            data.get('practice_target', 0),
            data.get('release_date'),
            data.get('notes', ''),
            data.get('performance_hints', ''),
            song_id
        ))

        if 'skill_ids' in data:
            current_skills = cursor.execute(
                'SELECT skill_id, is_mastered FROM song_skills WHERE song_id = ?',
                (song_id,)
            ).fetchall()
            current_skills_dict = {row['skill_id']: row['is_mastered'] for row in current_skills}

            selected_ids = set(data['skill_ids'])
            cursor.execute('DELETE FROM song_skills WHERE song_id = ? AND skill_id NOT IN ({})'.format(
                ','.join('?' * len(selected_ids)) if selected_ids else 'NULL'
            ), [song_id] + list(selected_ids) if selected_ids else [song_id])

            for skill_id in selected_ids:
                is_mastered = current_skills_dict.get(skill_id, 0)
                cursor.execute(
                    'INSERT OR REPLACE INTO song_skills (song_id, skill_id, is_mastered) VALUES (?, ?, ?)',
                    (song_id, skill_id, is_mastered)
                )

        return jsonify({'message': 'Song updated successfully'})

@app.route('/api/songs/<int:song_id>', methods=['DELETE'])
@login_required
def delete_song(song_id):
    """Delete a song"""
    with get_db() as conn:
        cursor = conn.cursor()
        _require_song(cursor, song_id, g.current_user['id'])
        cursor.execute('DELETE FROM songs WHERE id = ?', (song_id,))

        return jsonify({'message': 'Song deleted successfully'})

# ==================== PRACTICE API ====================

@app.route('/api/songs/<int:song_id>/practice', methods=['POST'])
@login_required
def practice_song(song_id):
    """Mark a song as practiced (increment counter and update last practiced)"""
    with get_db() as conn:
        cursor = conn.cursor()
        _require_song(cursor, song_id, g.current_user['id'])

        now = datetime.now().isoformat()

        cursor.execute(
            'UPDATE songs SET practice_count = practice_count + 1, last_practiced = ? WHERE id = ?',
            (now, song_id)
        )

        cursor.execute(
            'INSERT INTO practice_sessions (song_id, practiced_at) VALUES (?, ?)',
            (song_id, now)
        )

        return jsonify({'message': 'Practice recorded successfully'})

@app.route('/api/songs/<int:song_id>/target/increase', methods=['POST'])
@login_required
def increase_target(song_id):
    """Increase practice target by current practice count to reset progress bar while keeping history."""
    with get_db() as conn:
        cursor = conn.cursor()
        _require_song(cursor, song_id, g.current_user['id'])

        result = cursor.execute(
            'SELECT practice_count, practice_target FROM songs WHERE id = ?',
            (song_id,)
        ).fetchone()

        if not result:
            return jsonify({'error': 'Song not found'}), 404

        new_target = result['practice_target'] + result['practice_count']

        cursor.execute('UPDATE songs SET practice_target = ? WHERE id = ?', (new_target, song_id))

        return jsonify({'message': 'Target increased', 'new_target': new_target})

@app.route('/api/songs/<int:song_id>/skills/<int:skill_id>/toggle', methods=['POST'])
@login_required
def toggle_skill(song_id, skill_id):
    """Toggle skill mastery status"""
    with get_db() as conn:
        cursor = conn.cursor()
        _require_song(cursor, song_id, g.current_user['id'])

        result = cursor.execute(
            'SELECT is_mastered FROM song_skills WHERE song_id = ? AND skill_id = ?',
            (song_id, skill_id)
        ).fetchone()

        if result is None:
            return jsonify({'error': 'Skill not assigned to this song'}), 404

        new_status = 0 if result['is_mastered'] == 1 else 1

        cursor.execute(
            'UPDATE song_skills SET is_mastered = ? WHERE song_id = ? AND skill_id = ?',
            (new_status, song_id, skill_id)
        )

        return jsonify({'is_mastered': new_status})

@app.route('/api/songs/<int:song_id>/priority/toggle', methods=['POST'])
@login_required
def toggle_priority(song_id):
    """Toggle priority: mid -> high -> low -> mid"""
    with get_db() as conn:
        cursor = conn.cursor()
        _require_song(cursor, song_id, g.current_user['id'])

        result = cursor.execute('SELECT priority FROM songs WHERE id = ?', (song_id,)).fetchone()
        if not result:
            return jsonify({'error': 'Song not found'}), 404

        priority_cycle = {'mid': 'high', 'high': 'low', 'low': 'mid'}
        new_priority = priority_cycle.get(result['priority'], 'mid')

        cursor.execute('UPDATE songs SET priority = ? WHERE id = ?', (new_priority, song_id))

        return jsonify({'priority': new_priority})

# ==================== ORDERING API ====================

@app.route('/api/songs/reorder', methods=['POST'])
@login_required
def reorder_songs():
    """Reorder songs by array of song IDs in desired order; song_number becomes 1..N within repertoire."""
    data = request.json or {}
    ordered_ids = data.get('ordered_ids', [])
    repertoire_id = data.get('repertoire_id')

    if not isinstance(ordered_ids, list) or not all(isinstance(x, int) for x in ordered_ids):
        return jsonify({'error': 'ordered_ids must be an array of integers'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        scope_user_id = g.current_user['id']

        if repertoire_id:
            _require_repertoire(cursor, repertoire_id, scope_user_id)
            existing = cursor.execute(
                'SELECT id FROM songs WHERE repertoire_id = ? AND user_id = ? ORDER BY song_number ASC, id ASC',
                (repertoire_id, scope_user_id)
            ).fetchall()
        else:
            existing = cursor.execute(
                'SELECT id FROM songs WHERE user_id = ? ORDER BY song_number ASC, id ASC',
                (scope_user_id,)
            ).fetchall()
        
        existing_ids = [row['id'] for row in existing]
        if not existing_ids:
            return jsonify({'error': 'No songs available to reorder'}), 400

        seen = set(ordered_ids)
        remaining = [sid for sid in existing_ids if sid not in seen]
        full_order = ordered_ids + remaining

        base = 100000
        for i, sid in enumerate(full_order, start=1):
            if sid not in existing_ids:
                return jsonify({'error': 'Invalid song id in ordered_ids'}), 400
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (base + i, sid))
        for i, sid in enumerate(full_order, start=1):
            cursor.execute('UPDATE songs SET song_number = ? WHERE id = ?', (i, sid))

        return jsonify({'message': 'Order updated', 'count': len(full_order)})

# ==================== MEDIA SERVING ====================

def windows_path_to_wsl(win_path):
    """Convert Windows path to WSL path"""
    if not win_path:
        return None
    # Convert e:\ to /mnt/e/ and backslashes to forward slashes
    wsl_path = win_path.replace('e:\\', '/mnt/e/').replace('E:\\', '/mnt/e/')
    wsl_path = wsl_path.replace('\\', '/')
    return wsl_path

def resolve_chart_path(chart_path):
    """
    Resolve a chart path to work on any platform (Windows/WSL/Linux/Ubuntu).
    Handles Windows paths (e:\...), WSL paths (/mnt/e/...), and native Linux paths.
    """
    if not chart_path:
        return None
    
    # Normalize backslashes to forward slashes
    normalized = chart_path.replace('\\', '/')
    
    # If it's a Windows path (e.g., "e:/Drive/..."), convert to WSL
    if ':' in normalized and not normalized.startswith('/'):
        # Windows path like "e:/Drive/..." - convert to /mnt/e/Drive/...
        drive_letter = normalized[0].lower()
        rest = normalized[2:]  # Skip "e:/"
        return f'/mnt/{drive_letter}{rest}'
    
    # Otherwise return as-is (could be WSL /mnt/e/... or native /home/... or /root/...)
    return normalized

@app.route('/media/<int:song_id>')
@login_required
def media(song_id):
    """Serve the linked audio file for a song, if present."""
    with get_db() as conn:
        cur = conn.cursor()
        song = _require_song(cur, song_id, g.current_user['id'])
        path = song['audio_path']
        if not path:
            abort(404)
        wsl_path = windows_path_to_wsl(path)
        if not os.path.isfile(wsl_path):
            abort(404)
        with open(wsl_path, 'rb') as f:
            data = f.read()
        response = Response(data, mimetype='audio/mpeg')
        response.headers['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
        return response

@app.route('/chart/<int:song_id>')
@login_required
def chart(song_id):
    """Serve the linked chart file for a song, if present."""
    with get_db() as conn:
        cur = conn.cursor()
        song = _require_song(cur, song_id, g.current_user['id'])
        path = song['chart_path']
        if not path:
            abort(404)
        wsl_path = windows_path_to_wsl(path)
        if not os.path.isfile(wsl_path):
            abort(404)
        return send_file(wsl_path, as_attachment=False, download_name=os.path.basename(path))

@app.route('/api/songs/<int:song_id>/audio', methods=['POST', 'DELETE'])
@login_required
def manage_audio(song_id):
    """Attach or remove audio for a song.
    POST with JSON field 'file_path' to link to existing file.
    DELETE to unlink existing audio_path.
    """
    with get_db() as conn:
        cur = conn.cursor()
        exist = _require_song(cur, song_id, g.current_user['id'])

        if request.method == 'DELETE':
            cur.execute('UPDATE songs SET audio_path = NULL WHERE id = ?', (song_id,))
            return jsonify({'message': 'Audio link removed'})

        # POST - link to file path
        data = request.json
        if not data or 'file_path' not in data:
            return jsonify({'error': 'No file_path provided'}), 400
        
        file_path = data['file_path']
        
        # Validate file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ALLOWED_EXTS:
            return jsonify({'error': f'Unsupported file type {ext}'}), 400
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found at specified path'}), 404
        
        cur.execute('UPDATE songs SET audio_path = ? WHERE id = ?', (file_path, song_id))
        return jsonify({'message': 'Audio linked', 'audio_path': file_path})

@app.route('/api/songs/<int:song_id>/chart', methods=['POST', 'DELETE'])
@login_required
def manage_chart(song_id):
    """Attach or remove chart for a song.
    POST with JSON field 'file_path' to copy file to charts/ folder.
    DELETE to unlink existing chart_path.
    """
    with get_db() as conn:
        cur = conn.cursor()
        exist = _require_song(cur, song_id, g.current_user['id'])

        if request.method == 'DELETE':
            cur.execute('UPDATE songs SET chart_path = NULL WHERE id = ?', (song_id,))
            return jsonify({'message': 'Chart link removed'})

        # POST - copy file to charts folder
        data = request.json
        if not data or 'file_path' not in data:
            return jsonify({'error': 'No file_path provided'}), 400
        
        file_path = data['file_path']
        
        # Validate file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ALLOWED_CHART_EXTS:
            return jsonify({'error': f'Unsupported file type {ext}'}), 400
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found at specified path'}), 404
        
        # Copy file to charts folder
        charts_folder = os.path.join(os.getcwd(), 'charts')
        os.makedirs(charts_folder, exist_ok=True)
        
        # Get song title for filename
        song = cur.execute('SELECT title FROM songs WHERE id = ?', (song_id,)).fetchone()
        safe_title = ''.join(c for c in song['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
        dest_filename = f'{song_id}_{safe_title}{ext}'
        dest_path = os.path.join(charts_folder, dest_filename)
        
        # Copy the file
        import shutil
        shutil.copy2(file_path, dest_path)
        
        # Update database with local path
        cur.execute('UPDATE songs SET chart_path = ? WHERE id = ?', (dest_path, song_id))
        return jsonify({'message': 'Chart uploaded', 'chart_path': dest_path})

# ==================== SKILLS API ====================

@app.route('/api/skills', methods=['GET'])
@login_required
def get_skills():
    """Get all skills"""
    with get_db() as conn:
        cursor = conn.cursor()
        skills = cursor.execute('SELECT * FROM skills ORDER BY id').fetchall()

        return jsonify([dict(skill) for skill in skills])

@app.route('/api/skills', methods=['POST'])
@admin_required
def create_skill():
    """Create a new skill"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute('INSERT INTO skills (name) VALUES (?)', (data['name'],))
            skill_id = cursor.lastrowid

            return jsonify({'id': skill_id, 'message': 'Skill created successfully'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Skill already exists'}), 400

@app.route('/api/skills/<int:skill_id>', methods=['PUT'])
@admin_required
def update_skill(skill_id):
    """Update a skill"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute('UPDATE skills SET name = ? WHERE id = ?', (data['name'], skill_id))
            return jsonify({'message': 'Skill updated successfully'})
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Skill name already exists'}), 400

@app.route('/api/skills/<int:skill_id>', methods=['DELETE'])
@admin_required
def delete_skill(skill_id):
    """Delete a skill"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM skills WHERE id = ?', (skill_id,))

        return jsonify({'message': 'Skill deleted successfully'})

# ==================== REPERTOIRES API ====================

@app.route('/api/repertoires', methods=['GET'])
@login_required
def get_repertoires():
    """Get all repertoires with their default skills for the scoped user"""
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = _resolve_scope_user_id(requested_user_id)

    with get_db() as conn:
        cursor = conn.cursor()

        repertoires = cursor.execute(
            'SELECT * FROM repertoires WHERE user_id = ? ORDER BY COALESCE(sort_order, id), id',
            (scope_user_id,)
        ).fetchall()
        repertoires_list = []

        for rep in repertoires:
            rep_dict = dict(rep)

            skills = cursor.execute('''
                SELECT s.id, s.name
                FROM skills s
                INNER JOIN repertoire_skills rs ON s.id = rs.skill_id
                WHERE rs.repertoire_id = ?
                ORDER BY s.id
            ''', (rep['id'],)).fetchall()

            rep_dict['default_skills'] = [dict(skill) for skill in skills]

            song_count = cursor.execute(
                'SELECT COUNT(*) as count FROM songs WHERE repertoire_id = ? AND user_id = ?',
                (rep['id'], scope_user_id)
            ).fetchone()
            rep_dict['song_count'] = song_count['count']
            rep_dict['notes'] = rep['notes'] or ''

            repertoires_list.append(rep_dict)

        return jsonify(repertoires_list)

@app.route('/api/repertoires', methods=['POST'])
@login_required
def create_repertoire():
    """Create a new repertoire"""
    data = request.json or {}
    target_user_id = _resolve_scope_user_id(data.get('user_id', None))

    with get_db() as conn:
        cursor = conn.cursor()

        try:
            sort_max = cursor.execute(
                'SELECT COALESCE(MAX(sort_order), 0) as max_order FROM repertoires WHERE user_id = ?',
                (target_user_id,)
            ).fetchone()['max_order']

            cursor.execute(
                'INSERT INTO repertoires (name, date_created, user_id, sort_order) VALUES (?, ?, ?, ?)',
                (data['name'], datetime.now().isoformat(), target_user_id, sort_max + 1)
            )
            repertoire_id = cursor.lastrowid

            if 'skill_ids' in data:
                for skill_id in data['skill_ids']:
                    cursor.execute(
                        'INSERT INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                        (repertoire_id, skill_id)
                    )

            return jsonify({'id': repertoire_id, 'message': 'Repertoire created successfully'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Repertoire name already exists'}), 400

@app.route('/api/repertoires/<int:repertoire_id>', methods=['PUT'])
@login_required
def update_repertoire(repertoire_id):
    """Update a repertoire's name, folder paths, and default skills"""
    data = request.json or {}
    with get_db() as conn:
        cursor = conn.cursor()
        rep = _require_repertoire(cursor, repertoire_id, g.current_user['id'])

        if 'name' in data:
            try:
                cursor.execute(
                    'UPDATE repertoires SET name = ? WHERE id = ?',
                    (data['name'], repertoire_id)
                )
            except sqlite3.IntegrityError:
                return jsonify({'error': 'Repertoire name already exists'}), 400

        if 'notes' in data:
            cursor.execute(
                'UPDATE repertoires SET notes = ? WHERE id = ?',
                (data['notes'] or None, repertoire_id)
            )

        if 'songlist_folder' in data:
            cursor.execute(
                'UPDATE repertoires SET songlist_folder = ? WHERE id = ?',
                (data['songlist_folder'] or None, repertoire_id)
            )
        if 'mp3_folder' in data:
            cursor.execute(
                'UPDATE repertoires SET mp3_folder = ? WHERE id = ?',
                (data['mp3_folder'] or None, repertoire_id)
            )
        if 'sheet_folder' in data:
            cursor.execute(
                'UPDATE repertoires SET sheet_folder = ? WHERE id = ?',
                (data['sheet_folder'] or None, repertoire_id)
            )

        if 'skill_ids' in data:
            cursor.execute('DELETE FROM repertoire_skills WHERE repertoire_id = ?', (repertoire_id,))
            for skill_id in data['skill_ids']:
                cursor.execute(
                    'INSERT INTO repertoire_skills (repertoire_id, skill_id) VALUES (?, ?)',
                    (repertoire_id, skill_id)
                )

        return jsonify({'message': 'Repertoire updated successfully'})

@app.route('/api/repertoires/<int:repertoire_id>', methods=['DELETE'])
@login_required
def delete_repertoire(repertoire_id):
    """Delete a repertoire and cascade delete all songs in it"""
    with get_db() as conn:
        cursor = conn.cursor()
        _require_repertoire(cursor, repertoire_id, g.current_user['id'])

        song_count = cursor.execute(
            'SELECT COUNT(*) as count FROM songs WHERE repertoire_id = ?',
            (repertoire_id,)
        ).fetchone()

        cursor.execute('DELETE FROM songs WHERE repertoire_id = ?', (repertoire_id,))
        cursor.execute('DELETE FROM repertoires WHERE id = ?', (repertoire_id,))

        return jsonify({
            'message': 'Repertoire deleted successfully',
            'songs_deleted': song_count['count']
        })

@app.route('/api/repertoires/reorder', methods=['POST'])
@login_required
def reorder_repertoires():
    """Persist a new ordering of repertoires given an array of repertoire IDs."""
    data = request.json or {}
    order = data.get('order')
    if not isinstance(order, list) or not all(isinstance(i, int) for i in order):
        return jsonify({'error': 'Invalid order payload'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        scope_user_id = g.current_user['id']
        existing_ids = {row['id'] for row in cursor.execute('SELECT id FROM repertoires WHERE user_id = ?', (scope_user_id,)).fetchall()}
        if set(order) - existing_ids:
            return jsonify({'error': 'Unknown repertoire id(s) in order'}), 400

        for position, rep_id in enumerate(order, start=1):
            cursor.execute('UPDATE repertoires SET sort_order = ? WHERE id = ?', (position, rep_id))

    return jsonify({'message': 'Repertoires reordered successfully'})

@app.route('/api/repertoires/<int:repertoire_id>/sync', methods=['POST'])
@login_required
def sync_repertoire_folders(repertoire_id):
    """Scan MP3 folder, create songs from filenames, then link MP3s and sheets"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        rep = _require_repertoire(cursor, repertoire_id, g.current_user['id'])
        
        # Delete previous sync history for this repertoire
        cursor.execute('DELETE FROM sync_history WHERE repertoire_id = ?', (repertoire_id,))
        
        sync_timestamp = datetime.now().isoformat()
        
        stats = {
            'songs_added': 0,
            'mp3_linked': 0,
            'sheets_linked': 0,
            'charts_migrated': 0,
            'errors': [],
            'debug': {
                'songs_in_repertoire': 0,
                'mp3_files_found': 0,
                'sheet_files_found': 0,
                'songlist_files_found': 0,
                'external_charts_found': 0,
                'songlist_folder_path': rep['songlist_folder'],
                'mp3_folder_path': rep['mp3_folder'],
                'sheet_folder_path': rep['sheet_folder']
            }
        }
        
        # Count existing songs
        existing_songs_count = cursor.execute(
            'SELECT COUNT(*) as cnt FROM songs WHERE repertoire_id = ?',
            (repertoire_id,)
        ).fetchone()['cnt']
        stats['debug']['songs_in_repertoire'] = existing_songs_count
        
        # Step 1: Scan MP3 folder and create songs from MP3 filenames
        if rep['mp3_folder'] and os.path.isdir(rep['mp3_folder']):
            try:
                # Get existing song titles and linked audio paths
                existing_titles = {
                    row['title'].lower() 
                    for row in cursor.execute(
                        'SELECT title FROM songs WHERE repertoire_id = ?',
                        (repertoire_id,)
                    ).fetchall()
                }
                linked_audio_paths = {
                    row['audio_path']
                    for row in cursor.execute(
                        'SELECT audio_path FROM songs WHERE repertoire_id = ? AND audio_path IS NOT NULL',
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
                    # Skip if this MP3 is already linked to a song
                    if mp3_path in linked_audio_paths:
                        continue
                    
                    filename = os.path.basename(mp3_path)
                    name_no_ext = os.path.splitext(filename)[0]
                    
                    # Parse filename format: "YYYY - Title - Artist" or "Title - Artist" or "Title"
                    release_year = None
                    artist = 'Unknown'
                    title = name_no_ext.strip()
                    
                    if ' - ' in name_no_ext:
                        parts = name_no_ext.split(' - ')
                        
                        # Check if first part is a 4-digit year
                        if len(parts) >= 2 and parts[0].strip().isdigit() and len(parts[0].strip()) == 4:
                            release_year = parts[0].strip()
                            # Format: "YYYY - Title - Artist" or "YYYY - Title"
                            if len(parts) >= 3:
                                title = parts[1].strip()
                                artist = parts[2].strip()
                            else:
                                title = parts[1].strip()
                                artist = 'Unknown'
                        else:
                            # Format: "Title - Artist" or just "Title"
                            if len(parts) >= 2:
                                title = parts[0].strip()
                                artist = parts[1].strip()
                            else:
                                title = parts[0].strip()
                                artist = 'Unknown'
                    
                    # Check if song already exists by title
                    if title.lower() not in existing_titles:
                        # Get next song number
                        max_num = cursor.execute(
                            'SELECT COALESCE(MAX(song_number), 0) as max FROM songs WHERE repertoire_id = ?',
                            (repertoire_id,)
                        ).fetchone()['max']
                        
                        # Create new song with MP3 linked
                        cursor.execute('''
                            INSERT INTO songs (
                                title, artist, song_number, repertoire_id, user_id,
                                priority, practice_count, practice_target, date_added, audio_path, release_date
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            title, artist, max_num + 1, repertoire_id, rep['user_id'],
                            'mid', 0, 5, datetime.now().isoformat(), mp3_path, release_year
                        ))
                        
                        song_id = cursor.lastrowid
                        
                        # Record song creation in sync history
                        cursor.execute('''
                            INSERT INTO sync_history (
                                repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (repertoire_id, sync_timestamp, 'song_created', song_id, None, None, None))
                        
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
                                
                                # Record old value before updating
                                cursor.execute('''
                                    INSERT INTO sync_history (
                                        repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (repertoire_id, sync_timestamp, 'field_updated', song['id'], 'audio_path', None, mp3_path))
                                
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
                for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.doc', '.docx', '.odt']:
                    sheet_files.extend(glob.glob(os.path.join(rep['sheet_folder'], f'*{ext}')))
                
                stats['debug']['sheet_files_found'] = len(sheet_files)
                
                # Ensure charts folder exists
                charts_folder = os.path.join(os.getcwd(), 'charts')
                os.makedirs(charts_folder, exist_ok=True)
                
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
                        # Copy chart to local charts folder
                        ext = os.path.splitext(best_sheet)[1]
                        safe_title = ''.join(c for c in song['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                        dest_filename = f'{song["id"]}_{safe_title}{ext}'
                        dest_path = os.path.join(charts_folder, dest_filename)
                        
                        # Copy the file
                        import shutil
                        shutil.copy2(best_sheet, dest_path)
                        
                        # Record old value before updating (None since chart_path was NULL)
                        cursor.execute('''
                            INSERT INTO sync_history (
                                repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (repertoire_id, sync_timestamp, 'field_updated', song['id'], 'chart_path', None, dest_path))
                        
                        cursor.execute(
                            'UPDATE songs SET chart_path = ? WHERE id = ?',
                            (dest_path, song['id'])
                        )
                        stats['sheets_linked'] += 1
            except Exception as e:
                stats['errors'].append(f'Sheet sync error: {str(e)}')
        
        # Step 4: Check existing charts and copy to local folder if needed
        try:
            # Get all songs with charts that are NOT in the charts folder
            charts_folder = os.path.join(os.getcwd(), 'charts')
            charts_folder_pattern = charts_folder + '%'
            
            songs_with_external_charts = cursor.execute('''
                SELECT id, title, chart_path 
                FROM songs 
                WHERE repertoire_id = ? 
                AND chart_path IS NOT NULL 
                AND chart_path NOT LIKE ?
            ''', (repertoire_id, charts_folder_pattern)).fetchall()
            
            stats['debug']['external_charts_found'] = len(songs_with_external_charts)
            
            os.makedirs(charts_folder, exist_ok=True)
            
            for song in songs_with_external_charts:
                old_chart_path = song['chart_path']
                
                # Resolve the path to work on any platform (Windows/WSL/Linux/Ubuntu)
                resolved_chart_path = resolve_chart_path(old_chart_path)
                
                # Check if the file exists
                if not os.path.exists(resolved_chart_path):
                    continue
                
                # Copy to charts folder
                ext = os.path.splitext(resolved_chart_path)[1]
                safe_title = ''.join(c for c in song['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                dest_filename = f'{song["id"]}_{safe_title}{ext}'
                dest_path = os.path.join(charts_folder, dest_filename)
                
                # Copy the file
                import shutil
                shutil.copy2(resolved_chart_path, dest_path)
                
                # Record the change
                cursor.execute('''
                    INSERT INTO sync_history (
                        repertoire_id, sync_timestamp, operation_type, song_id, field_name, old_value, new_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (repertoire_id, sync_timestamp, 'chart_moved', song['id'], 'chart_path', old_chart_path, dest_path))
                
                # Update the database
                cursor.execute(
                    'UPDATE songs SET chart_path = ? WHERE id = ?',
                    (dest_path, song['id'])
                )
                stats['charts_migrated'] += 1
                
        except Exception as e:
            stats['errors'].append(f'Chart migration error: {str(e)}')
        
        return jsonify(stats)

@app.route('/api/repertoires/<int:repertoire_id>/undo-sync', methods=['POST'])
@login_required
def undo_sync_repertoire(repertoire_id):
    """Undo the last sync operation for a repertoire"""
    with get_db() as conn:
        cursor = conn.cursor()
        rep = _require_repertoire(cursor, repertoire_id, g.current_user['id'])
        
        # Get sync history for this repertoire
        history = cursor.execute(
            'SELECT * FROM sync_history WHERE repertoire_id = ? ORDER BY id',
            (repertoire_id,)
        ).fetchall()
        
        if not history:
            return jsonify({'error': 'No sync history to undo'}), 400
        
        stats = {
            'songs_deleted': 0,
            'audio_unlinked': 0,
            'charts_unlinked': 0,
            'charts_restored': 0,
            'files_deleted': 0
        }
        
        charts_folder = os.path.join(os.getcwd(), 'charts')
        
        # Reverse the operations
        for record in history:
            if record['operation_type'] == 'song_created':
                # Delete the song that was created
                cursor.execute('DELETE FROM songs WHERE id = ?', (record['song_id'],))
                stats['songs_deleted'] += 1
            
            elif record['operation_type'] == 'field_updated':
                # Restore the old value
                if record['field_name'] == 'audio_path':
                    cursor.execute(
                        'UPDATE songs SET audio_path = ? WHERE id = ?',
                        (record['old_value'], record['song_id'])
                    )
                    stats['audio_unlinked'] += 1
                
                elif record['field_name'] == 'chart_path':
                    # Delete the file from charts folder if it was created during sync
                    if record['new_value'] and record['new_value'].startswith(charts_folder):
                        try:
                            if os.path.exists(record['new_value']):
                                os.remove(record['new_value'])
                                stats['files_deleted'] += 1
                        except Exception as e:
                            print(f"Error deleting file {record['new_value']}: {e}")
                    
                    cursor.execute(
                        'UPDATE songs SET chart_path = ? WHERE id = ?',
                        (record['old_value'], record['song_id'])
                    )
                    stats['charts_unlinked'] += 1
            
            elif record['operation_type'] == 'chart_moved':
                # Restore original chart path and delete copied file
                if record['new_value'] and os.path.exists(record['new_value']):
                    try:
                        os.remove(record['new_value'])
                        stats['files_deleted'] += 1
                    except Exception as e:
                        print(f"Error deleting file {record['new_value']}: {e}")
                
                cursor.execute(
                    'UPDATE songs SET chart_path = ? WHERE id = ?',
                    (record['old_value'], record['song_id'])
                )
                stats['charts_restored'] += 1
        
        # Clear the sync history after undoing
        cursor.execute('DELETE FROM sync_history WHERE repertoire_id = ?', (repertoire_id,))
        
        return jsonify(stats)

@app.route('/api/songs/lookup', methods=['POST'])
@login_required
def lookup_song_metadata():
    """Look up song metadata (artist, release date) from MusicBrainz"""
    data = request.json
    title = data.get('title', '').strip()
    
    if not title:
        return jsonify({'error': 'Title required'}), 400
    
    try:
        # Query MusicBrainz API
        query = urllib.parse.quote(title)
        url = f'https://musicbrainz.org/ws/2/recording/?query=recording:{query}&fmt=json&limit=5'
        
        headers = {
            'User-Agent': 'SongTrainer/1.0 (https://github.com/yourapp)'
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
        
        recordings = result.get('recordings', [])
        if not recordings:
            return jsonify({'found': False})
        
        # Get best match (first result)
        best = recordings[0]
        
        metadata = {
            'found': True,
            'title': best.get('title', title),
            'artist': 'Unknown',
            'release_date': None
        }
        
        # Extract artist
        if 'artist-credit' in best and best['artist-credit']:
            metadata['artist'] = best['artist-credit'][0].get('name', 'Unknown')
        
        # Extract release date from first release
        if 'releases' in best and best['releases']:
            first_release = best['releases'][0]
            if 'date' in first_release:
                metadata['release_date'] = first_release['date']
        
        # Rate limiting (MusicBrainz requires 1 request per second)
        time.sleep(1)
        
        return jsonify(metadata)
        
    except Exception as e:
        return jsonify({'error': str(e), 'found': False}), 500

@app.route('/api/repertoires/<int:repertoire_id>/setlist-pdf', methods=['POST'])
@login_required
def generate_setlist_pdf(repertoire_id):
    """Generate a PDF setlist for a repertoire"""
    data = request.json
    max_song_number = data.get('max_song_number', None)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get repertoire info
        repertoire = cursor.execute(
            'SELECT name, user_id FROM repertoires WHERE id = ?',
            (repertoire_id,)
        ).fetchone()
        
        if not repertoire or (g.current_user['role'] != 'admin' and repertoire['user_id'] != g.current_user['id']):
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Get songs up to max_song_number
        if max_song_number:
            songs = cursor.execute('''
                SELECT song_number, title, performance_hints
                FROM songs 
                WHERE repertoire_id = ? AND song_number <= ?
                ORDER BY song_number ASC
            ''', (repertoire_id, max_song_number)).fetchall()
        else:
            songs = cursor.execute('''
                SELECT song_number, title, performance_hints
                FROM songs 
                WHERE repertoire_id = ?
                ORDER BY song_number ASC
            ''', (repertoire_id,)).fetchall()
        
        if not songs:
            return jsonify({'error': 'No songs found'}), 404
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
        
        # Container for PDF elements
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Add title
        elements.append(Paragraph(repertoire['name'], title_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Create setlist table data
        table_data = []
        for song in songs:
            song_text = song['title']
            
            # Format performance hints
            if song['performance_hints']:
                # Convert **text** to <b>text</b> for PDF
                hints = song['performance_hints']
                hints = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', hints)
                song_text += f' <font color="#7f8c8d">({hints})</font>'
            
            table_data.append([
                str(song['song_number']),
                Paragraph(song_text, styles['Normal'])
            ])
        
        # Create table
        table = Table(table_data, colWidths=[2*cm, 16*cm])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        filename = f"{repertoire['name']}_setlist.pdf"
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(debug=True, host='0.0.0.0', port=port)
