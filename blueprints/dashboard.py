"""Dashboard API Blueprint - Statistics and Progress Tracking"""

from flask import Blueprint, request, jsonify, g
from database import get_db
from utils.decorators import login_required
from utils.permissions import resolve_scope_user_id
from datetime import datetime, timedelta
from collections import defaultdict

dashboard_bp = Blueprint('dashboard', __name__)


def _get_date_range(period):
    """Get start date based on period (week, month, year, all)."""
    today = datetime.now().date()
    if period == 'week':
        start = today - timedelta(days=7)
    elif period == 'month':
        start = today - timedelta(days=30)
    elif period == 'year':
        start = today - timedelta(days=365)
    else:  # 'all'
        start = datetime(2000, 1, 1).date()
    return start.isoformat(), today.isoformat()


@dashboard_bp.route('/api/dashboard/summary', methods=['GET'])
@login_required
def get_summary():
    """Get overall dashboard summary statistics."""
    period = request.args.get('period', 'all')
    repertoire_id = request.args.get('repertoire_id', type=int)
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)
    
    start_date, end_date = _get_date_range(period)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Base conditions for repertoire filtering
        rep_condition = "AND s.repertoire_id = ?" if repertoire_id else ""
        rep_params = [repertoire_id] if repertoire_id else []
        
        # Total practice time (in seconds)
        if repertoire_id:
            time_query = '''
                SELECT COALESCE(SUM(s.duration * pl.practice_count), 0) as total_seconds
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                AND pl.practice_date <= ?
                AND s.repertoire_id = ?
                AND s.duration IS NOT NULL
            '''
            time_result = cursor.execute(time_query, (scope_user_id, start_date, end_date, repertoire_id)).fetchone()
        else:
            time_query = '''
                SELECT COALESCE(SUM(s.duration * pl.practice_count), 0) as total_seconds
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                AND pl.practice_date <= ?
                AND s.duration IS NOT NULL
            '''
            time_result = cursor.execute(time_query, (scope_user_id, start_date, end_date)).fetchone()
        
        total_seconds = time_result['total_seconds'] or 0
        
        # Count distinct songs practiced
        if repertoire_id:
            songs_query = '''
                SELECT COUNT(DISTINCT pl.song_id) as count
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                AND pl.practice_date <= ?
                AND s.repertoire_id = ?
            '''
            songs_practiced = cursor.execute(songs_query, (scope_user_id, start_date, end_date, repertoire_id)).fetchone()['count']
        else:
            songs_query = '''
                SELECT COUNT(DISTINCT song_id) as count
                FROM practice_date_log
                WHERE user_id = ?
                AND practice_date >= ?
                AND practice_date <= ?
            '''
            songs_practiced = cursor.execute(songs_query, (scope_user_id, start_date, end_date)).fetchone()['count']
        
        # Total practice sessions (sum of practice_count entries)
        if repertoire_id:
            sessions_query = '''
                SELECT COALESCE(SUM(pl.practice_count), 0) as count
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                AND pl.practice_date <= ?
                AND s.repertoire_id = ?
            '''
            practice_sessions = cursor.execute(sessions_query, (scope_user_id, start_date, end_date, repertoire_id)).fetchone()['count']
        else:
            sessions_query = '''
                SELECT COALESCE(SUM(practice_count), 0) as count
                FROM practice_date_log
                WHERE user_id = ?
                AND practice_date >= ?
                AND practice_date <= ?
            '''
            practice_sessions = cursor.execute(sessions_query, (scope_user_id, start_date, end_date)).fetchone()['count']
        
        # Skills mastered (current total, not time-bound)
        if repertoire_id:
            skills_query = '''
                SELECT COUNT(*) as mastered
                FROM song_skills ss
                JOIN songs s ON ss.song_id = s.id
                WHERE s.user_id = ?
                AND ss.is_mastered = 1
                AND s.repertoire_id = ?
            '''
            skills_mastered = cursor.execute(skills_query, (scope_user_id, repertoire_id)).fetchone()['mastered']
            
            total_skills_query = '''
                SELECT COUNT(*) as total
                FROM song_skills ss
                JOIN songs s ON ss.song_id = s.id
                WHERE s.user_id = ?
                AND s.repertoire_id = ?
            '''
            total_skills = cursor.execute(total_skills_query, (scope_user_id, repertoire_id)).fetchone()['total']
        else:
            skills_query = '''
                SELECT COUNT(*) as mastered
                FROM song_skills ss
                JOIN songs s ON ss.song_id = s.id
                WHERE s.user_id = ?
                AND ss.is_mastered = 1
            '''
            skills_mastered = cursor.execute(skills_query, (scope_user_id,)).fetchone()['mastered']
            
            total_skills_query = '''
                SELECT COUNT(*) as total
                FROM song_skills ss
                JOIN songs s ON ss.song_id = s.id
                WHERE s.user_id = ?
            '''
            total_skills = cursor.execute(total_skills_query, (scope_user_id,)).fetchone()['total']
        
        # Songs completed (practice_count >= practice_target and target > 0)
        if repertoire_id:
            completed_query = '''
                SELECT COUNT(*) as completed
                FROM songs
                WHERE user_id = ?
                AND practice_target > 0
                AND practice_count >= practice_target
                AND repertoire_id = ?
            '''
            songs_completed = cursor.execute(completed_query, (scope_user_id, repertoire_id)).fetchone()['completed']
            
            total_songs_query = '''
                SELECT COUNT(*) as total FROM songs WHERE user_id = ? AND repertoire_id = ?
            '''
            total_songs = cursor.execute(total_songs_query, (scope_user_id, repertoire_id)).fetchone()['total']
        else:
            completed_query = '''
                SELECT COUNT(*) as completed
                FROM songs
                WHERE user_id = ?
                AND practice_target > 0
                AND practice_count >= practice_target
            '''
            songs_completed = cursor.execute(completed_query, (scope_user_id,)).fetchone()['completed']
            
            total_songs_query = 'SELECT COUNT(*) as total FROM songs WHERE user_id = ?'
            total_songs = cursor.execute(total_songs_query, (scope_user_id,)).fetchone()['total']
        
        # Format time
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        time_formatted = f"{hours}h {minutes}m"
        
        return jsonify({
            'practice_time': {
                'seconds': total_seconds,
                'hours': hours,
                'minutes': minutes,
                'formatted': time_formatted
            },
            'songs_practiced': songs_practiced,
            'practice_sessions': practice_sessions,
            'skills': {
                'mastered': skills_mastered,
                'total': total_skills,
                'percentage': round(skills_mastered / total_skills * 100, 1) if total_skills > 0 else 0
            },
            'songs': {
                'completed': songs_completed,
                'total': total_songs,
                'percentage': round(songs_completed / total_songs * 100, 1) if total_songs > 0 else 0
            },
            'period': period,
            'start_date': start_date,
            'end_date': end_date
        })


@dashboard_bp.route('/api/dashboard/streaks', methods=['GET'])
@login_required
def get_streaks():
    """Get practice streak information."""
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get all distinct practice dates for user, ordered
        dates_query = '''
            SELECT DISTINCT practice_date
            FROM practice_date_log
            WHERE user_id = ?
            ORDER BY practice_date DESC
        '''
        rows = cursor.execute(dates_query, (scope_user_id,)).fetchall()
        practice_dates = [datetime.strptime(r['practice_date'], '%Y-%m-%d').date() for r in rows]
        
        if not practice_dates:
            return jsonify({
                'current_streak': 0,
                'longest_streak': 0,
                'last_practice_date': None,
                'practiced_today': False
            })
        
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # Check if practiced today
        practiced_today = practice_dates[0] == today if practice_dates else False
        
        # Calculate current streak
        current_streak = 0
        check_date = today if practiced_today else yesterday
        
        for pd in practice_dates:
            if pd == check_date:
                current_streak += 1
                check_date -= timedelta(days=1)
            elif pd < check_date:
                break
        
        # If didn't practice today or yesterday, streak is 0
        if not practiced_today and (not practice_dates or practice_dates[0] < yesterday):
            current_streak = 0
        
        # Calculate longest streak
        longest_streak = 0
        streak = 0
        prev_date = None
        
        for pd in sorted(practice_dates):
            if prev_date is None or pd == prev_date + timedelta(days=1):
                streak += 1
            else:
                longest_streak = max(longest_streak, streak)
                streak = 1
            prev_date = pd
        longest_streak = max(longest_streak, streak)
        
        return jsonify({
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'last_practice_date': practice_dates[0].isoformat() if practice_dates else None,
            'practiced_today': practiced_today
        })


