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
    
    async def run_single_attempt(self):
        """
        Execute ONE complete form submission attempt
        Returns: (success: bool, log_id: str)
        """
        
        # Step 1: Generate persona
        persona = self.persona_generator.generate()
        full_name = f"{persona['first']} {persona['last']}"
        
        self._print_header(full_name, persona['email'])
        
        # Step 2: Create initial database log
        if not self.test_mode:
            log_id = await self.db_logger.create_log(full_name, persona['email'])
            if not log_id:
                return False, None
        else:
            log_id = "TEST_MODE"
            print(f"   Test Mode: Skipping database log")
       
        # Step 3: Launch browser and attempt submission
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=BROWSER_CONFIG['headless'] and not self.manual_captcha and not self.test_mode
                )
            
                context = await browser.new_context(
                    viewport=BROWSER_CONFIG['viewport'],
                    user_agent=BROWSER_CONFIG['user_agent']
                )
            
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