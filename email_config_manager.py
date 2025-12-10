# =============================================================================
# EMAIL CONFIGURATION MANAGER - Supabase Edition
# Store master emails in Supabase so you can update them without redeploying
# =============================================================================

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

class EmailConfigManager:
    """Manages master email configuration stored in Supabase"""
    
    def __init__(self):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self._cache = None
        self._cache_timestamp = None
    
    def get_master_emails(self, use_cache=True):
        """
        Get master emails from Supabase
        Returns: dict like {"outlook.com": "UsersMaiI", "gmail.com": "myemail"}
        """
        # Cache for 60 seconds to avoid hammering database
        import time
        if use_cache and self._cache and self._cache_timestamp:
            if time.time() - self._cache_timestamp < 60:
                return self._cache
        
        try:
            # Fetch all active email configs
            result = self.supabase.table('email_config')\
                .select('*')\
                .eq('is_active', True)\
                .execute()
            
            # Convert to dict format
            emails = {}
            for row in result.data:
                emails[row['domain']] = row['email_account']
            
            # Update cache
            self._cache = emails
            self._cache_timestamp = time.time()
            
            return emails
            
        except Exception as e:
            print(f"⚠️  Failed to load email config from Supabase: {e}")
            # Fallback to hardcoded default
            return {"outlook.com": "UsersMaiI"}
    
    def add_email(self, domain: str, email_account: str):
        """Add a new master email configuration"""
        try:
            self.supabase.table('email_config').insert({
                'domain': domain,
                'email_account': email_account,
                'is_active': True
            }).execute()
            
            # Clear cache
            self._cache = None
            
            print(f"✅ Added: {email_account}@{domain}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to add email: {e}")
            return False
    
    def toggle_email(self, domain: str, active: bool):
        """Enable or disable an email"""
        try:
            self.supabase.table('email_config')\
                .update({'is_active': active})\
                .eq('domain', domain)\
                .execute()
            
            # Clear cache
            self._cache = None
            
            status = "enabled" if active else "disabled"
            print(f"✅ {domain} {status}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to toggle email: {e}")
            return False
    
    def delete_email(self, domain: str):
        """Delete an email configuration"""
        try:
            self.supabase.table('email_config')\
                .delete()\
                .eq('domain', domain)\
                .execute()
            
            # Clear cache
            self._cache = None
            
            print(f"✅ Deleted: {domain}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to delete email: {e}")
            return False
    
    def list_emails(self):
        """List all email configurations"""
        try:
            result = self.supabase.table('email_config')\
                .select('*')\
                .order('domain')\
                .execute()
            
            return result.data
            
        except Exception as e:
            print(f"❌ Failed to list emails: {e}")
            return []


# =============================================================================
# TEST SCRIPT
# =============================================================================

def test_email_config():
    """Test the email configuration system"""
    
    manager = EmailConfigManager()
    
    print("\n" + "="*70)
    print("🧪 TESTING EMAIL CONFIGURATION MANAGER")
    print("="*70)
    
    # Test 1: List current emails
    print("\n📋 Current Email Configurations:")
    print("-"*70)
    emails = manager.list_emails()
    if emails:
        for email in emails:
            status = "✅ Active" if email['is_active'] else "❌ Disabled"
            print(f"   {email['email_account']}@{email['domain']} - {status}")
    else:
        print("   (None configured yet)")
    
    # Test 2: Get active emails (what the bot uses)
    print("\n🤖 Active Emails (Used by Bot):")
    print("-"*70)
    active = manager.get_master_emails()
    for domain, account in active.items():
        print(f"   {account}@{domain}")
    
    print("\n" + "="*70)
    print("✅ Test complete!")
    print("="*70)


if __name__ == "__main__":
    test_email_config()