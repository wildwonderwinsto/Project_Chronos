import os
import random
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv
from supabase import create_client, Client
import pytesseract
from PIL import Image
import io
import re

# Assuming these imports exist in your project structure
from persona_generator import PersonaGenerator
from config import (
    TARGET_URL, 
    FORM_SELECTORS, 
    SUCCESS_INDICATORS, 
    FAILURE_INDICATORS,
    BROWSER_CONFIG,
    TIMING,
    AGE_RANGE
)

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

class BrowserEngine:
    """Core browser automation engine with strict context isolation"""
    
    def __init__(self, manual_captcha=False):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.persona_generator = PersonaGenerator()
        self.manual_captcha = manual_captcha
        
        # Create directories for error artifacts
        Path("screenshots").mkdir(exist_ok=True)
        Path("html_snapshots").mkdir(exist_ok=True)
        Path("captcha_images").mkdir(exist_ok=True)
    
    async def run_single_attempt(self):
        """
        Execute ONE complete form submission attempt
        Returns: (success: bool, log_id: str)
        """
        
        # Step 1: Generate persona
        persona = self.persona_generator.generate()
        full_name = f"{persona['first']} {persona['last']}"
        
        print(f"\n{'='*70}")
        print(f"🎭 NEW ATTEMPT STARTING")
        print(f"{'='*70}")
        print(f"   Name: {full_name}")
        print(f"   Email: {persona['email']}")
        
        # Step 2: Create initial database log (INITIATED status)
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'INITIATED',
            'persona_name': full_name,
            'persona_email': persona['email'],
            'start_time': datetime.utcnow().isoformat()
        }
        
        try:
            response = self.supabase.table('attempt_logs').insert(log_entry).execute()
            log_id = response.data[0]['id']
            print(f"   Log ID: {log_id}")
        except Exception as e:
            print(f"❌ Failed to create log entry: {e}")
            return False, None
       
        # Step 3: Launch browser and attempt submission
        try:
            async with async_playwright() as p:
                # Launch browser with strict context isolation
                browser = await p.chromium.launch(
                    headless=BROWSER_CONFIG['headless'] and not self.manual_captcha
                )
            
                # Create NEW context (isolated session)
                context = await browser.new_context(
                    viewport=BROWSER_CONFIG['viewport'],
                    user_agent=BROWSER_CONFIG['user_agent']
                )
            
                # Create new page
                page = await context.new_page()
            
                print(f"   🌐 Navigating to target...")
            
                # Navigate to target URL (directly to the iframe/embed)
                await page.goto(TARGET_URL, timeout=TIMING['page_load_timeout'])
                
                # Wait for page to fully load
                await asyncio.sleep(random.uniform(2, 3))
            
                # Check if already entered (localStorage check)
                already_entered = await page.evaluate('''
                    () => {
                        return localStorage.getItem("comp_388") !== null;
                    }
                ''')
                
                if already_entered:
                    print(f"   ⚠️  Browser context shows already entered (localStorage)")
                    # This shouldn't happen with fresh context, but log it
                    await self._update_log_failure(
                        log_id,
                        datetime.utcnow().isoformat(),
                        "ALREADY_ENTERED_LOCALSTORAGE",
                        None,
                        None
                    )
                    await context.close()
                    await browser.close()
                    return False, log_id
            
                # STEP 1: Click the "Start" button to reveal the form
                try:
                    print(f"   🔍 Looking for Start button...")
                    
                    # Wait for button to be visible
                    await page.wait_for_selector(
                        FORM_SELECTORS['user_details_button'], 
                        timeout=10000,
                        state='visible'
                    )
                    
                    print(f"   🔘 Clicking Start button...")
                    
                    # Click the button - try direct click first
                    try:
                        await page.click(FORM_SELECTORS['user_details_button'], timeout=5000)
                    except Exception as e1:
                        print(f"   ℹ️  Standard click failed, trying JavaScript click...")
                        await page.evaluate('''
                            () => {
                                const btn = document.querySelector('#user_details_button');
                                if (btn) btn.click();
                            }
                        ''')
                    
                    # Wait for form to appear after clicking Start
                    print(f"   ⏳ Waiting for form to load...")
                    await asyncio.sleep(random.uniform(1, 2))
                    
                    # Verify the first form field appeared
                    await page.wait_for_selector(
                        FORM_SELECTORS['first_name'],
                        timeout=10000,
                        state='visible'
                    )
                    print(f"   ✅ Form loaded successfully!")
                    
                except Exception as e:
                    print(f"   ❌ Failed to open form: {str(e)}")
                    raise
                    
                # --- FORM FILLING LOGIC ---
                print(f"   ✍️  Filling form...")
                
                # Fill the form with human-like behavior
                await self._fill_form_humanlike(page, persona)
                
                # --- CAPTCHA SOLVING ---
                print(f"   🔐 Solving CAPTCHA...")
                captcha_solved = await self._solve_captcha(page, log_id)
                
                if not captcha_solved:
                    print(f"   ❌ CAPTCHA solving failed")
                    await self._update_log_failure(
                        log_id,
                        datetime.utcnow().isoformat(),
                        "CAPTCHA_FAILED",
                        await self._capture_screenshot(page, log_id),
                        await self._capture_html(page, log_id)
                    )
                    await context.close()
                    await browser.close()
                    return False, log_id
                
                print(f"   🎯 Completing social actions...")
                
                # Handle social action links (click them to mark as complete)
                await self._handle_social_actions(page)
                
                print(f"   📤 Submitting form...")
                
                # Submit the form
                await page.click(FORM_SELECTORS['submit_button'])
                
                # Wait for form submission to process
                await asyncio.sleep(random.uniform(3, 5))
                
                print(f"   🔍 Verifying submission...")
                
                # Verify success or failure
                success, reason = await self._verify_submission(page)
                
                # Update database
                end_time = datetime.utcnow().isoformat()
                
                if success:
                    print(f"   ✅ SUCCESS!")
                    await self._update_log_success(log_id, end_time, reason)
                else:
                    print(f"   ❌ FAILED: {reason}")
                    
                    # Capture error artifacts
                    screenshot_path = await self._capture_screenshot(page, log_id)
                    html_path = await self._capture_html(page, log_id)
                    
                    await self._update_log_failure(
                        log_id, 
                        end_time, 
                        reason, 
                        screenshot_path, 
                        html_path
                    )
                
                # Cleanup
                await context.close()
                await browser.close()
                
                print(f"{'='*70}\n")
                
                return success, log_id
                
        except Exception as e:
            print(f"   ❌ CRITICAL ERROR: {str(e)}")
            
            # Try to capture error state
            try:
                screenshot_path = await self._capture_screenshot(page, log_id)
                html_path = await self._capture_html(page, log_id)
            except:
                screenshot_path = None
                html_path = None
            
            # Update log with error
            end_time = datetime.utcnow().isoformat()
            await self._update_log_failure(
                log_id,
                end_time,
                f"EXCEPTION: {str(e)}",
                screenshot_path,
                html_path
            )
            
            print(f"{'='*70}\n")
            return False, log_id
    
    async def _solve_captcha(self, page: Page, log_id: str):
        """
        Solve the CAPTCHA - either automatically with OCR or manually
        Returns: True if solved, False if failed
        """
        try:
            # Wait for CAPTCHA image to load
            await page.wait_for_selector('.captcha', timeout=5000)
            
            if self.manual_captcha:
                # MANUAL MODE: Show browser and wait for user input
                print(f"   🖐️  MANUAL CAPTCHA MODE")
                print(f"   👀 Browser is visible - please solve the CAPTCHA")
                print(f"   ⏳ Waiting for you to type the CAPTCHA text...")
                
                # Wait for user to fill in the captcha field (up to 60 seconds)
                for i in range(60):
                    await asyncio.sleep(1)
                    
                    # Check if user has typed something
                    captcha_value = await page.input_value(FORM_SELECTORS['captcha'])
                    if captcha_value and len(captcha_value) > 0:
                        print(f"   ✅ CAPTCHA entered: {captcha_value}")
                        return True
                
                print(f"   ⏰ Timeout waiting for manual CAPTCHA input")
                return False
            
            else:
                # AUTOMATIC MODE: Use OCR
                print(f"   🤖 Attempting automatic OCR...")
                
                # Get the CAPTCHA image element
                captcha_img = await page.query_selector('.captcha')
                if not captcha_img:
                    print(f"   ❌ CAPTCHA image not found")
                    return False
                
                # Take screenshot of the CAPTCHA
                captcha_screenshot = await captcha_img.screenshot()
                
                # Save for debugging
                captcha_path = f"captcha_images/{log_id}.png"
                with open(captcha_path, 'wb') as f:
                    f.write(captcha_screenshot)
                
                # Open with PIL
                image = Image.open(io.BytesIO(captcha_screenshot))
                
                # Preprocess image for better OCR
                image = image.convert('L')  # Convert to grayscale
                
                # Use pytesseract to extract text
                captcha_text = pytesseract.image_to_string(image, config='--psm 7')
                
                # Clean the text
                captcha_text = re.sub(r'[^a-zA-Z0-9]', '', captcha_text).strip()
                
                print(f"   📝 OCR detected: '{captcha_text}'")
                
                if len(captcha_text) < 3:
                    print(f"   ⚠️  OCR result too short, might be inaccurate")
                    # You can decide to retry or fail here
                
                # Fill in the CAPTCHA field
                await page.fill(FORM_SELECTORS['captcha'], captcha_text)
                
                print(f"   ✅ CAPTCHA filled with OCR result")
                return True
                
        except Exception as e:
            print(f"   ❌ CAPTCHA solving error: {e}")
            return False
    
    async def _fill_form_humanlike(self, page: Page, persona: dict):
        """Fill form fields with realistic human typing behavior"""
        
        # First Name
        await page.wait_for_selector(FORM_SELECTORS['first_name'], timeout=TIMING['element_wait_timeout'])
        await page.click(FORM_SELECTORS['first_name'])
        await self._type_humanlike(page, FORM_SELECTORS['first_name'], persona['first'])
        
        # Pause between fields (hesitation)
        await asyncio.sleep(random.uniform(
            TIMING['field_pause_min'] / 1000,
            TIMING['field_pause_max'] / 1000
        ))
        
        # Last Name
        await page.click(FORM_SELECTORS['last_name'])
        await self._type_humanlike(page, FORM_SELECTORS['last_name'], persona['last'])
        
        # Pause
        await asyncio.sleep(random.uniform(
            TIMING['field_pause_min'] / 1000,
            TIMING['field_pause_max'] / 1000
        ))
        
        # Email
        await page.click(FORM_SELECTORS['email'])
        await self._type_humanlike(page, FORM_SELECTORS['email'], persona['email'])
        
        # Pause
        await asyncio.sleep(random.uniform(
            TIMING['field_pause_min'] / 1000,
            TIMING['field_pause_max'] / 1000
        ))
        
        # Country - select United States (already pre-selected in the HTML)
        try:
            await page.select_option(FORM_SELECTORS['country'], value='US')
            print(f"      ✓ Country selected")
        except Exception as e:
            print(f"      ℹ️  Country already set to US")
        
        # Skip newsletter checkbox as requested
        
        # Age checkbox (over 18)
        try:
            await page.check(FORM_SELECTORS['age'])
            print(f"      ✓ Age checkbox checked")
        except Exception as e:
            print(f"      ⚠️  Could not check age: {e}")
        
        # Terms checkbox
        try:
            await page.check(FORM_SELECTORS['terms'])
            print(f"      ✓ Terms checkbox checked")
        except Exception as e:
            print(f"      ⚠️  Could not check terms: {e}")
        
        # Final pause before captcha
        await asyncio.sleep(random.uniform(0.5, 1))
    
    async def _type_humanlike(self, page: Page, selector: str, text: str):
        """Type text with randomized delays between keystrokes"""
        for char in text:
            await page.type(selector, char, delay=random.randint(
                TIMING['typing_delay_min'],
                TIMING['typing_delay_max']
            ))
    
    async def _handle_social_actions(self, page: Page):
        """
        Handle social action links - click them to mark as complete
        These are the Instagram, TikTok, Facebook, etc. links
        """
        actions_completed = 0
        
        # Get all action links
        action_selectors = [
            'a[data-action-id="1765"]',  # Instagram
            'a[data-action-id="1766"]',  # TikTok
            'a[data-action-id="1767"]',  # Facebook
            'a[data-action-id="1768"]',  # Discord
            'a[data-action-id="1769"]',  # YouTube
            'a[data-action-id="1770"]',  # Reddit
            'a[data-action-id="1771"]',  # Twitch
            'a[data-action-id="1772"]',  # Twitter
        ]
        
        for selector in action_selectors:
            try:
                # Check if the action link exists and is visible
                element = await page.query_selector(selector)
                
                if element:
                    # Check if already completed
                    action_id = await element.get_attribute('data-action-id')
                    already_complete = await page.evaluate(f'''
                        () => {{
                            const tick = document.getElementById('tick_{action_id}');
                            return tick && tick.style.display !== 'none';
                        }}
                    ''')
                    
                    if not already_complete:
                        # Open the link in a new tab and immediately close it
                        async with page.expect_popup() as popup_info:
                            await page.click(selector)
                        
                        popup = await popup_info.value
                        await asyncio.sleep(0.5)  # Brief delay
                        await popup.close()
                        
                        # Wait for the action to be marked complete
                        await asyncio.sleep(0.5)
                        
                        actions_completed += 1
                    
            except Exception as e:
                # Continue even if one action fails
                continue
        
        if actions_completed > 0:
            print(f"      ✓ Completed {actions_completed} social actions")
        else:
            print(f"      ℹ️  Social actions already complete or not found")
    
    async def _verify_submission(self, page: Page):
        """
        Check if submission was successful or failed
        Returns: (success: bool, reason: str)
        """
        
        # Wait a moment for page to update
        await asyncio.sleep(2)
        
        # Check if the "thanks" div is now visible (success indicator)
        try:
            thanks_visible = await page.evaluate('''
                () => {
                    const thanks = document.getElementById('thanks');
                    return thanks && thanks.style.display !== 'none';
                }
            ''')
            
            if thanks_visible:
                return True, "THANKS_MESSAGE_DISPLAYED"
        except:
            pass
        
        # Check if content div is hidden (another success indicator)
        try:
            content_hidden = await page.evaluate('''
                () => {
                    const content = document.getElementById('content');
                    return content && content.style.display === 'none';
                }
            ''')
            
            if content_hidden:
                return True, "CONTENT_HIDDEN_SUCCESS"
        except:
            pass
        
        # Check for localStorage flag
        try:
            localstorage_set = await page.evaluate('''
                () => {
                    return localStorage.getItem("comp_388") !== null;
                }
            ''')
            
            if localstorage_set:
                return True, "LOCALSTORAGE_FLAG_SET"
        except:
            pass
        
        # Check page content for errors
        page_content = await page.content()
        
        # Look for common error messages
        if 'already entered' in page_content.lower():
            return False, "ALREADY_ENTERED"
        
        if 'invalid' in page_content.lower():
            return False, "INVALID_SUBMISSION"
        
        if 'error' in page_content.lower():
            return False, "ERROR_IN_PAGE"
        
        # Check for CAPTCHA error
        if 'captcha' in page_content.lower() and 'incorrect' in page_content.lower():
            return False, "CAPTCHA_INCORRECT"
        
        # Default: If form is still visible, assume failure
        try:
            form_visible = await page.is_visible(FORM_SELECTORS['submit_button'])
            if form_visible:
                return False, "FORM_STILL_VISIBLE"
        except:
            pass
        
        # Default: Unclear state
        return False, "UNKNOWN_STATE"
    
    async def _capture_screenshot(self, page: Page, log_id: str):
        """Capture screenshot on failure"""
        try:
            filename = f"screenshots/{log_id}.png"
            await page.screenshot(path=filename, full_page=True)
            return filename
        except:
            return None
    
    async def _capture_html(self, page: Page, log_id: str):
        """Capture HTML snapshot on failure"""
        try:
            filename = f"html_snapshots/{log_id}.html"
            html_content = await page.content()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return filename
        except:
            return None
    
    async def _update_log_success(self, log_id: str, end_time: str, reason: str):
        """Update database log with success status"""
        try:
            self.supabase.table('attempt_logs').update({
                'status': 'SUCCESS',
                'end_time': end_time,
                'error_code': None,
                'error_message': reason
            }).eq('id', log_id).execute()
        except Exception as e:
            print(f"⚠️  Failed to update success log: {e}")
    
    async def _update_log_failure(self, log_id: str, end_time: str, reason: str, 
                                   screenshot_path: str, html_path: str):
        """Update database log with failure status"""
        try:
            self.supabase.table('attempt_logs').update({
                'status': 'FAILED',
                'end_time': end_time,
                'error_code': reason.split(':')[0] if ':' in reason else reason,
                'error_message': reason,
                'screenshot_path': screenshot_path,
                'html_snapshot_path': html_path
            }).eq('id', log_id).execute()
        except Exception as e:
            print(f"⚠️  Failed to update failure log: {e}")


