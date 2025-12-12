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
    
    def _apply_adaptive_threshold(self, image: Image.Image) -> Image.Image:
        """Apply adaptive thresholding using local pixel analysis"""
        import numpy as np
        img_array = np.array(image)
        
        # Calculate local threshold using block mean
        block_size = 15
        h, w = img_array.shape
        output = np.zeros_like(img_array)
        
        for i in range(h):
            for j in range(w):
                # Define local region
                y1 = max(0, i - block_size // 2)
                y2 = min(h, i + block_size // 2 + 1)
                x1 = max(0, j - block_size // 2)
                x2 = min(w, j + block_size // 2 + 1)
                
                local_mean = np.mean(img_array[y1:y2, x1:x2])
                # Threshold with offset for better text detection
                threshold = local_mean - 10
                output[i, j] = 255 if img_array[i, j] > threshold else 0
        
        return Image.fromarray(output)
    
    def _fix_common_confusions(self, text: str) -> str:
        """Fix common OCR character confusions for uppercase letters"""
        # Common misreads in CAPTCHA OCR
        fixes = {
            '0': 'O', '1': 'I', '5': 'S', '8': 'B',
            '6': 'G', '2': 'Z', '4': 'A', '7': 'T',
        }
        result = ''
        for char in text.upper():
            result += fixes.get(char, char)
        return result

    async def _ocr_captcha(self, page: Page, log_id: str) -> Optional[str]:
        """
        Read CAPTCHA optimized for 4-letter uppercase CAPTCHAs
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
            
            # === IMPROVED PREPROCESSING FOR 4-LETTER CAPTCHA ===
            
            # 1. Upscale 4x for better detail preservation
            width, height = image.size
            image = image.resize((width * 4, height * 4), Image.LANCZOS)
            
            # 2. Convert to grayscale
            image = image.convert('L')
            
            # 3. Sharpen BEFORE noise removal to preserve edges
            image = image.filter(ImageFilter.SHARPEN)
            image = image.filter(ImageFilter.SHARPEN)
            
            # 4. Light noise removal
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # 5. Moderate contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.8)
            
            # 6. Brightness adjustment
            brightness = ImageEnhance.Brightness(image)
            image = brightness.enhance(1.1)
            
            # 7. Apply adaptive thresholding
            image = self._apply_adaptive_threshold(image)
            
            # 8. Morphological cleanup - erode then dilate to remove noise
            image = image.filter(ImageFilter.MinFilter(size=3))
            image = image.filter(ImageFilter.MaxFilter(size=3))
            
            # 9. Final cleanup
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # 10. Ensure black text on white background
            pixels = list(image.getdata())
            if sum(pixels) / len(pixels) < 128:
                image = Image.eval(image, lambda x: 255 - x)
            
            # Save preprocessed
            processed_path = f"captcha_images/{log_id}_processed.png"
            image.save(processed_path)
            
            # === OCR - EXACTLY 4 UPPERCASE LETTERS ===
            LETTERS_ONLY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            best_result = None
            best_confidence = 0
            
            # Try multiple PSM modes with different configs
            configs = [
                (7, '--oem 3'),   # Single text line
                (8, '--oem 3'),   # Single word
                (13, '--oem 3'),  # Raw line
                (6, '--oem 3'),   # Uniform block
                (7, '--oem 1'),   # LSTM only
                (8, '--oem 1'),
            ]
            
            for psm, oem_config in configs:
                try:
                    # Get text with confidence data
                    data = pytesseract.image_to_data(
                        image,
                        config=f'--psm {psm} {oem_config} -c tessedit_char_whitelist={LETTERS_ONLY}',
                        output_type=pytesseract.Output.DICT
                    )
                    
                    # Extract text and confidence
                    texts = [t for t in data['text'] if t.strip()]
                    confs = [c for c, t in zip(data['conf'], data['text']) if t.strip() and c != -1]
                    
                    if texts:
                        raw_text = ''.join(texts)
                        cleaned = re.sub(r'[^A-Z0-9]', '', raw_text.upper()).strip()
                        cleaned = self._fix_common_confusions(cleaned)
                        avg_conf = sum(confs) / len(confs) if confs else 0
                        
                        # Perfect match - exactly 4 letters with good confidence
                        if len(cleaned) == 4 and avg_conf > 60:
                            return cleaned
                        
                        # Track best result
                        if len(cleaned) >= 3 and (avg_conf > best_confidence or 
                            (abs(len(cleaned) - 4) < abs(len(best_result or '') - 4))):
                            best_result = cleaned
                            best_confidence = avg_conf
                        
                except Exception:
                    pass
            
            # Fallback: simple string extraction
            for psm in [7, 8, 13]:
                try:
                    text = pytesseract.image_to_string(
                        image,
                        config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}0123456789'
                    )
                    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper()).strip()
                    cleaned = self._fix_common_confusions(cleaned)
                    
                    if len(cleaned) == 4:
                        return cleaned
                    
                    if cleaned and (best_result is None or abs(len(cleaned) - 4) < abs(len(best_result) - 4)):
                        best_result = cleaned
                except Exception:
                    pass
            
            # Return best result, adjusted to 4 chars
            if best_result:
                if len(best_result) > 4:
                    return best_result[:4]
                elif len(best_result) == 3:
                    print(f"   ⚠️  Only got 3 letters: {best_result}")
                    return best_result
                elif len(best_result) == 4:
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