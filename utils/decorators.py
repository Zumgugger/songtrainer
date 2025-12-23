"""Authentication and authorization decorators."""

from functools import wraps
from flask import request, jsonify, redirect, url_for, g, abort


def login_required(fn):
    """Decorator to require authenticated user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(g, 'current_user', None):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """Decorator to require admin role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = getattr(g, 'current_user', None)
        if not user:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login', next=request.path))
        if user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper
