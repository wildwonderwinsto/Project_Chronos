import os
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
import pytz

load_dotenv()

app = Flask(__name__)
CORS(app)

# Supabase setup
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TIMEZONE = pytz.timezone('America/New_York')

# Store for live logs (in-memory)
live_logs = []
MAX_LIVE_LOGS = 100


@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    try:
        # Get bot status
        status_result = supabase.table('bot_status').select('*').limit(1).execute()
        bot_status = status_result.data[0] if status_result.data else {}
        
        # Get total counts from attempt_logs
        logs = supabase.table('attempt_logs').select('status').execute()
        
        total_attempts = len(logs.data)
        successes = len([l for l in logs.data if l['status'] == 'SUCCESS'])
        failures = len([l for l in logs.data if l['status'] == 'FAILED'])
        
        success_rate = (successes / total_attempts * 100) if total_attempts > 0 else 0
        
        # Get recent activity (last 24 hours)
        yesterday = (datetime.now(TIMEZONE) - timedelta(days=1)).isoformat()
        recent = supabase.table('attempt_logs')\
            .select('*')\
            .gte('timestamp', yesterday)\
            .execute()
        
        recent_successes = len([l for l in recent.data if l['status'] == 'SUCCESS'])
        
        # Calculate entries per hour (last 24h)
        entries_per_hour = len(recent.data) / 24.0
        
        return jsonify({
            'bot_status': bot_status.get('status', 'UNKNOWN'),
            'current_mode': bot_status.get('current_mode', 'DAY'),
            'total_attempts': total_attempts,
            'total_successes': successes,
            'total_failures': failures,
            'success_rate': round(success_rate, 1),
            'consecutive_failures': bot_status.get('consecutive_failures', 0),
            'entries_last_24h': len(recent.data),
            'successes_last_24h': recent_successes,
            'entries_per_hour': round(entries_per_hour, 2),
            'target_frequency': bot_status.get('target_frequency', 0),
            'next_run_time': bot_status.get('next_run_time'),
            'last_attempt_time': bot_status.get('last_attempt_time')
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recent-logs')
def get_recent_logs():
    """Get recent attempt logs"""
    try:
        limit = 50  # Last 50 attempts
        
        logs = supabase.table('attempt_logs')\
            .select('*')\
            .order('timestamp', desc=True)\
            .limit(limit)\
            .execute()
        
        return jsonify({
            'logs': logs.data
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/hourly-chart')
def get_hourly_chart():
    """Get data for hourly activity chart (last 24 hours)"""
    try:
        yesterday = (datetime.now(TIMEZONE) - timedelta(days=1)).isoformat()
        
        logs = supabase.table('attempt_logs')\
            .select('timestamp, status')\
            .gte('timestamp', yesterday)\
            .order('timestamp', desc=False)\
            .execute()
        
        # Group by hour
        hourly_data = {}
        for log in logs.data:
            timestamp = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
            
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {'total': 0, 'success': 0, 'failed': 0}
            
            hourly_data[hour_key]['total'] += 1
            if log['status'] == 'SUCCESS':
                hourly_data[hour_key]['success'] += 1
            elif log['status'] == 'FAILED':
                hourly_data[hour_key]['failed'] += 1
        
        # Convert to array format for chart
        labels = sorted(hourly_data.keys())
        totals = [hourly_data[h]['total'] for h in labels]
        successes = [hourly_data[h]['success'] for h in labels]
        failures = [hourly_data[h]['failed'] for h in labels]
        
        return jsonify({
            'labels': labels,
            'totals': totals,
            'successes': successes,
            'failures': failures
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/proxy-stats')
def get_proxy_stats():
    """Get proxy usage statistics"""
    try:
        # Get logs with proxy info
        logs = supabase.table('attempt_logs')\
            .select('proxy_ip, proxy_city, proxy_state, status')\
            .not_.is_('proxy_ip', 'null')\
            .execute()
        
        # Count by IP
        proxy_usage = {}
        for log in logs.data:
            ip = log.get('proxy_ip', 'Unknown')
            if ip not in proxy_usage:
                proxy_usage[ip] = {
                    'ip': ip,
                    'city': log.get('proxy_city', 'Unknown'),
                    'state': log.get('proxy_state', 'Unknown'),
                    'total': 0,
                    'success': 0,
                    'failed': 0
                }
            
            proxy_usage[ip]['total'] += 1
            if log['status'] == 'SUCCESS':
                proxy_usage[ip]['success'] += 1
            elif log['status'] == 'FAILED':
                proxy_usage[ip]['failed'] += 1
        
        # Convert to list and sort by total
        proxy_list = sorted(proxy_usage.values(), key=lambda x: x['total'], reverse=True)
        
        return jsonify({
            'proxies': proxy_list[:20]  # Top 20
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-logs')
def search_logs():
    """Search logs with filters"""
    try:
        # Get query parameters
        status = request.args.get('status')  # SUCCESS, FAILED, INITIATED
        search = request.args.get('search')  # Name or email search
        limit = int(request.args.get('limit', 100))
        
        # Build query
        query = supabase.table('attempt_logs').select('*')
        
        if status:
            query = query.eq('status', status)
        
        if search:
            # Search in name or email
            query = query.or_(f'persona_name.ilike.%{search}%,persona_email.ilike.%{search}%')
        
        result = query.order('timestamp', desc=True).limit(limit).execute()
        
        return jsonify({
            'logs': result.data,
            'count': len(result.data)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear-database', methods=['POST'])
def clear_database():
    """Clear all attempt logs and reset counters"""
    try:
        # Get password from request
        data = request.get_json()
        password = data.get('password')
        
        # Simple password check (change this!)
        if password != os.getenv('ADMIN_PASSWORD', 'chronos2025'):
            return jsonify({'error': 'Invalid password'}), 403
        
        # Delete all attempt logs
        supabase.table('attempt_logs').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        
        # Reset bot status
        supabase.table('bot_status').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('bot_status').insert({
            'status': 'PAUSED',
            'current_mode': 'DAY',
            'total_attempts': 0,
            'total_successes': 0,
            'total_failures': 0,
            'consecutive_failures': 0
        }).execute()
        
        return jsonify({
            'success': True,
            'message': 'Database cleared successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/live-logs')
def get_live_logs():
    """Get live terminal-style logs"""
    return jsonify({
        'logs': live_logs[-100:]  # Last 100 log lines
    })


@app.route('/api/add-log', methods=['POST'])
def add_live_log():
    """Add a log entry (called by bot)"""
    try:
        data = request.get_json()
        log_entry = {
            'timestamp': datetime.now(TIMEZONE).isoformat(),
            'message': data.get('message', ''),
            'level': data.get('level', 'INFO')  # INFO, WARNING, ERROR, SUCCESS
        }
        
        live_logs.append(log_entry)
        
        # Keep only last MAX_LIVE_LOGS entries
        if len(live_logs) > MAX_LIVE_LOGS:
            live_logs.pop(0)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Production WSGI server
    try:
        from waitress import serve
        port = int(os.getenv('PORT', 8080))
        print(f"🚀 Starting production server on port {port}")
        serve(app, host='0.0.0.0', port=port)
    except ImportError:
        # Fallback to development server
        print("⚠️  Waitress not installed, using development server")
        print("   Install with: pip install waitress")
        port = int(os.getenv('PORT', 8080))
        app.run(host='0.0.0.0', port=port, debug=True)