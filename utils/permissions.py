"""Permission and scope resolution utilities."""

from flask import g, abort


def resolve_scope_user_id(get_db, requested_user_id):
    """
    Admin can request another user_id; others stay on their own.
    Returns the effective user_id for the request.
    """
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


def require_repertoire(cursor, repertoire_id, scope_user_id=None):
    """
    Fetch repertoire and verify access permissions.
    Raises 404 if not found, 403 if not authorized.
    Returns the repertoire row.
    """
    scope = scope_user_id or (g.current_user['id'] if g.current_user else None)
    rep = cursor.execute('SELECT * FROM repertoires WHERE id = ?', (repertoire_id,)).fetchone()
    if not rep:
        abort(404)
    if g.current_user['role'] != 'admin' and rep['user_id'] != scope:
        abort(403)
    return rep


def require_song(cursor, song_id, scope_user_id=None):
    """
    Fetch song and verify access permissions.
    Raises 404 if not found, 403 if not authorized.
    Returns the song row.
    """
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
