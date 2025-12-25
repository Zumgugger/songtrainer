"""Settings blueprint to manage admin-configurable application settings."""

from flask import Blueprint, request, jsonify
from database import get_db
from utils.decorators import admin_required, login_required

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/api/settings/difficulty-thresholds', methods=['GET'])
@admin_required
def get_difficulty_thresholds():
    """Return the practice auto-bump thresholds (days) per difficulty."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            'SELECT key, value FROM settings WHERE key IN (?, ?, ?)',
            ('threshold_easy_days', 'threshold_normal_days', 'threshold_hard_days')
        ).fetchall()
        m = {r['key']: int(r['value']) for r in rows}
        return jsonify({
            'easy': m.get('threshold_easy_days', 90),
            'normal': m.get('threshold_normal_days', 60),
            'hard': m.get('threshold_hard_days', 30),
        })


@settings_bp.route('/api/settings/difficulty-thresholds', methods=['PUT'])
@admin_required
def update_difficulty_thresholds():
    """Update the practice auto-bump thresholds (days) per difficulty."""
    data = request.json or {}

    def _sanitize(v, default):
        try:
            iv = int(v)
            if iv < 0 or iv > 10000:
                return default
            return iv
        except Exception:
            return default

    easy = _sanitize(data.get('easy'), 90)
    normal = _sanitize(data.get('normal'), 60)
    hard = _sanitize(data.get('hard'), 30)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('threshold_easy_days', str(easy)))
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('threshold_normal_days', str(normal)))
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('threshold_hard_days', str(hard)))
        return jsonify({'message': 'Thresholds updated', 'easy': easy, 'normal': normal, 'hard': hard})
