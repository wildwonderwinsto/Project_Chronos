import random
import asyncio
from playwright.async_api import Page
from config import FORM_SELECTORS, TIMING


class FormFiller:
    """Handles form filling with human-like behavior"""
    
    async def fill_form(self, page: Page, persona: dict):
        """Fill form fields with realistic human typing behavior"""
        
        # First Name
        await page.wait_for_selector(FORM_SELECTORS['first_name'], timeout=TIMING['element_wait_timeout'])
        await page.click(FORM_SELECTORS['first_name'])
        await self._type_humanlike(page, FORM_SELECTORS['first_name'], persona['first'])
        
        await self._pause()
        
        # Last Name
        await page.click(FORM_SELECTORS['last_name'])
        await self._type_humanlike(page, FORM_SELECTORS['last_name'], persona['last'])
        
        await self._pause()
        
        # Email
        await page.click(FORM_SELECTORS['email'])
        await self._type_humanlike(page, FORM_SELECTORS['email'], persona['email'])
        
        await self._pause()
        
        # Country - select United States
        try:
            await page.select_option(FORM_SELECTORS['country'], value='US')
            print(f"      ✓ Country selected")
        except Exception as e:
            print(f"      ℹ️  Country already set to US")
        
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
    
    async def _pause(self):
        """Pause between form fields"""
        await asyncio.sleep(random.uniform(
            TIMING['field_pause_min'] / 1000,
            TIMING['field_pause_max'] / 1000
        ))