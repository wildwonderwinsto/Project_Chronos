import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

def test_supabase_connection():
    """Test that we can write to Supabase securely"""
    try:
        # Initialize client (NO PROXY PARAMETER)
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test write
        test_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'INITIATED',
            'persona_name': 'Test User',
            'persona_email': 'test@example.com'
        }
        
        response = supabase.table('attempt_logs').insert(test_data).execute()
        
        print("✅ SUCCESS! Database connection verified.")
        print(f"📊 Inserted record ID: {response.data[0]['id']}")
        
        # Test read
        records = supabase.table('attempt_logs').select('*').limit(5).execute()
        print(f"📖 Total records in database: {len(records.data)}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    test_supabase_connection()