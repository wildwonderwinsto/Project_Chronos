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
from config import TARGET_URL, BROWSER_CONFIG, TIMING

# Import from same directory (Browser/) - NO DOTS when running as script
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
        """
        Test if a proxy works by attempting a quick page load with Playwright
        Returns: True if proxy works, False if it fails
        """
        try:
            from playwright.async_api import async_playwright
            
            # Try to load a simple page through the proxy
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                
                context = await browser.new_context(
                    proxy={'server': proxy['server']}
                )
                
                page = await context.new_page()
                
                # Try to load a lightweight page
                await page.goto('http://example.com', timeout=10000)
                
                await context.close()
                await browser.close()
                
                return True
        
        except Exception as e:
            return False

    async def run_single_attempt(self):
        
        """
        Execute ONE complete form submission attempt
        Returns: (success: bool, log_id: str)
        """
        
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
        
        # Try to get a working proxy (with retries)
        proxy = None
        max_proxy_attempts = 3
        
        for attempt in range(max_proxy_attempts):
            candidate_proxy = await proxy_mgr.get_proxy()
            
            if not candidate_proxy:
                print(f"   ⚠️  No proxy available, will use direct connection")
                break
            
            # Test if proxy works
            print(f"   🔍 Testing proxy {candidate_proxy['ip']}...")
            if await self._test_proxy(candidate_proxy):
                proxy = candidate_proxy
                print(f"   ✅ Proxy validated!")
                break
            else:
                print(f"   ❌ Proxy failed validation, trying next...")
                proxy_mgr.mark_proxy_failed(candidate_proxy['server'])
        
        if proxy:
            print(f"   🌐 Using proxy: {proxy['ip']} ({proxy['city']}, {proxy['country']})")
            fingerprint = fingerprint_mgr.generate_fingerprint(timezone=proxy['timezone'])
        else:
            print(f"   🌐 Using direct connection (no proxy)")
            fingerprint = fingerprint_mgr.generate_fingerprint()
            proxy = None
        
        print(f"   🎭 Fingerprint: {fingerprint['browser_type'].title()} on {fingerprint['platform']}")
        print(f"   🕐 Timezone: {fingerprint['timezone']}")
    
    
        
        # Step 3: Create initial database log
        if not self.test_mode:
            log_id = await self.db_logger.create_log(full_name, persona['email'])
            if not log_id:
                return False, None
            
            # Log proxy info
            if proxy:
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
                    'color_scheme': random.choice(['light', 'dark', 'no-preference'])
                }
                
                # Add proxy if available
                if proxy:
                    context_options['proxy'] = {
                        'server': proxy['server']
                    }
                
                # Launch browser
                browser = await p.chromium.launch(
                    headless=BROWSER_CONFIG['headless'] and not self.manual_captcha and not self.test_mode,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
            
                # Create context with fingerprint
                context = await browser.new_context(**context_options)
                
                # Inject stealth scripts
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
                """)
            
                # Create page
                page = await context.new_page()
            
                print(f"   🌐 Navigating to target...")
                await page.goto(TARGET_URL, timeout=TIMING['page_load_timeout'])
                await asyncio.sleep(random.uniform(2, 3))
            
           
            
                # Check if already entered
                if await self._check_already_entered(page):
                    if not self.test_mode:
                        await self.db_logger.log_failure(
                            log_id,
                            "ALREADY_ENTERED_LOCALSTORAGE",
                            None
                        )
                    await context.close()
                    await browser.close()
                    return False, log_id
            
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
    
    async def _check_already_entered(self, page):
        """Check if already entered via localStorage"""
        already_entered = await page.evaluate('''
            () => {
                return localStorage.getItem("comp_388") !== null;
            }
        ''')
        
        if already_entered:
            print(f"   ⚠️  Browser context shows already entered (localStorage)")
        
        return already_entered
    
    async def _open_form(self, page):
        """Click Start button to reveal form"""
        from config import FORM_SELECTORS
        
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
    
    async def _submit_and_verify(self, page):
        """Submit form and verify result"""
        from config import FORM_SELECTORS
        
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