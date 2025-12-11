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
        Read CAPTCHA optimized for 4-letter uppercase CAPTCHAs like YCFQ
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
            
            # === PREPROCESSING FOR 4-LETTER CAPTCHA ===
            
            # 1. Upscale 3x
            width, height = image.size
            image = image.resize((width * 3, height * 3), Image.LANCZOS)
            
            # 2. Convert to grayscale
            image = image.convert('L')
            
            # 3. Light noise removal (preserves letter edges)
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # 4. Increase contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.5)
            
            # 5. Binary threshold
            threshold = 140
            image = image.point(lambda p: 0 if p < threshold else 255)
            
            # 6. Clean up
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # 7. Ensure black text on white background
            pixels = list(image.getdata())
            if sum(pixels) / len(pixels) < 128:
                image = Image.eval(image, lambda x: 255 - x)
            
            # Save preprocessed
            processed_path = f"captcha_images/{log_id}_processed.png"
            image.save(processed_path)
            
            # === OCR - EXACTLY 4 UPPERCASE LETTERS ===
            LETTERS_ONLY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            best_result = None
            
            # Try multiple PSM modes
            for psm in [7, 8, 13, 6]:
                try:
                    text = pytesseract.image_to_string(
                        image,
                        config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
                    )
                    cleaned = re.sub(r'[^A-Z]', '', text.upper()).strip()
                    
                    # Perfect match - exactly 4 letters
                    if len(cleaned) == 4:
                        return cleaned
                    
                    # Store closest result
                    if cleaned and (best_result is None or abs(len(cleaned) - 4) < abs(len(best_result) - 4)):
                        best_result = cleaned
                        
                except:
                    pass
            
            # If we got something close, try to fix it
            if best_result:
                if len(best_result) > 4:
                    # Take first 4
                    return best_result[:4]
                elif len(best_result) == 3:
                    # Too short - still return it, might work
                    print(f"   ⚠️  Only got 3 letters: {best_result}")
                    return best_result
            
            return None
            
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