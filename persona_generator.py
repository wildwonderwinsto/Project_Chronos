import random
import string
from datetime import datetime
from faker import Faker

# Initialize Faker with US locale
fake = Faker('en_US')

class PersonaGenerator:
    """Generates realistic, internally consistent fake identities"""
    
    # Master email accounts (all aliases route here)
    MASTER_EMAILS = {
        "gmail.com": "",      # Replace with your actual Gmail
        "outlook.com": "", # Replace with your actual Outlook
        "yahoo.com": "",       # Replace with your actual Yahoo
        "icloud.com": "",    # Replace with your actual iCloud
    }
    
    # Common keyboard typo patterns (adjacent keys)
    TYPO_MAP = {
        'a': ['s', 'q', 'w'],
        'e': ['w', 'r', 'd'],
        'i': ['u', 'o', 'k'],
        'o': ['i', 'p', 'l'],
        's': ['a', 'd', 'w'],
        't': ['r', 'y', 'g'],
        'n': ['b', 'm', 'h'],
        'r': ['e', 't', 'f']
    }
    
    def __init__(self):
        self.fake = Faker('en_US')
    
    def generate(self):
        """Generate a complete persona with first/last name and routed email"""
        
        # Step 1: Generate core identity
        first_name = self.fake.first_name()
        last_name = self.fake.last_name()
        
        # Step 2: Apply "Fat Finger" typo (5% chance, name only)
        if random.random() < 0.05:
            first_name = self._inject_typo(first_name)
        if random.random() < 0.05:
            last_name = self._inject_typo(last_name)
        
        # Step 3: Generate email (50% chance name-based, 50% random username)
        email = self._generate_email(first_name, last_name)
        
        return {
            "first": first_name,
            "last": last_name,
            "email": email
        }
    
    def _inject_typo(self, text):
        """Simulate human typing error (adjacent key substitution)"""
        text_lower = text.lower()
        typo_candidates = [i for i, char in enumerate(text_lower) if char in self.TYPO_MAP]
        
        if not typo_candidates:
            return text  # No typo-able characters
        
        # Pick random character to mistype
        typo_index = random.choice(typo_candidates)
        char_to_replace = text_lower[typo_index]
        typo_char = random.choice(self.TYPO_MAP[char_to_replace])
        
        # Replace in original text (preserve case)
        text_list = list(text)
        if text[typo_index].isupper():
            typo_char = typo_char.upper()
        text_list[typo_index] = typo_char
        
        return ''.join(text_list)
    
    def _generate_email(self, first_name, last_name):
        """
        Generate email with Gmail+ style aliasing that routes to master account
        
        50% chance: Name-based (j.smith, john.smith, etc.)
        50% chance: Random username (coolguy47, happycat29, etc.)
        
        All emails use + aliasing:
        - Gmail: masteraccount+alias@gmail.com → routes to masteraccount@gmail.com
        - Outlook: masteraccount+alias@outlook.com → routes to masteraccount@outlook.com
        """
        
        # Choose base domain
        base_domain = random.choice(list(self.MASTER_EMAILS.keys()))
        master_email = self.MASTER_EMAILS[base_domain]
        master_account = master_email.split('@')[0]
        
        # 50/50 chance: name-based vs random username
        use_name_based = random.random() < 0.5
        
        if use_name_based:
            # Name-based patterns
            alias = self._generate_name_based_alias(first_name, last_name)
        else:
            # Random username patterns
            alias = self._generate_random_username_alias()
        
        # Construct final email with + aliasing
        # Format: masteraccount+alias@domain.com
        final_email = f"{master_account}+{alias}@{base_domain}"
        
        return final_email
    
    def _generate_name_based_alias(self, first_name, last_name):
        """Generate alias based on actual name"""
        # Normalize names
        first_clean = first_name.lower().replace("'", "").replace("-", "")
        last_clean = last_name.lower().replace("'", "").replace("-", "")
        
        # Random birth year (not older than 30 years)
        current_year = datetime.now().year
        birth_year = random.randint(current_year - 30, current_year - 18)  # Ages 18-30
        
        # Choose pattern
        pattern = random.choice([
            f"{first_clean[0]}.{last_clean}",           # j.smith
            f"{first_clean}.{last_clean}",              # john.smith
            f"{first_clean}{last_clean}",               # johnsmith
            f"{first_clean}.{last_clean[0]}",           # john.s
            f"{first_clean[0]}{last_clean}",            # jsmith
            f"{first_clean}.{last_clean}.{birth_year}", # john.smith.1995
            f"{first_clean}{birth_year}",               # john1995
            f"{last_clean}.{first_clean[0]}",           # smith.j
        ])
        
        return pattern
    
    def _generate_random_username_alias(self):
        """Generate completely random username (no name correlation)"""
        
        # Random birth year (ages 18-30)
        current_year = datetime.now().year
        birth_year = random.randint(current_year - 30, current_year - 18)
        
        # Random username patterns
        adjectives = [
            "cool", "happy", "lucky", "super", "fast", "smart", "brave",
            "wild", "free", "bright", "dark", "silent", "loud", "epic",
            "mega", "ultra", "swift", "true", "real", "pro"
        ]
        
        nouns = [
            "cat", "dog", "wolf", "bear", "tiger", "eagle", "lion",
            "dragon", "phoenix", "ninja", "gamer", "rider", "hunter",
            "king", "queen", "star", "moon", "sun", "sky", "storm"
        ]
        
        pattern_type = random.choice([
            "adjective_noun_number",
            "noun_number",
            "adjective_number",
            "word_year",
            "random_chars"
        ])
        
        if pattern_type == "adjective_noun_number":
            # coolguy47, happycat92
            adj = random.choice(adjectives)
            noun = random.choice(nouns)
            num = random.randint(10, 99)
            return f"{adj}{noun}{num}"
        
        elif pattern_type == "noun_number":
            # tiger2023, dragon88
            noun = random.choice(nouns)
            num = random.choice([random.randint(10, 99), birth_year])
            return f"{noun}{num}"
        
        elif pattern_type == "adjective_number":
            # lucky77, cool1995
            adj = random.choice(adjectives)
            num = random.choice([random.randint(10, 99), birth_year])
            return f"{adj}{num}"
        
        elif pattern_type == "word_year":
            # gamer1998, ninja2001
            word = random.choice(adjectives + nouns)
            return f"{word}{birth_year}"
        
        else:  # random_chars
            # random alphanumeric like: user7k3m2
            chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            return f"user{chars}"
    
    def generate_batch(self, count=10):
        """Generate multiple personas"""
        return [self.generate() for _ in range(count)]


