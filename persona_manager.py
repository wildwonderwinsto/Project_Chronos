import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime
from persona_generator import PersonaGenerator

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

class PersonaManager:
    """Manages persona generation and storage in Supabase"""
    
    def __init__(self):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.generator = PersonaGenerator()
    
    def create_and_log_persona(self):
        """
        Generate a persona and immediately log it to Supabase
        Returns: (persona_dict, log_id)
        """
        
        # Generate persona
        persona = self.generator.generate()
        
        # Create full name for database
        full_name = f"{persona['first']} {persona['last']}"
        
        # Create database entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'INITIATED',
            'persona_name': full_name,
            'persona_email': persona['email'],
            'persona_username': None  # Not using username anymore
        }
        
        try:
            response = self.supabase.table('attempt_logs').insert(log_entry).execute()
            log_id = response.data[0]['id']
            
            print(f"✅ Persona logged to database")
            print(f"   ID: {log_id}")
            print(f"   Name: {persona['first']} {persona['last']}")
            print(f"   Email: {persona['email']}")
            
            return persona, log_id
            
        except Exception as e:
            print(f"❌ Failed to log persona: {str(e)}")
            return persona, None
    
    def generate_batch_and_log(self, count=5):
        """Generate multiple personas and log them all"""
        results = []
        
        print(f"\n🔄 Generating {count} personas...\n")
        
        for i in range(count):
            persona, log_id = self.create_and_log_persona()
            results.append((persona, log_id))
            print(f"   Progress: {i+1}/{count}\n")
        
        print(f"✅ Batch complete! {len(results)} personas generated and logged.\n")
        return results


def test_persona_manager():
    """Test the full persona generation → database pipeline"""
    
    manager = PersonaManager()
    
    print("=" * 70)
    print("🧪 TESTING PERSONA MANAGER (Generation → Database Pipeline)")
    print("=" * 70)
    
    # Test single persona
    print("\n📝 Test 1: Single Persona Generation")
    print("-" * 70)
    persona, log_id = manager.create_and_log_persona()
    
    if log_id:
        print("\n✅ Single persona test PASSED")
    else:
        print("\n❌ Single persona test FAILED")
        return
    
    # Test batch generation
    print("\n📝 Test 2: Batch Generation (5 personas)")
    print("-" * 70)
    results = manager.generate_batch_and_log(5)
    
    success_count = sum(1 for _, log_id in results if log_id is not None)
    
    print(f"\n📊 Results:")
    print(f"   Total Generated: {len(results)}")
    print(f"   Successfully Logged: {success_count}")
    print(f"   Failed: {len(results) - success_count}")
    
    # Email routing summary
    print(f"\n📮 Email Routing Summary:")
    print("-" * 70)
    routing = {}
    for persona, _ in results:
        domain = persona['email'].split('@')[1]
        routing[domain] = routing.get(domain, 0) + 1
    
    for domain, count in routing.items():
        print(f"   {domain}: {count} emails")
    
    print("\n💡 All emails route to your configured master accounts!")
    
    if success_count == len(results):
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  Some tests failed ({len(results) - success_count} failures)")
    
    print("=" * 70)

if __name__ == "__main__":
    test_persona_manager()