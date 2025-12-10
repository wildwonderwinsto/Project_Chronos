"""
Configuration file for Project Chronos
"""
from datetime import datetime
import pytz

TARGET_URL = "https://prod-giveaways.corsair.com/compo/embed/388/"

FORM_SELECTORS = {
    'user_details_button': '#user_details_button',
    'first_name': '#id_first_name',
    'last_name': '#id_last_name',
    'email': '#id_email',
    'country': '#id_country',
    'newsletter': '#id_newsletter',
    'captcha': '#id_captcha_1',
    'age': '#id_age',
    'terms': '#id_terms',
    'submit_button': '#submit_button'
}

# Success detection
SUCCESS_INDICATORS = {
    "url_contains": None,  # No redirect happens
    "text_contains": "Thanks for entering.",
    "element_exists": "#content > p:nth-child(1)"
}

# Failure detection
FAILURE_INDICATORS = {
    "text_contains": ["error", "invalid", "already", "required"],
    "element_exists": ".error-message"
}

# ===== BROWSER CONFIGURATION =====
BROWSER_CONFIG = {
    "headless": True,  # Set to True for production (no visible browser)
    "viewport": {
        "width": 1920,
        "height": 1080
    },
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ===== PROXY CONFIGURATION =====
PROXY_CONFIG = {
    "max_attempts": 15,  # Try up to 15 proxies before falling back to direct connection
    "test_timeout": 15000,  # Timeout for proxy testing (milliseconds)
    "us_only": True  # Only use US-based proxies
}

# ===== TIMING CONFIGURATION =====
TIMING = {
    "page_load_timeout": 60000,      # 60 second
    "element_wait_timeout": 1000000,   # 10 seconds
    "typing_delay_min": 70,          # Min ms between keystrokes
    "typing_delay_max": 150,         # Max ms between keystrokes
    "field_pause_min": 500,          # Min ms pause between fields
    "field_pause_max": 2000,         # Max ms pause between fields
    "popup_close_delay": 300         # 300ms delay after closing popups
}

# ===== AGE CONFIGURATION =====
# Generate realistic ages (must match your 18-30 constraint)
AGE_RANGE = {
    "min": 18,
    "max": 30
}

# ===== SCHEDULING CONFIGURATION =====
# Automatically get today's date for start
_TODAY = datetime.now(pytz.timezone('America/New_York')).strftime("%Y-%m-%d")

SCHEDULING = {
    # Absolute termination date
    "termination_date": "2025-12-31",
    "termination_time": "23:59:59",
    
    # AUTOMATICALLY USE TODAY'S DATE
    "ramp_start_date": _TODAY,  # ✅ AUTO-UPDATES TO TODAY!
    
    # Day/Night modes (EST)
    "day_start_hour": 8,    # 8 AM EST
    "day_end_hour": 23,     # 11 PM EST
    
    # ===== INCREASED BASE FREQUENCY FOR MORE ENTRIES =====
    # OLD: 2.0/hr day, 0.5/hr night = ~19,000 total entries
    # NEW: 4.0/hr day, 1.0/hr night = ~38,000 total entries
    "day_mode_base_frequency": 4.0,      # 4 entries/hour during day (was 2.0)
    "night_mode_base_frequency": 1.0,    # 1 entry/hour at night (was 0.5)
    
    # Volume ramp-up settings
    "casual_multiplier": 1.0,            # Multiply base frequency by this at start
    "aggressive_multiplier": 5.0,        # Multiply base frequency by this near deadline (was 4.0)
    "final_day_multiplier": 6.0,         # Extra boost on last day (was 4.0)
    
    # Weekend boost
    "weekend_multiplier": 1.3,           # 30% more on weekends (was 1.2)
    
    # Stochastic jitter (randomness)
    "jitter_min_factor": 0.5,            # Minimum timing (50% of calculated)
    "jitter_max_factor": 1.5,            # Maximum timing (150% of calculated)
    
    # Panic mode (cool-down after failures)
    "panic_failure_threshold": 5,        # Trigger panic after 5 consecutive failures (was 10)
    "panic_cooldown_minutes": 60,        # Sleep for 60-120 minutes in panic mode
    "panic_cooldown_max_minutes": 120,
    
    # Retry settings
    "max_retries_per_attempt": 5,        # Retry failed attempts up to 5 times (was 3)
    "retry_delay_minutes": 5,            # Wait 5 minutes between retries
}

# Timezone for scheduling (EST)
SCHEDULE_TIMEZONE = "America/New_York"