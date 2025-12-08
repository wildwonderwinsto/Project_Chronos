import asyncio
import io
import re
from playwright.async_api import Page
import pytesseract
from PIL import Image, ImageEnhance
from config import FORM_SELECTORS


class CaptchaSolver:
    """Handles CAPTCHA solving - both manual and automatic OCR"""
    
    def __init__(self, manual_mode=False):
        self.manual_mode = manual_mode
    
    async def solve(self, page: Page, log_id: str):
        """
        Solve the CAPTCHA - either automatically with OCR or manually
        Returns: True if solved, False if failed
        """
        try:
            # Wait for CAPTCHA image to load
            await page.wait_for_selector('.captcha', timeout=5000)
            
            if self.manual_mode:
                return await self._solve_manually(page)
            else:
                return await self._solve_with_ocr(page, log_id)
                
        except Exception as e:
            print(f"   ❌ CAPTCHA solving error: {e}")
            return False
    
    async def _solve_manually(self, page: Page):
        """Manual CAPTCHA solving - wait for user input"""
        print(f"   🖐️  MANUAL CAPTCHA MODE")
        print(f"   👀 Browser is visible - please solve the CAPTCHA")
        print(f"   ⏳ Waiting for you to type the CAPTCHA text...")
        
        # Wait for user to fill in the captcha field (up to 60 seconds)
        for i in range(60):
            await asyncio.sleep(1)
            
            captcha_value = await page.input_value(FORM_SELECTORS['captcha'])
            if captcha_value and len(captcha_value) > 0:
                print(f"   ✅ CAPTCHA entered: {captcha_value}")
                return True
        
        print(f"   ⏰ Timeout waiting for manual CAPTCHA input")
        return False
    
    async def _solve_with_ocr(self, page: Page, log_id: str):
        """Automatic CAPTCHA solving using OCR"""
        print(f"   🤖 Attempting automatic OCR...")
        
        # Get the CAPTCHA image element
        captcha_img = await page.query_selector('.captcha')
        if not captcha_img:
            print(f"   ❌ CAPTCHA image not found")
            return False
        
        # Take screenshot of the CAPTCHA
        captcha_screenshot = await captcha_img.screenshot()
        
        # Save original for debugging
        captcha_path = f"captcha_images/{log_id}_original.png"
        with open(captcha_path, 'wb') as f:
            f.write(captcha_screenshot)
        
        # Process image with OCR
        image = Image.open(io.BytesIO(captcha_screenshot))
        preprocessed_image = self._preprocess_image(image)
        
        # Save preprocessed image for debugging
        preprocessed_path = f"captcha_images/{log_id}_preprocessed.png"
        preprocessed_image.save(preprocessed_path)
        
        # Try multiple OCR configurations
        captcha_text = self._ocr_multiple_attempts(preprocessed_image)
        
        print(f"   ✅ Selected: '{captcha_text}' (length: {len(captcha_text)})")
        
        if len(captcha_text) == 0:
            print(f"   ❌ OCR failed completely - empty result")
            print(f"   📁 Check images: {captcha_path} and {preprocessed_path}")
            return False
        
        if len(captcha_text) < 3:
            print(f"   ⚠️  OCR result suspiciously short")
            print(f"   📁 Check: {preprocessed_path}")
        
        # Fill in the CAPTCHA field
        await page.fill(FORM_SELECTORS['captcha'], captcha_text)
        print(f"   ✅ CAPTCHA filled with OCR result")
        
        await asyncio.sleep(1)
        return True
    
    def _preprocess_image(self, image: Image):
        """Enhanced preprocessing for better OCR accuracy"""
        # 1. Resize to 3x size
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.LANCZOS)
        
        # 2. Convert to grayscale
        image = image.convert('L')
        
        # 3. Increase contrast heavily
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.0)
        
        # 4. Increase brightness slightly
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.2)
        
        # 5. Apply threshold to make it pure black and white
        threshold = 140
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # 6. Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        return image
    
    def _ocr_multiple_attempts(self, image: Image):
        """Try multiple OCR configurations for better accuracy"""
        captcha_attempts = []
        
        # Attempt 1: Default config with character whitelist
        try:
            text1 = pytesseract.image_to_string(
                image, 
                config='--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            captcha_attempts.append(re.sub(r'[^a-zA-Z0-9]', '', text1).strip())
        except:
            pass
        
        # Attempt 2: Single word mode
        try:
            text2 = pytesseract.image_to_string(
                image, 
                config='--psm 8 --oem 3'
            )
            captcha_attempts.append(re.sub(r'[^a-zA-Z0-9]', '', text2).strip())
        except:
            pass
        
        # Attempt 3: With inverted colors
        try:
            inverted = Image.eval(image, lambda x: 255 - x)
            text3 = pytesseract.image_to_string(
                inverted,
                config='--psm 7 --oem 3'
            )
            captcha_attempts.append(re.sub(r'[^a-zA-Z0-9]', '', text3).strip())
        except:
            pass
        
        print(f"   📝 OCR attempts: {captcha_attempts}")
        
        # Pick the longest result (usually most accurate)
        return max(captcha_attempts, key=len) if captcha_attempts else ""