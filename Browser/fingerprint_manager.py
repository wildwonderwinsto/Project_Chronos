import random
from fake_useragent import UserAgent


class FingerprintManager:
    """Manages browser fingerprint randomization - US ONLY"""
    
    # US timezones only
    US_TIMEZONES = [
        'America/New_York',      # Eastern
        'America/Chicago',       # Central
        'America/Denver',        # Mountain
        'America/Phoenix',       # Arizona (no DST)
        'America/Los_Angeles',   # Pacific
        'America/Anchorage',     # Alaska
        'Pacific/Honolulu'       # Hawaii
    ]
    
    def __init__(self):
        try:
            self.ua = UserAgent()
        except:
            self.ua = None
    
    def generate_fingerprint(self, timezone: str = None) -> dict:
        """
        Generate a randomized browser fingerprint with US timezone
        """
        
        # Pick a browser type
        browser_type = random.choice(['chrome', 'firefox', 'safari', 'edge'])
        
        # Generate user agent
        user_agent = self._get_user_agent(browser_type)
        
        # Generate viewport
        viewport = self._get_viewport()
        
        # Set timezone - if not provided, use random US timezone
        if not timezone:
            timezone = random.choice(self.US_TIMEZONES)
        elif timezone not in self.US_TIMEZONES:
            # If proxy timezone is not US, default to Eastern
            print(f"      ⚠️  Non-US timezone {timezone}, defaulting to America/New_York")
            timezone = 'America/New_York'
        
        # Determine platform
        if 'Windows' in user_agent:
            platform = 'Win32'
        elif 'Mac' in user_agent:
            platform = 'MacIntel'
        elif 'Linux' in user_agent:
            platform = 'Linux x86_64'
        else:
            platform = 'Win32'
        
        return {
            'user_agent': user_agent,
            'viewport': viewport,
            'timezone': timezone,
            'locale': 'en-US',
            'platform': platform,
            'browser_type': browser_type
        }
    
    def _get_user_agent(self, browser_type: str) -> str:
        """Get a realistic user agent"""
        
        # Try fake-useragent first
        if self.ua:
            try:
                if browser_type == 'chrome':
                    return self.ua.chrome
                elif browser_type == 'firefox':
                    return self.ua.firefox
                elif browser_type == 'safari':
                    return self.ua.safari
                elif browser_type == 'edge':
                    return self.ua.edge
            except:
                pass
        
        # Fallback user agents
        fallback_uas = {
            'chrome': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ],
            'firefox': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            ],
            'safari': [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
            ],
            'edge': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
            ]
        }
        
        return random.choice(fallback_uas.get(browser_type, fallback_uas['chrome']))
    
    def _get_viewport(self) -> dict:
        """Get random viewport"""
        resolutions = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1536, 'height': 864},
            {'width': 1440, 'height': 900},
            {'width': 2560, 'height': 1440},
        ]
        
        return random.choice(resolutions)