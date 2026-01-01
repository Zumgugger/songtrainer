"""
Songtrainer Flask Application - Modular Architecture
Main application factory and configuration
"""

from flask import Flask, session, g, request
from datetime import timedelta
import os
from database import (
    get_db,
    init_db,
    ensure_indexes_and_normalize,
    ensure_audio_path_column,
    ensure_drive_file_id_column,
    ensure_chart_path_column,
    ensure_repertoire_id_column,
    ensure_release_date_column,
    ensure_repertoire_sort_order_column,
    ensure_repertoire_folder_columns,
    ensure_performance_hints_column,
    ensure_sync_history_table,
    ensure_practice_targets_not_below_count,
    ensure_repertoire_notes_column,
    ensure_practice_date_log_table,
    ensure_duration_column,
    ensure_repertoire_copy_tracking_columns,
    ensure_users_table,
    ensure_remember_tokens_table,
    ensure_default_admin,
    ensure_repertoire_user_column,
    ensure_song_user_column,
    ensure_archive_repertoires,
    ensure_settings_table,
)

# Import blueprints
from blueprints.auth import auth, attach_current_user
from blueprints.main import main
from blueprints.songs import songs_bp
from blueprints.skills import skills
from blueprints.repertoires import repertoires_bp
from blueprints.settings import settings_bp


def create_app():
    """Application factory function."""
    
    # Create Flask app instance
    app = Flask(__name__)
    
    # ==================== CONFIGURATION ====================
    app.secret_key = os.getenv('SECRET_KEY', os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me'))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV', 'development') == 'production'
    app.permanent_session_lifetime = timedelta(hours=12)
    
    # ==================== INITIALIZATION ====================
    
    # Initialize database on first run
    if not os.path.exists('songs.db'):
        init_db()
    
    # Ensure all database constraints and columns exist
    _ensure_database_schema(app)
    
    # ==================== REGISTER BLUEPRINTS ====================
    app.register_blueprint(auth, url_prefix='')
    app.register_blueprint(main, url_prefix='')
    app.register_blueprint(songs_bp, url_prefix='')
    app.register_blueprint(skills, url_prefix='')
    app.register_blueprint(repertoires_bp, url_prefix='')
    app.register_blueprint(settings_bp, url_prefix='')
    
    # ==================== REQUEST HANDLERS ====================
    
    @app.before_request
    def before_request():
        """Load current user from session/remember-me token before each request."""
        attach_current_user()
    
    @app.teardown_appcontext
    def close_db(error):
        """Close database connection at end of request."""
        db = g.pop('db', None)
        if db is not None:
            db.close()
    
    return app


def _ensure_database_schema(app):
    """Ensure all database migrations and schema updates are applied."""
    
    with app.app_context():
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
            ensure_drive_file_id_column()
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
            ensure_performance_hints_column()
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
        
        try:
            ensure_practice_targets_not_below_count()
        except Exception:
            pass
        
        try:
            ensure_practice_date_log_table()
        except Exception:
            pass
        
        try:
            ensure_duration_column()
        except Exception:
            pass
        
        try:
            ensure_repertoire_copy_tracking_columns()
        except Exception:
            pass
        
        try:
            ensure_archive_repertoires()
        except Exception:
            pass

        try:
            ensure_settings_table()
        except Exception:
            pass


# Create app instance for direct execution
app = create_app()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