# Test function
def test_persona_generator():
    """Test the persona generator and show examples"""
    generator = PersonaGenerator()
    
    print("=" * 70)
    print("🎭 PERSONA GENERATOR TEST")
    print("=" * 70)
    print("\n⚠️  IMPORTANT: Update MASTER_EMAILS in the code with your real emails!")
    print("-" * 70)
    
    personas = generator.generate_batch(15)
    
    # Separate by type
    name_based = []
    random_based = []
    
    for persona in personas:
        # Check if email contains name parts
        email_local = persona['email'].split('@')[0].split('+')[1]  # Get alias part
        first_in_email = persona['first'].lower()[:4] in email_local
        last_in_email = persona['last'].lower()[:4] in email_local
        
        if first_in_email or last_in_email:
            name_based.append(persona)
        else:
            random_based.append(persona)
    
    print(f"\n📊 NAME-BASED EMAILS ({len(name_based)} personas)")
    print("-" * 70)
    for persona in name_based[:5]:  # Show first 5
        print(f"   {persona['first']} {persona['last']}")
        print(f"   → {persona['email']}")
        print()
    
    print(f"\n🎲 RANDOM USERNAME EMAILS ({len(random_based)} personas)")
    print("-" * 70)
    for persona in random_based[:5]:  # Show first 5
        print(f"   {persona['first']} {persona['last']}")
        print(f"   → {persona['email']}")
        print()
    
    print("=" * 70)
    print(f"✅ Generated {len(personas)} personas successfully!")
    print(f"   Name-based: {len(name_based)} (~50% expected)")
    print(f"   Random: {len(random_based)} (~50% expected)")
    print("=" * 70)
    
    # Show routing explanation
    print("\n📮 EMAIL ROUTING EXPLANATION:")
    print("-" * 70)
    print("All emails use '+' aliasing, which routes to your master account:")
    print()
    print("Example:")
    print("  masteraccount+john.smith@gmail.com  → masteraccount@gmail.com")
    print("  masteraccount+coolguy47@gmail.com   → masteraccount@gmail.com")
    print()
    print("The website sees different emails, but YOU receive all messages!")
    print("=" * 70)

if __name__ == "__main__":
    test_persona_generator()