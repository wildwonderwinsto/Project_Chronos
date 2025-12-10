import os
import sys
import threading
import asyncio
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
import pytz

# IMPORT YOUR SCHEDULER
from scheduler_engine import ChronoScheduler
from email_config_manager import EmailConfigManager

load_dotenv()

app = Flask(__name__)
CORS(app)

# Supabase setup
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TIMEZONE = pytz.timezone('America/New_York')

# Email manager
email_manager = EmailConfigManager()

# ==========================================
# 🔌 LOGGING INTERCEPTOR (The Magic Part)
# ==========================================
live_logs = []
MAX_LIVE_LOGS = 100

class LoggerInterceptor(io.StringIO):
    """
    Catches all 'print' statements.
    1. Sends them to the Render Console (so you see them in Deployment logs).
    2. Saves them to 'live_logs' (so you see them in Dashboard).
    """
    def write(self, message):
        # 1. Write to standard Render console
        sys.__stdout__.write(message)
        sys.__stdout__.flush()
        
        # 2. Add to Dashboard list (ignore empty newlines)
        if message and message.strip():
            current_time = datetime.now(TIMEZONE).isoformat()
            
            # Determine log level based on content
            level = 'INFO'
            if '❌' in message or 'ERROR' in message or 'Exception' in message:
                level = 'ERROR'
            elif '⚠️' in message or 'WARNING' in message:
                level = 'WARNING'
            elif '✅' in message or 'SUCCESS' in message:
                level = 'SUCCESS'
            
            log_entry = {
                'timestamp': current_time,
                'message': message.strip(),
                'level': level
            }
            
            live_logs.append(log_entry)
            
            # Keep list size manageable
            if len(live_logs) > MAX_LIVE_LOGS:
                live_logs.pop(0)

    def flush(self):
        sys.__stdout__.flush()

# Redirect Python's "print" to our Interceptor
sys.stdout = LoggerInterceptor()

# ==========================================
# 🤖 SCHEDULER BACKGROUND WORKER
# ==========================================
scheduler_started = False

def run_scheduler_loop():
    """Function to run the async scheduler in a separate thread"""
    print(f"🚀 Background Scheduler Thread Started at {datetime.now(TIMEZONE)}")
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initialize Scheduler
    scheduler = ChronoScheduler(use_proxies=True, manual_captcha=False)
    
    # Run it
    try:
        loop.run_until_complete(scheduler.run())
    except Exception as e:
        print(f"❌ Scheduler Thread Crashed: {e}")

def start_background_worker():
    """Starts the scheduler thread"""
    global scheduler_started
    if not scheduler_started:
        scheduler_started = True
        thread = threading.Thread(target=run_scheduler_loop, daemon=True)
        thread.start()

# ==========================================
# 🌐 FLASK ROUTES - PAGES
# ==========================================

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

# ==========================================
# 🌐 FLASK ROUTES - API
# ==========================================