# Test functions
async def test_browser_engine_auto():
    """Test with automatic OCR CAPTCHA solving"""
    
    print("\n" + "="*70)
    print("🧪 TESTING BROWSER ENGINE - AUTOMATIC OCR MODE")
    print("="*70)
    print("\n⚠️  Make sure you have pytesseract installed:")
    print("     pip install pytesseract pillow")
    print("     (Also install Tesseract OCR on your system)")
    print("\nStarting test in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    engine = BrowserEngine(manual_captcha=False)
    success, log_id = await engine.run_single_attempt()
    
    print("\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    print(f"   Success: {success}")
    print(f"   Log ID: {log_id}")
    print("\n✅ Check Supabase and captcha_images/ folder!")
    print("="*70)


async def test_browser_engine_manual():
    """Test with manual CAPTCHA solving"""
    
    print("\n" + "="*70)
    print("🧪 TESTING BROWSER ENGINE - MANUAL CAPTCHA MODE")
    print("="*70)
    print("\n🖐️  Browser will stay open for you to solve CAPTCHA manually")
    print("   Just type the CAPTCHA text and the bot will continue")
    print("\nStarting test in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    engine = BrowserEngine(manual_captcha=True)
    success, log_id = await engine.run_single_attempt()
    
    print("\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    print(f"   Success: {success}")
    print(f"   Log ID: {log_id}")
    print("\n✅ Check Supabase to see the logged attempt!")
    print("="*70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "manual":
        asyncio.run(test_browser_engine_manual())
    else:
        asyncio.run(test_browser_engine_auto())