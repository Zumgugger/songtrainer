"""Authentication blueprint for login, logout, password reset, and user management."""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, g, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from database import get_db
from utils.decorators import login_required, admin_required
import sqlite3
import secrets
import hashlib

auth = Blueprint('auth', __name__)

# Constants
REMEMBER_COOKIE_NAME = 'songtrainer_remember'
REMEMBER_TOKEN_DAYS = 30
RESET_TOKEN_HOURS = 2


# ==================== HELPER FUNCTIONS ====================

def _hash_token(token: str) -> str:
    """Hash a token using SHA256."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _serialize_user(row):
    """Convert user row to dict for JSON response."""
    return {'id': row['id'], 'email': row['email'], 'role': row['role']}


def _load_user(user_id):
    """Load user from database by ID."""
    if not user_id:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        return cursor.execute(
            'SELECT id, email, role FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()


def _clear_remember_token(token_cookie_value):
    """Delete a remember-me token from database."""
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
    """Clear session and remember-me token."""
    token_cookie = request.cookies.get(REMEMBER_COOKIE_NAME)
    _clear_remember_token(token_cookie)
    session.pop('user_id', None)


def _set_remember_cookie(response, token_value):
    """Set or delete remember-me cookie on response."""
    from flask import current_app
    if token_value:
        response.set_cookie(
            REMEMBER_COOKIE_NAME,
            token_value,
            max_age=REMEMBER_TOKEN_DAYS * 24 * 60 * 60,
            httponly=True,
            samesite='Lax',
            secure=current_app.config['SESSION_COOKIE_SECURE'],
            path='/'
        )
    else:
        response.delete_cookie(REMEMBER_COOKIE_NAME, path='/')
    return response


def attach_current_user():
    """Before-request handler to load current user from session or remember-me cookie."""
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


# ==================== ROUTES ====================

@auth.route('/login')
def login():
    """Render login page."""
    if getattr(g, 'current_user', None):
        return redirect(url_for('main.index'))
    next_url = request.args.get('next', url_for('main.index'))
    return render_template('login.html', next_url=next_url)


@auth.route('/logout', methods=['GET'])
def logout_page():
    """Handle logout via GET."""
    _logout_user()
    resp = redirect(url_for('auth.login'))
    _set_remember_cookie(resp, None)
    return resp


@auth.route('/api/auth/login', methods=['POST'])
def api_login():
    """API endpoint for login."""
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


@auth.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API endpoint for logout."""
    _logout_user()
    resp = jsonify({'message': 'Logged out'})
    _set_remember_cookie(resp, None)
    return resp


@auth.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    """Get current user info."""
    return jsonify({'user': _serialize_user(g.current_user)})


@auth.route('/api/auth/reset/request', methods=['POST'])
def api_reset_request():
    """Request password reset token."""
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


@auth.route('/api/auth/reset/confirm', methods=['POST'])
def api_reset_confirm():
    """Confirm password reset with token."""
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

@auth.route('/api/users', methods=['GET'])
@login_required
def list_users():
    """List all users (for sharing repertoires, etc)."""
    with get_db() as conn:
        cursor = conn.cursor()
        users = cursor.execute(
            'SELECT id, email, role FROM users ORDER BY email'
        ).fetchall()
        return jsonify([dict(id=u['id'], email=u['email'], role=u['role']) for u in users])


@auth.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    """Create new user (admin only)."""
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
            
            # Create Archive repertoire for new user
            cursor.execute(
                'INSERT INTO repertoires (name, date_created, user_id, sort_order) VALUES (?, ?, ?, ?)',
                ('Archive', now, user_id, 0)
            )
            
            return jsonify({'id': user_id, 'message': 'User created'})
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Email already exists'}), 400


@auth.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """Get user by ID (for displaying copy info, etc)."""
    with get_db() as conn:
        cursor = conn.cursor()
        user = cursor.execute(
            'SELECT id, email, role FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(dict(id=user['id'], email=user['email'], role=user['role']))


@auth.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update user (admin only)."""
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


@auth.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete user (admin only)."""
    if user_id == g.current_user['id']:
        return jsonify({'error': 'You cannot delete your own account'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        deleted = cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        if deleted.rowcount == 0:
            return jsonify({'error': 'User not found'}), 404
    return jsonify({'message': 'User deleted'})


@auth.route('/api/users/<int:user_id>/progress', methods=['GET'])
@admin_required
def user_progress(user_id):
    """Get user progress stats (admin only)."""
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