@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    try:
        # Get bot status
        status_result = supabase.table('bot_status').select('*').limit(1).execute()
        bot_status = status_result.data[0] if status_result.data else {}
        
        # Get total counts from attempt_logs
        logs = supabase.table('attempt_logs').select('status', count='exact').execute()
        
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
        print(f"⚠️ Stats Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-logs')
def get_recent_logs():
    """Get recent attempt logs from DB"""
    try:
        logs = supabase.table('attempt_logs')\
            .select('*')\
            .order('timestamp', desc=True)\
            .limit(50)\
            .execute()
        return jsonify({'logs': logs.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/hourly-chart')
def get_hourly_chart():
    """Get data for chart"""
    try:
        yesterday = (datetime.now(TIMEZONE) - timedelta(days=1)).isoformat()
        logs = supabase.table('attempt_logs')\
            .select('timestamp, status')\
            .gte('timestamp', yesterday)\
            .order('timestamp', desc=False)\
            .execute()
        
        hourly_data = {}
        for log in logs.data:
            ts_str = log['timestamp'].replace('Z', '+00:00')
            timestamp = datetime.fromisoformat(ts_str)
            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
            
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {'total': 0, 'success': 0, 'failed': 0}
            
            hourly_data[hour_key]['total'] += 1
            if log['status'] == 'SUCCESS':
                hourly_data[hour_key]['success'] += 1
            elif log['status'] == 'FAILED':
                hourly_data[hour_key]['failed'] += 1
        
        labels = sorted(hourly_data.keys())
        totals = [hourly_data[h]['total'] for h in labels]
        successes = [hourly_data[h]['success'] for h in labels]
        failures = [hourly_data[h]['failed'] for h in labels]
        
        return jsonify({'labels': labels, 'totals': totals, 'successes': successes, 'failures': failures})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proxy-stats')
def get_proxy_stats():
    """Get proxy usage"""
    try:
        logs = supabase.table('attempt_logs')\
            .select('proxy_ip, proxy_city, proxy_state, status')\
            .not_.is_('proxy_ip', 'null')\
            .execute()
        
        proxy_usage = {}
        for log in logs.data:
            ip = log.get('proxy_ip', 'Unknown')
            if ip not in proxy_usage:
                proxy_usage[ip] = {
                    'ip': ip, 
                    'city': log.get('proxy_city', 'Unknown'), 
                    'state': log.get('proxy_state', 'Unknown'),
                    'total': 0, 'success': 0, 'failed': 0
                }
            proxy_usage[ip]['total'] += 1
            if log['status'] == 'SUCCESS': proxy_usage[ip]['success'] += 1
            elif log['status'] == 'FAILED': proxy_usage[ip]['failed'] += 1
        
        return jsonify({'proxies': sorted(proxy_usage.values(), key=lambda x: x['total'], reverse=True)[:20]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-logs')
def search_logs():
    """Search logs"""
    try:
        status = request.args.get('status')
        search = request.args.get('search')
        limit = int(request.args.get('limit', 100))
        query = supabase.table('attempt_logs').select('*')
        if status: query = query.eq('status', status)
        if search: query = query.or_(f'persona_name.ilike.%{search}%,persona_email.ilike.%{search}%')
        result = query.order('timestamp', desc=True).limit(limit).execute()
        return jsonify({'logs': result.data, 'count': len(result.data)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live-logs')
def get_live_logs():
    """Get live terminal logs (intercepted from stdout)"""
    return jsonify({'logs': live_logs[-100:]})

@app.route('/api/clear-database', methods=['POST'])
def clear_database():
    """Clear all database records"""
    try:
        data = request.get_json()
        password = data.get('password')
        if password != os.getenv('ADMIN_PASSWORD', 'chronos2025'):
            return jsonify({'error': 'Invalid password'}), 403
        
        supabase.table('attempt_logs').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('bot_status').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        supabase.table('bot_status').insert({
            'status': 'PAUSED', 'current_mode': 'DAY',
            'total_attempts': 0, 'total_successes': 0, 'total_failures': 0, 'consecutive_failures': 0
        }).execute()
        
        print("⚠️ DATABASE CLEARED BY ADMIN")
        return jsonify({'success': True, 'message': 'Database cleared successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# 📧 EMAIL CONFIGURATION API
# ==========================================

@app.route('/api/emails')
def get_emails():
    """Get all email configurations"""
    try:
        emails = email_manager.list_emails()
        return jsonify({'emails': emails})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/add', methods=['POST'])
def add_email():
    """Add a new master email"""
    try:
        data = request.get_json()
        password = data.get('password')
        domain = data.get('domain')
        email_account = data.get('email_account')
        
        if password != os.getenv('ADMIN_PASSWORD', 'chronos2025'):
            return jsonify({'error': 'Invalid password'}), 403
        
        if not domain or not email_account:
            return jsonify({'error': 'Domain and email account are required'}), 400
        
        success = email_manager.add_email(domain, email_account)
        
        if success:
            return jsonify({'success': True, 'message': f'Added {email_account}@{domain}'})
        else:
            return jsonify({'error': 'Failed to add email'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/toggle', methods=['POST'])
def toggle_email():
    """Enable or disable an email"""
    try:
        data = request.get_json()
        password = data.get('password')
        domain = data.get('domain')
        active = data.get('active', True)
        
        if password != os.getenv('ADMIN_PASSWORD', 'chronos2025'):
            return jsonify({'error': 'Invalid password'}), 403
        
        if not domain:
            return jsonify({'error': 'Domain is required'}), 400
        
        success = email_manager.toggle_email(domain, active)
        
        if success:
            status = "enabled" if active else "disabled"
            return jsonify({'success': True, 'message': f'{domain} {status}'})
        else:
            return jsonify({'error': 'Failed to toggle email'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/delete', methods=['POST'])
def delete_email():
    """Delete an email configuration"""
    try:
        data = request.get_json()
        password = data.get('password')
        domain = data.get('domain')
        
        if password != os.getenv('ADMIN_PASSWORD', 'chronos2025'):
            return jsonify({'error': 'Invalid password'}), 403
        
        if not domain:
            return jsonify({'error': 'Domain is required'}), 400
        
        success = email_manager.delete_email(domain)
        
        if success:
            return jsonify({'success': True, 'message': f'Deleted {domain}'})
        else:
            return jsonify({'error': 'Failed to delete email'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/current')
def get_current_emails():
    """Get currently active email accounts being used"""
    try:
        active_emails = email_manager.get_master_emails()
        return jsonify({'active_emails': active_emails})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# 📸 SCREENSHOT & CAPTCHA IMAGE VIEWER
# ==========================================

@app.route('/api/screenshots')
def list_screenshots():
    """List all available screenshots"""
    try:
        import os
        screenshots = []
        
        if os.path.exists('screenshots'):
            for filename in sorted(os.listdir('screenshots'), reverse=True)[:50]:
                if filename.endswith('.png'):
                    log_id = filename.replace('.png', '')
                    screenshots.append({
                        'log_id': log_id,
                        'filename': filename,
                        'url': f'/screenshots/{filename}'
                    })
        
        return jsonify({'screenshots': screenshots})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/captcha-images')
def list_captcha_images():
    """List all CAPTCHA images"""
    try:
        import os
        captcha_images = {}
        
        if os.path.exists('captcha_images'):
            for filename in sorted(os.listdir('captcha_images'), reverse=True):
                if filename.endswith('.png'):
                    # Parse filename: log_id_attempt1_original.png
                    parts = filename.replace('.png', '').split('_')
                    if len(parts) >= 2:
                        log_id = parts[0]
                        
                        if log_id not in captcha_images:
                            captcha_images[log_id] = []
                        
                        captcha_images[log_id].append({
                            'filename': filename,
                            'url': f'/captcha-images/{filename}',
                            'type': 'preprocessed' if 'preprocessed' in filename or any(s in filename for s in ['high_contrast', 'ultra_sharp', 'denoised', 'inverted', 'adaptive']) else 'original'
                        })
        
        return jsonify({'captcha_images': captcha_images})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve static files from screenshots and captcha_images directories
@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    """Serve screenshot files"""
    return send_from_directory('screenshots', filename)

@app.route('/captcha-images/<path:filename>')
def serve_captcha_image(filename):
    """Serve CAPTCHA image files"""
    return send_from_directory('captcha_images', filename)

# ==========================================
# 🚀 STARTUP
# ==========================================

if __name__ == '__main__':
    # START THE SCHEDULER
    start_background_worker()
    
    # Production WSGI server
    try:
        from waitress import serve
        port = int(os.getenv('PORT', 8080))
        print(f"🚀 Starting production server on port {port}")
        serve(app, host='0.0.0.0', port=port)
    except ImportError:
        print("⚠️  Waitress not installed, using development server")
        port = int(os.getenv('PORT', 8080))
        app.run(host='0.0.0.0', port=port, debug=True)