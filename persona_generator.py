import random
import string
from datetime import datetime
from faker import Faker

fake = Faker('en_US')

class PersonaGenerator:
    """Generates highly realistic, internally consistent fake identities"""
    
    # Master email accounts (weighted by real-world usage)
    # ✅ ENABLED emails will be used for persona generation
    # ❌ DISABLED emails are commented out but can be re-enabled anytime
    MASTER_EMAILS = {
        # ✅ ACTIVE MASTER EMAIL
        "outlook.com": "UsersMaiI",      # Your primary email
        
        # ❌ DISABLED - Uncomment to re-enable
        # "gmail.com": "",                # Uncomment and add your Gmail
        # "yahoo.com": "",                # Uncomment and add your Yahoo
        # "icloud.com": "",               # Uncomment and add your iCloud
        # "protonmail.com": "",           # Uncomment and add your ProtonMail
    }
    
    # Domain weights - automatically calculated from enabled emails
    # This will dynamically adjust based on which emails are enabled
    @classmethod
    def _get_active_domains(cls):
        """Get only the domains that have email addresses configured"""
        return {domain: email for domain, email in cls.MASTER_EMAILS.items() if email}
    
    @classmethod
    def _get_domain_weights(cls):
        """Generate weights based on number of active domains"""
        active = cls._get_active_domains()
        num_active = len(active)
        
        if num_active == 0:
            raise ValueError("No master emails configured! Please add at least one email address.")
        
        # Equal weight distribution if only one domain
        if num_active == 1:
            return [100]
        
        # Distribute weights evenly across active domains
        return [100 // num_active] * num_active
    
    # Enhanced typo patterns
    TYPO_MAP = {
        'a': ['s', 'q', 'w', 'z'],
        'b': ['v', 'n', 'g', 'h'],
        'c': ['x', 'v', 'd', 'f'],
        'd': ['s', 'f', 'e', 'r', 'c'],
        'e': ['w', 'r', 'd', 's'],
        'f': ['d', 'g', 'r', 't', 'v'],
        'g': ['f', 'h', 't', 'y', 'b'],
        'h': ['g', 'j', 'y', 'u', 'n'],
        'i': ['u', 'o', 'k', 'j'],
        'j': ['h', 'k', 'u', 'i', 'n'],
        'k': ['j', 'l', 'i', 'o', 'm'],
        'l': ['k', 'o', 'p'],
        'm': ['n', 'k', 'j'],
        'n': ['b', 'm', 'h', 'j'],
        'o': ['i', 'p', 'l', 'k'],
        'p': ['o', 'l'],
        'q': ['w', 'a'],
        'r': ['e', 't', 'f', 'd'],
        's': ['a', 'd', 'w', 'e', 'x'],
        't': ['r', 'y', 'g', 'f'],
        'u': ['y', 'i', 'j', 'h'],
        'v': ['c', 'b', 'f', 'g'],
        'w': ['q', 'e', 's', 'a'],
        'x': ['z', 'c', 's', 'd'],
        'y': ['t', 'u', 'h', 'g'],
        'z': ['x', 'a', 's']
    }
    
    # Common nicknames
    NICKNAMES = {
        'Michael': ['Mike', 'Mikey', 'Mick'],
        'William': ['Will', 'Bill', 'Billy', 'Liam'],
        'James': ['Jim', 'Jimmy', 'Jamie'],
        'Robert': ['Rob', 'Bob', 'Bobby', 'Robbie'],
        'Richard': ['Rick', 'Dick', 'Ricky', 'Rich'],
        'Christopher': ['Chris', 'Topher'],
        'Matthew': ['Matt', 'Matty'],
        'Daniel': ['Dan', 'Danny'],
        'David': ['Dave', 'Davey'],
        'Joseph': ['Joe', 'Joey'],
        'Jennifer': ['Jen', 'Jenny', 'Jenn'],
        'Elizabeth': ['Liz', 'Beth', 'Betty', 'Lizzy'],
        'Jessica': ['Jess', 'Jessie'],
        'Katherine': ['Kate', 'Katie', 'Kathy', 'Kat'],
        'Margaret': ['Maggie', 'Meg', 'Peggy'],
        'Rebecca': ['Becky', 'Becca'],
        'Samantha': ['Sam', 'Sammy'],
        'Patricia': ['Pat', 'Patty', 'Tricia'],
        'Christine': ['Chris', 'Christie', 'Tina'],
        'Kimberly': ['Kim', 'Kimmy']
    }
    
    def __init__(self):
        self.fake = Faker('en_US')
    
    def generate(self):
        """Generate a complete persona with realistic variations"""
        
        # Verify at least one email is configured
        active_domains = self._get_active_domains()
        if not active_domains:
            raise ValueError("No master emails configured! Please add at least one email address in MASTER_EMAILS.")
        
        # Step 1: Generate core identity
        first_name = self.fake.first_name()
        last_name = self.fake.last_name()
        
        # Step 2: Apply nickname (30% chance)
        if random.random() < 0.30 and first_name in self.NICKNAMES:
            first_name = random.choice(self.NICKNAMES[first_name])
        
        # Step 3: Apply realistic typos (8% chance for name-based emails)
        original_first = first_name
        original_last = last_name
        has_typo = False
        
        if random.random() < 0.08:
            typo_type = random.choice(['adjacent', 'double', 'omit', 'transpose'])
            if random.random() < 0.5:  # Typo in first or last
                first_name = self._apply_realistic_typo(first_name, typo_type)
            else:
                last_name = self._apply_realistic_typo(last_name, typo_type)
            has_typo = True
        
        # Step 4: Add middle initial (25% chance)
        middle_initial = ""
        if random.random() < 0.25:
            middle_initial = random.choice(string.ascii_uppercase)
        
        # Step 5: Generate realistic age
        birth_year = self._generate_realistic_birth_year()
        
        # Step 6: Generate email
        email = self._generate_email(original_first, original_last, birth_year)
        
        return {
            "first": first_name,
            "middle": middle_initial,
            "last": last_name,
            "email": email,
            "birth_year": birth_year,
            "has_typo": has_typo
        }
    
    def _apply_realistic_typo(self, text, typo_type):
        """Apply various realistic typing errors"""
        if len(text) < 2:
            return text
        
        text_lower = text.lower()
        
        if typo_type == 'adjacent' and any(c in self.TYPO_MAP for c in text_lower):
            # Adjacent key substitution
            typo_candidates = [i for i, char in enumerate(text_lower) if char in self.TYPO_MAP]
            if typo_candidates:
                idx = random.choice(typo_candidates)
                char = text_lower[idx]
                typo_char = random.choice(self.TYPO_MAP[char])
                text_list = list(text)
                text_list[idx] = typo_char.upper() if text[idx].isupper() else typo_char
                return ''.join(text_list)
        
        elif typo_type == 'double':
            # Double letter (common with fast typing)
            idx = random.randint(1, len(text) - 1)
            return text[:idx] + text[idx-1] + text[idx:]
        
        elif typo_type == 'omit':
            # Missing letter
            if len(text) > 3:
                idx = random.randint(1, len(text) - 2)
                return text[:idx] + text[idx+1:]
        
        elif typo_type == 'transpose':
            # Swap adjacent letters
            if len(text) > 2:
                idx = random.randint(0, len(text) - 2)
                text_list = list(text)
                text_list[idx], text_list[idx+1] = text_list[idx+1], text_list[idx]
                return ''.join(text_list)
        
        return text
    
    def _generate_realistic_birth_year(self):
        """Generate realistic age distribution (not everyone is 20-something)"""
        # Age distribution based on internet users
        age_ranges = [
            (18, 25, 20),  # Young adults - 20%
            (26, 35, 30),  # Millennials - 30%
            (36, 45, 25),  # Gen X - 25%
            (46, 60, 20),  # Boomers - 20%
            (61, 75, 5),   # Seniors - 5%
        ]
        
        current_year = datetime.now().year
        ranges, weights = zip(*[(r, w) for *r, w in age_ranges])
        age_range = random.choices(ranges, weights=weights)[0]
        age = random.randint(age_range[0], age_range[1])
        return current_year - age
    
    def _generate_email(self, first_name, last_name, birth_year):
        """Generate realistic email with proper domain distribution"""
        
        # Get active domains and weights
        active_domains = self._get_active_domains()
        domains = list(active_domains.keys())
        weights = self._get_domain_weights()
        
        # Choose domain based on weights
        base_domain = random.choices(domains, weights=weights)[0]
        master_account = active_domains[base_domain]
        
        # 60% name-based, 40% random (people usually use their names)
        use_name_based = random.random() < 0.60
        
        if use_name_based:
            alias = self._generate_name_based_alias(first_name, last_name, birth_year)
        else:
            alias = self._generate_random_username_alias(birth_year)
        
        return f"{master_account}+{alias}@{base_domain}"
    
    def _generate_name_based_alias(self, first_name, last_name, birth_year):
        """Generate realistic name-based email aliases"""
        first = first_name.lower().replace("'", "").replace("-", "")
        last = last_name.lower().replace("'", "").replace("-", "")
        
        # More diverse patterns with realistic weights
        patterns = [
            (f"{first}.{last}", 20),                    # john.smith (most common)
            (f"{first}{last}", 15),                     # johnsmith
            (f"{first[0]}.{last}", 12),                 # j.smith
            (f"{first[0]}{last}", 10),                  # jsmith
            (f"{first}.{last[0]}", 8),                  # john.s
            (f"{first}_{last}", 7),                     # john_smith
            (f"{first}.{last}{birth_year % 100}", 6),   # john.smith95
            (f"{first}{birth_year % 100}", 5),          # john95
            (f"{last}.{first}", 5),                     # smith.john
            (f"{last}{first[0]}", 4),                   # smithj
            (f"{first}{last[0]}", 3),                   # johns
            (f"{first}.{last}.{birth_year}", 3),        # john.smith.1995
            (f"{first}_{last}_{birth_year % 100}", 2), # john_smith_95
        ]
        
        pattern_choices, weights = zip(*patterns)
        return random.choices(pattern_choices, weights=weights)[0]
    
    def _generate_random_username_alias(self, birth_year):
        """Generate realistic random usernames"""
        
        adjectives = [
            "cool", "happy", "lucky", "super", "fast", "smart", "brave", "wild",
            "free", "bright", "dark", "silent", "loud", "epic", "mega", "ultra",
            "swift", "true", "real", "pro", "blue", "red", "golden", "silver",
            "mad", "crazy", "chill", "lit", "fire", "ice", "shadow", "ghost"
        ]
        
        nouns = [
            "cat", "dog", "wolf", "bear", "tiger", "eagle", "lion", "dragon",
            "phoenix", "ninja", "gamer", "rider", "hunter", "warrior", "king",
            "queen", "star", "moon", "sun", "sky", "storm", "thunder", "blade",
            "knight", "wizard", "ace", "boss", "chief", "legend", "beast", "fox"
        ]
        
        # More realistic username patterns
        pattern_type = random.choices(
            ["adjective_noun_num", "noun_num", "word_year", "word_underscore_num", 
             "just_word_num", "double_word", "xXwordXx"],
            weights=[25, 20, 15, 15, 10, 10, 5]
        )[0]
        
        if pattern_type == "adjective_noun_num":
            adj = random.choice(adjectives)
            noun = random.choice(nouns)
            num = random.randint(1, 999)
            return f"{adj}{noun}{num}"
        
        elif pattern_type == "noun_num":
            noun = random.choice(nouns)
            num = random.choice([
                random.randint(1, 99),
                random.randint(100, 999),
                birth_year % 100,
                birth_year
            ])
            return f"{noun}{num}"
        
        elif pattern_type == "word_year":
            word = random.choice(adjectives + nouns)
            return f"{word}{birth_year}"
        
        elif pattern_type == "word_underscore_num":
            word = random.choice(adjectives + nouns)
            num = random.randint(1, 999)
            return f"{word}_{num}"
        
        elif pattern_type == "just_word_num":
            word = random.choice(adjectives + nouns)
            num = random.randint(10, 99)
            return f"{word}{num}"
        
        elif pattern_type == "double_word":
            word1 = random.choice(adjectives + nouns)
            word2 = random.choice(nouns)
            return f"{word1}{word2}"
        
        else:  # xXwordXx (nostalgic early 2000s style)
            word = random.choice(adjectives + nouns)
            return f"xX{word}Xx"
    
    def generate_batch(self, count=10):
        """Generate multiple personas"""
        return [self.generate() for _ in range(count)]


# Enhanced test function
def test_persona_generator():
    """Test the enhanced persona generator"""
    generator = PersonaGenerator()
    
    print("=" * 80)
    print("🎭 ENHANCED REALISTIC PERSONA GENERATOR")
    print("=" * 80)
    
    # Show active configuration
    active_domains = generator._get_active_domains()
    print(f"\n✅ ACTIVE MASTER EMAILS:")
    print("-" * 80)
    for domain, account in active_domains.items():
        print(f"   • {account}@{domain}")
    
    disabled_count = len(generator.MASTER_EMAILS) - len(active_domains)
    if disabled_count > 0:
        print(f"\n❌ DISABLED: {disabled_count} email(s) (can be re-enabled in code)")
    
    print("-" * 80)
    
    personas = generator.generate_batch(20)
    
    # Statistics
    name_based = sum(1 for p in personas if any(
        p['first'].lower()[:3] in p['email'].split('+')[1].lower() or
        p['last'].lower()[:3] in p['email'].split('+')[1].lower()
    ))
    with_middle = sum(1 for p in personas if p['middle'])
    with_typos = sum(1 for p in personas if p['has_typo'])
    
    # Age distribution
    ages = [datetime.now().year - p['birth_year'] for p in personas]
    avg_age = sum(ages) / len(ages)
    
    print(f"\n📊 SAMPLE PERSONAS (showing 10 of {len(personas)})")
    print("-" * 80)
    
    for i, persona in enumerate(personas[:10], 1):
        age = datetime.now().year - persona['birth_year']
        middle = f" {persona['middle']}." if persona['middle'] else ""
        typo_flag = " ⚠️ typo" if persona['has_typo'] else ""
        
        print(f"{i:2d}. {persona['first']}{middle} {persona['last']} (age {age}){typo_flag}")
        print(f"    📧 {persona['email']}")
        print()
    
    print("=" * 80)
    print(f"✅ GENERATION STATISTICS")
    print("-" * 80)
    print(f"   Total personas: {len(personas)}")
    print(f"   Name-based emails: {name_based} ({name_based/len(personas)*100:.0f}%)")
    print(f"   Random usernames: {len(personas)-name_based} ({(len(personas)-name_based)/len(personas)*100:.0f}%)")
    print(f"   With middle initials: {with_middle} ({with_middle/len(personas)*100:.0f}%)")
    print(f"   With typos: {with_typos} ({with_typos/len(personas)*100:.0f}%)")
    print(f"   Average age: {avg_age:.0f} years old")
    print("=" * 80)
    
    print("\n📮 EMAIL ROUTING (+ Aliasing)")
    print("-" * 80)
    print("All emails route to your master account:")
    print()
    for domain, account in active_domains.items():
        print(f"  {account}+john.smith@{domain}  → {account}@{domain}")
    print()
    print("🎯 Websites see unique emails, but YOU receive everything!")
    print("=" * 80)

if __name__ == "__main__":
    test_persona_generator()