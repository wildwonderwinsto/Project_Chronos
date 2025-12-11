import asyncio
import io
import re
from pathlib import Path
from typing import Optional
from playwright.async_api import Page
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from config import FORM_SELECTORS


class CaptchaSolver:
    """Simple CAPTCHA solver - ONE strategy that works for YCEQ style CAPTCHAs"""
    
    def __init__(self, manual_mode: bool = False):
        self.manual_mode = manual_mode
        Path("captcha_images").mkdir(exist_ok=True)
    
    async def solve(self, page: Page, log_id: str) -> bool:
        """Solve the CAPTCHA"""
        try:
            await page.wait_for_selector('.captcha', timeout=5000)
            
            if self.manual_mode:
                return await self._solve_manually(page)
            
            # Get CAPTCHA text
            captcha_text = await self._ocr_captcha(page, log_id)
            
            if not captcha_text or len(captcha_text) < 4:
                print(f"   ❌ OCR failed or result too short: '{captcha_text}'")
                return False
            
            print(f"   ✅ CAPTCHA read: '{captcha_text}'")
            
            # Fill it in
            await page.fill(FORM_SELECTORS['captcha'], '')
            await asyncio.sleep(0.2)
            await page.fill(FORM_SELECTORS['captcha'], captcha_text)
            await asyncio.sleep(0.3)
            
            # Verify
            filled = await page.input_value(FORM_SELECTORS['captcha'])
            if filled == captcha_text:
                print(f"   ✅ CAPTCHA filled successfully")
                return True
            
            print(f"   ❌ Fill verification failed")
            return False
                
        except Exception as e:
            print(f"   ❌ CAPTCHA error: {e}")
            return False
    
    async def _ocr_captcha(self, page: Page, log_id: str) -> Optional[str]:
        """
        Read CAPTCHA with ONE preprocessing strategy optimized for YCEQ-style text
        """
        try:
            # Get CAPTCHA image
            captcha_img = await page.query_selector('.captcha')
            if not captcha_img:
                return None
            
            # Screenshot it
            screenshot_bytes = await captcha_img.screenshot()
            
            # Save original
            original_path = f"captcha_images/{log_id}_original.png"
            with open(original_path, 'wb') as f:
                f.write(screenshot_bytes)
            
            # Open with PIL
            image = Image.open(io.BytesIO(screenshot_bytes))
            
            # === SINGLE PREPROCESSING STRATEGY ===
            # Optimized for noisy CAPTCHAs with dots like "KAEH"
            
            # 1. Upscale 4x for better OCR (larger = better noise removal)
            width, height = image.size
            image = image.resize((width * 4, height * 4), Image.LANCZOS)
            
            # 2. Convert to grayscale
            image = image.convert('L')
            
            # 3. AGGRESSIVE noise removal FIRST (removes dots)
            image = image.filter(ImageFilter.MedianFilter(size=5))
            
            # 4. Increase contrast to make letters darker
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(4.0)
            
            # 5. Binary threshold - LOWER to keep letter pixels
            threshold = 100
            image = image.point(lambda p: 0 if p < threshold else 255)
            
            # 6. Remove any remaining small noise
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # 7. Sharpen the letters
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.5)
            
            # Save preprocessed
            processed_path = f"captcha_images/{log_id}_processed.png"
            image.save(processed_path)
            
            # === OCR WITH SIMPLE CONFIG ===
            # Letters only, single line mode
            LETTERS_ONLY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            
            text = pytesseract.image_to_string(
                image,
                config=f'--psm 7 --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
            )
            
            # Clean result
            captcha_text = re.sub(r'[^a-zA-Z]', '', text).strip().upper()
            
            # Validate length (CAPTCHAs are usually 4-6 chars)
            if len(captcha_text) < 4:
                return None
            
            if len(captcha_text) > 8:
                captcha_text = captcha_text[:6]  # Truncate if too long
            
            return captcha_text
            
        except Exception as e:
            print(f"   ❌ OCR error: {e}")
            return None
    
    async def _solve_manually(self, page: Page) -> bool:
        """Manual CAPTCHA solving"""
        print(f"   🖐️  MANUAL MODE - Type the CAPTCHA")
        
        for i in range(60):
            await asyncio.sleep(1)
            try:
                value = await page.input_value(FORM_SELECTORS['captcha'])
                if value and len(value) > 0:
                    print(f"   ✅ CAPTCHA entered: {value}")
                    return True
            except:
                pass
        
        return False