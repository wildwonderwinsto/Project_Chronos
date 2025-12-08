from datetime import datetime
from supabase import Client


class DatabaseLogger:
    """Handles all database logging operations"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
    
    async def create_log(self, name: str, email: str):
        """
        Create initial database log entry with INITIATED status
        Returns: log_id or None if failed
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'INITIATED',
            'persona_name': name,
            'persona_email': email,
            'start_time': datetime.utcnow().isoformat()
        }
        
        try:
            response = self.supabase.table('attempt_logs').insert(log_entry).execute()
            log_id = response.data[0]['id']
            print(f"   Log ID: {log_id}")
            return log_id
        except Exception as e:
            print(f"❌ Failed to create log entry: {e}")
            return None
    
    async def log_success(self, log_id: str, reason: str):
        """Update database log with success status"""
        try:
            self.supabase.table('attempt_logs').update({
                'status': 'SUCCESS',
                'end_time': datetime.utcnow().isoformat(),
                'error_code': None,
                'error_message': reason
            }).eq('id', log_id).execute()
        except Exception as e:
            print(f"⚠️  Failed to update success log: {e}")
    
    async def log_failure(self, log_id: str, reason: str, screenshot_path: str):
        """Update database log with failure status"""
        try:
            self.supabase.table('attempt_logs').update({
                'status': 'FAILED',
                'end_time': datetime.utcnow().isoformat(),
                'error_code': reason.split(':')[0] if ':' in reason else reason,
                'error_message': reason,
                'screenshot_path': screenshot_path
            }).eq('id', log_id).execute()
        except Exception as e:
            print(f"⚠️  Failed to update failure log: {e}")