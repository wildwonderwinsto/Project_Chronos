import os
import random
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv
from supabase import create_client, Client

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
    
    def __init__(self):
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.persona_generator = PersonaGenerator()
        
        # Create directories for error artifacts
        Path("screenshots").mkdir(exist_ok=True)
        Path("html_snapshots").mkdir(exist_ok=True)
    
    async def run_single_attempt(self):
        """
        Execute ONE complete form submission attempt
        Returns: (success: bool, log_id: str)
        """
        
        # Step 1: Generate persona
        persona = self.persona_generator.generate()
        full_name = f"{persona['first']} {persona['last']}"
        
        # Generate random age within range
        age = random.randint(AGE_RANGE['min'], AGE_RANGE['max'])
        
        print(f"\n{'='*70}")
        print(f"🎭 NEW ATTEMPT STARTING")
        print(f"{'='*70}")
        print(f"   Name: {full_name}")
        print(f"   Email: {persona['email']}")
        print(f"   Age: {age}")
        
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
                    headless=BROWSER_CONFIG['headless']
                )
            
                # Create NEW context (isolated session)
                context = await browser.new_context(
                    viewport=BROWSER_CONFIG['viewport'],
                    user_agent=BROWSER_CONFIG['user_agent']
                )
            
                # Create new page
                page = await context.new_page()
            
                print(f"   🌐 Navigating to target...")
            
                # Navigate to target URL
                await page.goto(TARGET_URL, timeout=TIMING['page_load_timeout'])
            
                # STEP 1: Wait for and close the newsletter modal popup
                try:
                    print(f"   ⏳ Waiting for newsletter popup (appears after ~5 seconds)...")
                    await page.wait_for_selector(
                        FORM_SELECTORS['modal_close_button'],
                        timeout=8000,  # Wait up to 8 seconds for modal
                        state='visible'
                    )
                    print(f"   ❌ Closing newsletter popup...")
                    await page.click(FORM_SELECTORS['modal_close_button'])
                    await asyncio.sleep(random.uniform(0.5, 1))
                    print(f"   ✅ Newsletter popup closed")
                except Exception as e:
                    print(f"   ℹ️  No newsletter popup (or already closed)")
            
                # STEP 2: Click the "Start" button to reveal the form
                try:
                    print(f"   🔍 Looking for Start button...")
                    await page.wait_for_selector(
                        FORM_SELECTORS['user_details_button'], 
                        timeout=10000,
                        state='visible'
                    )
                    print(f"   🔘 Clicking Start button...")
                    await page.click(FORM_SELECTORS['user_details_button'])
                
                    # Wait for form to appear after clicking Start
                    print(f"   ⏳ Waiting for form to load...")
                    await asyncio.sleep(random.uniform(2, 3))
                
                    # Verify the first form field appeared
                    await page.wait_for_selector(
                        FORM_SELECTORS['first_name'],
                        timeout=10000,
                        state='visible'
                    )
                    print(f"   ✅ Form loaded successfully!")
                
                except Exception as e:
                    print(f"   ❌ Failed to open form: {str(e)}")
                    raise  # Re-raise to trigger the outer error handling
                    
                # --- FORM FILLING LOGIC (Runs only if Start button succeeded) ---
                print(f"   ✍️  Filling form...")
                
                # Fill the form with human-like behavior
                await self._fill_form_humanlike(page, persona, age)
                
                print(f"   📤 Submitting form...")
                
                # Submit the form
                await page.click(FORM_SELECTORS['submit_button'])
                
                # Wait for form submission to process
                await asyncio.sleep(random.uniform(2, 4))
                
                print(f"   🔗 Handling social action links...")
                
                # Handle extra action links (open and instantly close)
                await self._handle_social_actions(page)
                
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
            
            # Update log with error
            end_time = datetime.utcnow().isoformat()
            await self._update_log_failure(
                log_id,
                end_time,
                f"EXCEPTION: {str(e)}",
                None,
                None
            )
            
            print(f"{'='*70}\n")
            return False, log_id
    
    async def _fill_form_humanlike(self, page: Page, persona: dict, age: int):
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
        
        # Age
        await page.click(FORM_SELECTORS['age'])
        await self._type_humanlike(page, FORM_SELECTORS['age'], str(age))
        
        # Pause
        await asyncio.sleep(random.uniform(
            TIMING['field_pause_min'] / 1000,
            TIMING['field_pause_max'] / 1000
        ))
        
        # Terms checkbox
        try:
            await page.check(FORM_SELECTORS['terms'])
            print(f"      ✓ Terms checkbox checked")
        except Exception as e:
            print(f"      ⚠️  Could not check terms: {e}")
        
        # Final pause before submit
        await asyncio.sleep(random.uniform(1, 2))
    
    async def _type_humanlike(self, page: Page, selector: str, text: str):
        """Type text with randomized delays between keystrokes"""
        for char in text:
            await page.type(selector, char, delay=random.randint(
                TIMING['typing_delay_min'],
                TIMING['typing_delay_max']
            ))
    
    async def _handle_social_actions(self, page: Page):
        """
        Handle extra action links (open and instantly close popups)
        These are social media links that need to be clicked for bonus entries
        """
        actions_completed = 0
        
        for selector in FORM_SELECTORS["extra_actions"]:
            try:
                # Check if the action link exists on the page
                element = await page.query_selector(selector)
                
                if element:
                    # Open the popup and immediately close it
                    async with page.expect_popup() as popup_info:
                        await page.click(selector)
                    
                    popup = await popup_info.value
                    await popup.close()
                    
                    # Small delay before next action
                    await asyncio.sleep(TIMING['popup_close_delay'] / 1000)
                    
                    actions_completed += 1
                    
            except Exception as e:
                # Silently continue if action fails (not critical)
                continue
        
        if actions_completed > 0:
            print(f"      ✓ Completed {actions_completed} social actions")
        else:
            print(f"      ℹ️  No social actions found")
    
    async def _verify_submission(self, page: Page):
        """
        Check if submission was successful or failed
        Returns: (success: bool, reason: str)
        """
        
        # Wait a moment for page to update
        await asyncio.sleep(2)
        
        # Check for success indicators
        current_url = page.url
        page_content = await page.content()
        
        # Success check 1: URL contains success path (if configured)
        if SUCCESS_INDICATORS.get('url_contains'):
            if SUCCESS_INDICATORS['url_contains'] in current_url:
                return True, "URL_REDIRECT_SUCCESS"
        
        # Success check 2: Success text appears
        if SUCCESS_INDICATORS.get('text_contains'):
            if SUCCESS_INDICATORS['text_contains'].lower() in page_content.lower():
                return True, "SUCCESS_TEXT_FOUND"
        
        # Success check 3: Success element exists
        if SUCCESS_INDICATORS.get('element_exists'):
            try:
                await page.wait_for_selector(
                    SUCCESS_INDICATORS['element_exists'],
                    timeout=3000
                )
                return True, "SUCCESS_ELEMENT_FOUND"
            except:
                pass
        
        # Failure check: Look for error indicators
        for error_text in FAILURE_INDICATORS.get('text_contains', []):
            if error_text.lower() in page_content.lower():
                return False, f"ERROR_TEXT: {error_text}"
        
        # Check for error element
        if FAILURE_INDICATORS.get('element_exists'):
            try:
                error_element = await page.query_selector(FAILURE_INDICATORS['element_exists'])
                if error_element:
                    error_msg = await error_element.inner_text()
                    return False, f"ERROR_ELEMENT: {error_msg[:50]}"
            except:
                pass
        
        # Default: If no clear success, assume failure
        return False, "NO_SUCCESS_INDICATOR"
    
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


# Test function
async def test_browser_engine():
    """Test a single browser automation attempt"""
    
    print("\n" + "="*70)
    print("🧪 TESTING BROWSER AUTOMATION ENGINE")
    print("="*70)
    print("\n⚠️  Make sure you've updated TARGET_URL in config.py!")
    print("\nStarting test in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    engine = BrowserEngine()
    success, log_id = await engine.run_single_attempt()
    
    print("\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    print(f"   Success: {success}")
    print(f"   Log ID: {log_id}")
    print("\n✅ Check Supabase to see the logged attempt!")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(test_browser_engine())