@dashboard_bp.route('/api/dashboard/activity', methods=['GET'])
@login_required
def get_activity():
    """Get activity heatmap data (practice time per day)."""
    weeks = request.args.get('weeks', 12, type=int)
    repertoire_id = request.args.get('repertoire_id', type=int)
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)
    
    # Calculate date range
    today = datetime.now().date()
    start_date = today - timedelta(days=weeks * 7)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get practice data per day
        if repertoire_id:
            query = '''
                SELECT pl.practice_date, 
                       SUM(COALESCE(s.duration, 180) * pl.practice_count) as total_seconds,
                       SUM(pl.practice_count) as session_count
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                AND s.repertoire_id = ?
                GROUP BY pl.practice_date
                ORDER BY pl.practice_date
            '''
            rows = cursor.execute(query, (scope_user_id, start_date.isoformat(), repertoire_id)).fetchall()
        else:
            query = '''
                SELECT pl.practice_date, 
                       SUM(COALESCE(s.duration, 180) * pl.practice_count) as total_seconds,
                       SUM(pl.practice_count) as session_count
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                GROUP BY pl.practice_date
                ORDER BY pl.practice_date
            '''
            rows = cursor.execute(query, (scope_user_id, start_date.isoformat())).fetchall()
        
        # Build activity map
        activity = {}
        max_seconds = 0
        for row in rows:
            activity[row['practice_date']] = {
                'seconds': row['total_seconds'],
                'sessions': row['session_count']
            }
            max_seconds = max(max_seconds, row['total_seconds'])
        
        # Generate all dates in range
        all_dates = []
        current = start_date
        while current <= today:
            date_str = current.isoformat()
            data = activity.get(date_str, {'seconds': 0, 'sessions': 0})
            # Calculate intensity level (0-4)
            if data['seconds'] == 0:
                level = 0
            elif max_seconds > 0:
                ratio = data['seconds'] / max_seconds
                if ratio < 0.25:
                    level = 1
                elif ratio < 0.5:
                    level = 2
                elif ratio < 0.75:
                    level = 3
                else:
                    level = 4
            else:
                level = 0
            
            all_dates.append({
                'date': date_str,
                'seconds': data['seconds'],
                'sessions': data['sessions'],
                'level': level
            })
            current += timedelta(days=1)
        
        return jsonify({
            'activity': all_dates,
            'max_seconds': max_seconds,
            'start_date': start_date.isoformat(),
            'end_date': today.isoformat()
        })


