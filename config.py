"""
Configuration file for Project Chronos
"""

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
    "headless": False,  # Set to True for production (no visible browser)
    "viewport": {
        "width": 1920,
        "height": 1080
    },
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
SCHEDULING = {
    # Absolute termination date
    "termination_date": "2025-12-31",
    "termination_time": "23:59:59",
    
    # Day/Night modes (EST)
    "day_start_hour": 8,    # 8 AM EST
    "day_end_hour": 23,     # 11 PM EST
    
    # Base frequency (entries per hour)
    "day_mode_base_frequency": 2.0,      # 2 entries/hour during day
    "night_mode_base_frequency": 0.5,    # 0.5 entries/hour at night
    
    # Volume ramp-up settings
    "ramp_start_date": "2024-12-06",     # Start date (today)
    "casual_multiplier": 1.0,            # Multiply base frequency by this at start
    "aggressive_multiplier": 4.0,        # Multiply base frequency by this near deadline
    "final_day_multiplier": 4.0,         # Extra boost on last day
    
    # Weekend boost
    "weekend_multiplier": 1.2,           # 20% more on weekends
    
    # Stochastic jitter (randomness)
    "jitter_min_factor": 0.5,            # Minimum timing (50% of calculated)
    "jitter_max_factor": 1.5,            # Maximum timing (150% of calculated)
    
    # Panic mode (cool-down after failures)
    "panic_failure_threshold": 10,       # Trigger panic after 10 consecutive failures
    "panic_cooldown_minutes": 60,        # Sleep for 60-120 minutes in panic mode
    "panic_cooldown_max_minutes": 120,
    
    # Retry settings
    "max_retries_per_attempt": 3,        # Retry failed attempts up to 3 times
    "retry_delay_minutes": 5,            # Wait 5 minutes between retries
}

# Timezone for scheduling (EST)
SCHEDULE_TIMEZONE = "America/New_York"