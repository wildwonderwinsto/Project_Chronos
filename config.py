"""
Configuration file for Project Chronos
"""

# ===== TARGET WEBSITE CONFIGURATION =====
TARGET_URL = "https://www.originpc.com/landing/2025/winter-white-arachnid-giveaway/#enter"  # ← UPDATE THIS WITH YOUR REAL URL

# Form field selectors
FORM_SELECTORS = {
    # Modal popup that appears first (close it)
    "modal_close_button": "#newsletterModal > div > div > div.modal-header.border-0.pb-0 > button",
    
    # User details button (initial click to reveal form)
    "user_details_button": "#user_details_button",
    
    # Required fields
    "first_name": "#id_first_name",
    "last_name": "#id_last_name",
    "email": "#id_email",
    "age": "#id_age",
    "terms": "#id_terms",
    "submit_button": "#submit_button",
    
    # Extra social actions (open + close immediately)
    "extra_actions": [
        "#action_1765",
        "#action_1766",
        "#action_1767",
        "#action_1768",
        "#action_1769",
        "#action_1770",
        "#action_1771",
        "#action_1772",
    ]
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
    "page_load_timeout": 30000,      # 30 seconds
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