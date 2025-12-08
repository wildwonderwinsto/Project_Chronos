import asyncio
from playwright.async_api import Page
from config import FORM_SELECTORS


class SubmissionVerifier:
    """Verifies if form submission was successful or failed"""
    
    async def verify(self, page: Page):
        """
        Check if submission was successful or failed
        Returns: (success: bool, reason: str)
        """
        
        # Wait a moment for page to update
        await asyncio.sleep(2)
        
        # Check success indicators
        if await self._check_thanks_message(page):
            return True, "THANKS_MESSAGE_DISPLAYED"
        
        if await self._check_content_hidden(page):
            return True, "CONTENT_HIDDEN_SUCCESS"
        
        if await self._check_localstorage_flag(page):
            return True, "LOCALSTORAGE_FLAG_SET"
        
        # Check for failure indicators
        page_content = await page.content()
        
        if 'already entered' in page_content.lower():
            return False, "ALREADY_ENTERED"
        
        if 'invalid' in page_content.lower():
            return False, "INVALID_SUBMISSION"
        
        if 'error' in page_content.lower():
            return False, "ERROR_IN_PAGE"
        
        if 'captcha' in page_content.lower() and 'incorrect' in page_content.lower():
            return False, "CAPTCHA_INCORRECT"
        
        # Check if form is still visible
        if await self._check_form_visible(page):
            return False, "FORM_STILL_VISIBLE"
        
        # Default: Unclear state
        return False, "UNKNOWN_STATE"
    
    async def _check_thanks_message(self, page: Page):
        """Check if the thanks div is visible"""
        try:
            return await page.evaluate('''
                () => {
                    const thanks = document.getElementById('thanks');
                    return thanks && thanks.style.display !== 'none';
                }
            ''')
        except:
            return False
    
    async def _check_content_hidden(self, page: Page):
        """Check if content div is hidden"""
        try:
            return await page.evaluate('''
                () => {
                    const content = document.getElementById('content');
                    return content && content.style.display === 'none';
                }
            ''')
        except:
            return False
    
    async def _check_localstorage_flag(self, page: Page):
        """Check for localStorage flag"""
        try:
            return await page.evaluate('''
                () => {
                    return localStorage.getItem("comp_388") !== null;
                }
            ''')
        except:
            return False
    
    async def _check_form_visible(self, page: Page):
        """Check if form is still visible"""
        try:
            return await page.is_visible(FORM_SELECTORS['submit_button'])
        except:
            return False