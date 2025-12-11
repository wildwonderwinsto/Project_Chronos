import warnings
warnings.filterwarnings('ignore', message='.*urllib3 v2 only supports OpenSSL.*')

import os
import random
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from supabase import create_client, Client

# Add parent directory to path so we can import config and persona_generator
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from parent directory (Project_Chronos/)
from persona_generator import PersonaGenerator
from config import TARGET_URL, BROWSER_CONFIG, TIMING, FORM_SELECTORS, PROXY_CONFIG

# Import from same directory (Browser/)
from Browser.form_filler import FormFiller
from Browser.captcha_solver import CaptchaSolver
from Browser.social_actions import SocialActionsHandler
from Browser.submission_verifier import SubmissionVerifier
from Browser.database_logger import DatabaseLogger
from Browser.screenshot_manager import ScreenshotManager

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')


class BrowserEngine:
    """Core browser automation engine with strict context isolation"""
    
    def __init__(self, manual_captcha=False, test_mode=False):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.persona_generator = PersonaGenerator()
        self.manual_captcha = manual_captcha
        self.test_mode = test_mode
        
        # Initialize helper components
        self.db_logger = DatabaseLogger(self.supabase)
        self.screenshot_manager = ScreenshotManager()
        self.form_filler = FormFiller()
        self.captcha_solver = CaptchaSolver(manual_captcha)
        self.social_handler = SocialActionsHandler()
        self.verifier = SubmissionVerifier()
        
        # Create directories for error artifacts
        Path("screenshots").mkdir(exist_ok=True)
        Path("captcha_images").mkdir(exist_ok=True)
        
    async def _test_proxy(self, proxy: dict) -> bool:
        """Test if a proxy works by attempting a quick HTTPS page load"""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                
                context = await browser.new_context(
                    proxy={'server': proxy['server']}
                )
                
                page = await context.new_page()
                
                # Test with a simple, fast endpoint
                await page.goto('https://www.google.com', timeout=15000, wait_until='domcontentloaded')
                
                await context.close()
                await browser.close()
                
                return True
        
        except Exception as e:
            print(f"      ⚠️  Proxy test failed: {str(e)[:60]}")
            return False

    async def _get_working_proxy(self, proxy_mgr):
        """
        Keep trying to get a working proxy until one is found.
        Will refresh proxy list if needed and NEVER return None.
        """
        max_consecutive_failures = 50  # After 50 failed proxies, refresh the list
        consecutive_failures = 0
        attempt = 0
        
        while True:
            attempt += 1
            
            # Get a candidate proxy
            candidate_proxy = await proxy_mgr.get_proxy()
            
            if not candidate_proxy:
                print(f"   ⚠️  No more proxies in cache, forcing refresh...")
                # Force refresh the proxy list
                await proxy_mgr._refresh_proxy_list()
                consecutive_failures = 0
                continue
            
            # Test if proxy works
            print(f"   🔍 Testing proxy #{attempt}: {candidate_proxy['ip']}...")
            
            if await self._test_proxy(candidate_proxy):
                print(f"   ✅ Proxy validated after {attempt} attempts!")
                return candidate_proxy
            else:
                print(f"   ❌ Proxy failed, trying next...")
                proxy_mgr.mark_proxy_failed(candidate_proxy['server'])
                consecutive_failures += 1
                
                # If we've failed too many times, refresh the proxy list
                if consecutive_failures >= max_consecutive_failures:
                    print(f"   ⚠️  {consecutive_failures} consecutive failures, refreshing proxy list...")
                    await proxy_mgr._refresh_proxy_list()
                    consecutive_failures = 0
                
                # Small delay to avoid hammering
                await asyncio.sleep(0.5)

    async def run_single_attempt(self):
        """Execute ONE complete form submission attempt"""
        
        # Import managers
        from Browser.proxy_manager import ProxyManager
        from Browser.fingerprint_manager import FingerprintManager
        
        # Step 1: Generate persona
        persona = self.persona_generator.generate()
        full_name = f"{persona['first']} {persona['last']}"
        
        self._print_header(full_name, persona['email'])
        
        # Step 2: Get proxy and fingerprint
        proxy_mgr = ProxyManager()
        fingerprint_mgr = FingerprintManager()
        
        # Get a working proxy - will NEVER return None
        print(f"   🌐 Finding working proxy...")
        proxy = await self._get_working_proxy(proxy_mgr)
        
        print(f"   ✅ Using proxy: {proxy['ip']} ({proxy['city']}, {proxy['country']})")
        fingerprint = fingerprint_mgr.generate_fingerprint(timezone=proxy['timezone'])
        
        print(f"   🎭 Fingerprint: {fingerprint['browser_type'].title()} on {fingerprint['platform']}")
        print(f"   🕐 Timezone: {fingerprint['timezone']}")
        
        # Step 3: Create initial database log
        if not self.test_mode:
            log_id = await self.db_logger.create_log(full_name, persona['email'])
            if not log_id:
                return False, None
            
            # Log proxy info
            await self._log_proxy_info(log_id, proxy)
        else:
            log_id = "TEST_MODE"
            print(f"   Test Mode: Skipping database log")
    
        # Step 4: Launch browser with stealth
        try:
            async with async_playwright() as p:
                # Build browser context options
                context_options = {
                    'viewport': fingerprint['viewport'],
                    'user_agent': fingerprint['user_agent'],
                    'timezone_id': fingerprint['timezone'],
                    'locale': fingerprint['locale'],
                    'permissions': [],
                    'geolocation': None,
                    'color_scheme': random.choice(['light', 'dark', 'no-preference']),
                    'proxy': {
                        'server': proxy['server']
                    }
                }
                
                # Launch browser
                browser = await p.chromium.launch(
                    headless=BROWSER_CONFIG['headless'] and not self.manual_captcha and not self.test_mode,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--incognito',  
                        '--disable-extensions',
                    ]
                )
            
                # Create FRESH context with NO PERSISTENCE
                context = await browser.new_context(**context_options)
                
                # Inject stealth scripts BEFORE page creation
                await context.add_init_script("""
                    // Remove webdriver flag
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Remove automation flags
                    delete navigator.__proto__.webdriver;
                    
                    // Fix Chrome detection
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Fix permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // CRITICAL: Override localStorage to prevent ANY persistence
                    const fakeStorage = {
                        length: 0,
                        clear: () => {},
                        getItem: (key) => null,
                        setItem: (key, value) => {},
                        removeItem: (key) => {},
                        key: (index) => null
                    };
                    
                    // Replace localStorage with fake version that does nothing
                    Object.defineProperty(window, 'localStorage', {
                        value: fakeStorage,
                        writable: false,
                        configurable: false
                    });
                    
                    // Replace sessionStorage too
                    Object.defineProperty(window, 'sessionStorage', {
                        value: fakeStorage,
                        writable: false,
                        configurable: false
                    });
                    
                    console.log('🔒 Storage override complete - localStorage/sessionStorage disabled');
                """)
            
                # Create page
                page = await context.new_page()

                print(f"   🌐 Navigating to target...")
                
                # Navigate to the page
                await page.goto(TARGET_URL, timeout=TIMING['page_load_timeout'], wait_until='domcontentloaded')
                
                # Wait for page to fully load
                await asyncio.sleep(random.uniform(2, 3))

                # Verify localStorage is actually blocked
                print(f"   🔍 Verifying storage is disabled...")
                try:
                    storage_check = await page.evaluate("""
                        () => {
                            try {
                                // Try to write
                                localStorage.setItem('test', 'value');
                                const hasTest = localStorage.getItem('test') !== null;
                                
                                // Check for comp flag
                                const hasFlag = localStorage.getItem('comp_388') !== null;
                                
                                return {
                                    canWrite: hasTest,
                                    hasCompFlag: hasFlag,
                                    storageLength: localStorage.length
                                };
                            } catch (e) {
                                return {
                                    canWrite: false,
                                    hasCompFlag: false,
                                    blocked: true
                                };
                            }
                        }
                    """)
                    
                    if storage_check.get('hasCompFlag'):
                        print(f"   ❌ CRITICAL: comp_388 flag detected! Storage override failed!")
                        print(f"   📊 Storage state: {storage_check}")
                        raise Exception("Storage persistence detected - cannot proceed")
                    
                    if storage_check.get('canWrite'):
                        print(f"   ⚠️  WARNING: localStorage is still writable! Check: {storage_check}")
                    else:
                        print(f"   ✅ Storage successfully disabled - comp_388 flag cannot be set")
                        
                except Exception as e:
                    if "Storage persistence detected" in str(e):
                        raise  # Re-raise critical errors
                    print(f"   ⚠️  Storage verification error: {e}")
           
                # Open the form
                if not await self._open_form(page):
                    raise Exception("Failed to open form")
                
                # Fill form
                print(f"   ✍️  Filling form...")
                await self.form_filler.fill_form(page, persona)
                
                # Solve CAPTCHA
                print(f"   🔐 Solving CAPTCHA...")
                captcha_solved = await self.captcha_solver.solve(page, log_id)
                
                if not captcha_solved:
                    print(f"   ❌ CAPTCHA solving failed")
                    if not self.test_mode:
                        screenshot = await self.screenshot_manager.capture(page, log_id)
                        await self.db_logger.log_failure(log_id, "CAPTCHA_FAILED", screenshot)
                    await context.close()
                    await browser.close()
                    return False, log_id
                
                # Handle social actions
                print(f"   🎯 Completing social actions...")
                await self.social_handler.handle_actions(page)

                # Verify CAPTCHA is still valid after social actions
                print(f"   🔍 Verifying CAPTCHA still valid...")
                captcha_still_valid = await self._verify_captcha_filled(page)
                
                if not captcha_still_valid:
                    print(f"   ⚠️  CAPTCHA cleared after social actions, re-solving...")
                    captcha_solved = await self.captcha_solver.solve(page, log_id)
                    
                    if not captcha_solved:
                        print(f"   ❌ CAPTCHA re-solve failed")
                        if not self.test_mode:
                            screenshot = await self.screenshot_manager.capture(page, log_id)
                            await self.db_logger.log_failure(log_id, "CAPTCHA_RESET_FAILED", screenshot)
                        await context.close()
                        await browser.close()
                        return False, log_id
                
                # TEST MODE: Stop before submission
                if self.test_mode:
                    return await self._handle_test_mode(context, browser, log_id)
                
                # PRODUCTION MODE: Submit
                print(f"   📤 Submitting form...")
                success, reason = await self._submit_and_verify(page)
                
                # Update database
                if success:
                    print(f"   ✅ SUCCESS!")
                    await self.db_logger.log_success(log_id, reason)
                else:
                    print(f"   ❌ FAILED: {reason}")
                    screenshot = await self.screenshot_manager.capture(page, log_id)
                    await self.db_logger.log_failure(log_id, reason, screenshot)
                
                await context.close()
                await browser.close()
                
                print(f"{'='*70}\n")
                return success, log_id
                
        except Exception as e:
            print(f"   ❌ CRITICAL ERROR: {str(e)}")
            return await self._handle_exception(page, log_id, e)

    async def _log_proxy_info(self, log_id: str, proxy: dict):
        """Log proxy information to database"""
        try:
            self.supabase.table('attempt_logs').update({
                'proxy_ip': proxy['ip'],
                'proxy_city': proxy.get('city'),
                'proxy_state': proxy.get('country'),
                'proxy_isp': proxy.get('isp'),
                'proxy_timezone': proxy.get('timezone')
            }).eq('id', log_id).execute()
        except Exception as e:
            print(f"      ⚠️  Failed to log proxy info: {e}")

    def _print_header(self, name, email):
        """Print attempt header"""
        print(f"\n{'='*70}")
        if self.test_mode:
            print(f"🧪 TEST MODE - NO ACTUAL SUBMISSION")
        else:
            print(f"🎭 NEW ATTEMPT STARTING")
        print(f"{'='*70}")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
    
    async def _open_form(self, page):
        """Click Start button to reveal form"""
        try:
            print(f"   🔍 Looking for Start button...")
            
            await page.wait_for_selector(
                FORM_SELECTORS['user_details_button'], 
                timeout=10000,
                state='visible'
            )
            
            print(f"   🔘 Clicking Start button...")
            
            try:
                await page.click(FORM_SELECTORS['user_details_button'], timeout=5000)
            except:
                print(f"   ℹ️  Standard click failed, trying JavaScript click...")
                await page.evaluate('''
                    () => {
                        const btn = document.querySelector('#user_details_button');
                        if (btn) btn.click();
                    }
                ''')
            
            print(f"   ⏳ Waiting for form to load...")
            await asyncio.sleep(random.uniform(1, 2))
            
            await page.wait_for_selector(
                FORM_SELECTORS['first_name'],
                timeout=10000,
                state='visible'
            )
            print(f"   ✅ Form loaded successfully!")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to open form: {str(e)}")
            return False
    
    async def _verify_captcha_filled(self, page):
        """Verify that CAPTCHA field still has a value"""
        try:
            current_captcha = await page.input_value(FORM_SELECTORS['captcha'])
            is_filled = current_captcha and len(current_captcha) >= 3
            if is_filled:
                print(f"      ✅ CAPTCHA still valid: '{current_captcha}'")
            return is_filled
        except Exception as e:
            print(f"      ⚠️  Could not verify CAPTCHA: {e}")
            return False
    
    async def _submit_and_verify(self, page):
        """Submit form and verify result"""
        await page.click(FORM_SELECTORS['submit_button'])
        await asyncio.sleep(random.uniform(3, 5))
        
        print(f"   🔍 Verifying submission...")
        return await self.verifier.verify(page)
    
    async def _handle_test_mode(self, context, browser, log_id):
        """Handle test mode completion"""
        print(f"\n   🧪 TEST MODE: Stopping before submission")
        print(f"   ✅ Form filled and ready to submit")
        print(f"   👀 Browser will stay open for 30 seconds for you to inspect")
        
        await asyncio.sleep(30)
        
        await context.close()
        await browser.close()
        
        print(f"{'='*70}\n")
        return True, log_id
    
    async def _handle_exception(self, page, log_id, exception):
        """Handle critical exceptions"""
        try:
            screenshot = await self.screenshot_manager.capture(page, log_id)
        except:
            screenshot = None
        
        if not self.test_mode:
            await self.db_logger.log_failure(
                log_id,
                f"EXCEPTION: {str(exception)}",
                screenshot
            )
        
        print(f"{'='*70}\n")
        return False, log_id