@dashboard_bp.route('/api/dashboard/trends', methods=['GET'])
@login_required
def get_trends():
    """Get progress trends over time for charts."""
    period = request.args.get('period', 'month')  # week, month, year
    repertoire_id = request.args.get('repertoire_id', type=int)
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)
    
    today = datetime.now().date()
    
    if period == 'week':
        start_date = today - timedelta(days=7)
        group_format = '%Y-%m-%d'  # Daily
    elif period == 'month':
        start_date = today - timedelta(days=30)
        group_format = '%Y-%m-%d'  # Daily
    else:  # year
        start_date = today - timedelta(days=365)
        group_format = '%Y-%W'  # Weekly
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Practice time trends
        if repertoire_id:
            time_query = '''
                SELECT pl.practice_date,
                       SUM(COALESCE(s.duration, 180) * pl.practice_count) as total_seconds
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                AND s.repertoire_id = ?
                GROUP BY pl.practice_date
                ORDER BY pl.practice_date
            '''
            time_rows = cursor.execute(time_query, (scope_user_id, start_date.isoformat(), repertoire_id)).fetchall()
        else:
            time_query = '''
                SELECT pl.practice_date,
                       SUM(COALESCE(s.duration, 180) * pl.practice_count) as total_seconds
                FROM practice_date_log pl
                JOIN songs s ON pl.song_id = s.id
                WHERE pl.user_id = ?
                AND pl.practice_date >= ?
                GROUP BY pl.practice_date
                ORDER BY pl.practice_date
            '''
            time_rows = cursor.execute(time_query, (scope_user_id, start_date.isoformat())).fetchall()
        
        # Aggregate by period if yearly
        if period == 'year':
            weekly_data = defaultdict(int)
            for row in time_rows:
                dt = datetime.strptime(row['practice_date'], '%Y-%m-%d')
                week_key = dt.strftime('%Y-%W')
                weekly_data[week_key] += row['total_seconds']
            
            practice_time_data = [{'date': k, 'seconds': v} for k, v in sorted(weekly_data.items())]
        else:
            practice_time_data = [{'date': r['practice_date'], 'seconds': r['total_seconds']} for r in time_rows]
        
        # Cumulative progress calculation (songs completed over time based on last_practiced)
        if repertoire_id:
            progress_query = '''
                SELECT last_practiced, COUNT(*) as completed_count
                FROM songs
                WHERE user_id = ?
                AND practice_target > 0
                AND practice_count >= practice_target
                AND last_practiced IS NOT NULL
                AND repertoire_id = ?
                GROUP BY DATE(last_practiced)
                ORDER BY last_practiced
            '''
            progress_rows = cursor.execute(progress_query, (scope_user_id, repertoire_id)).fetchall()
        else:
            progress_query = '''
                SELECT last_practiced, COUNT(*) as completed_count
                FROM songs
                WHERE user_id = ?
                AND practice_target > 0
                AND practice_count >= practice_target
                AND last_practiced IS NOT NULL
                GROUP BY DATE(last_practiced)
                ORDER BY last_practiced
            '''
            progress_rows = cursor.execute(progress_query, (scope_user_id,)).fetchall()
        
        # Build cumulative progress
        cumulative = 0
        progress_data = []
        for row in progress_rows:
            if row['last_practiced']:
                date_part = row['last_practiced'][:10]  # Get just the date part
                cumulative += row['completed_count']
                progress_data.append({'date': date_part, 'completed': cumulative})
        
        return jsonify({
            'practice_time': practice_time_data,
            'progress': progress_data,
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': today.isoformat()
        })


@dashboard_bp.route('/api/dashboard/repertoire-breakdown', methods=['GET'])
@login_required
def get_repertoire_breakdown():
    """Get practice time breakdown by repertoire."""
    period = request.args.get('period', 'month')
    requested_user_id = request.args.get('user_id', type=int)
    scope_user_id = resolve_scope_user_id(get_db, requested_user_id)
    
    start_date, end_date = _get_date_range(period)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT r.id, r.name,
                   COALESCE(SUM(COALESCE(s.duration, 180) * pl.practice_count), 0) as total_seconds,
                   COUNT(DISTINCT pl.song_id) as songs_practiced,
                   COALESCE(SUM(pl.practice_count), 0) as sessions
            FROM repertoires r
            LEFT JOIN songs s ON s.repertoire_id = r.id AND s.user_id = ?
            LEFT JOIN practice_date_log pl ON pl.song_id = s.id 
                AND pl.user_id = ?
                AND pl.practice_date >= ?
                AND pl.practice_date <= ?
            WHERE r.user_id = ?
            GROUP BY r.id, r.name
            ORDER BY total_seconds DESC
        '''
        rows = cursor.execute(query, (scope_user_id, scope_user_id, start_date, end_date, scope_user_id)).fetchall()
        
        breakdown = []
        for row in rows:
            seconds = row['total_seconds'] or 0
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            breakdown.append({
                'id': row['id'],
                'name': row['name'],
                'seconds': seconds,
                'formatted': f"{hours}h {minutes}m",
                'songs_practiced': row['songs_practiced'] or 0,
                'sessions': row['sessions'] or 0
            })
        
        return jsonify({
            'breakdown': breakdown,
            'period': period
        })
