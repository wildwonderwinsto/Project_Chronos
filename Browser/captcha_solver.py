import asyncio
import io
import re
from pathlib import Path
from typing import List, Tuple
from playwright.async_api import Page
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from config import FORM_SELECTORS


class CaptchaSolver:
    """Enhanced CAPTCHA solver - improved but not over-engineered"""
    
    def __init__(self, manual_mode: bool = False, debug: bool = False):
        self.manual_mode = manual_mode
        self.debug = debug
        self._ensure_captcha_dir()
    
    def _ensure_captcha_dir(self):
        """Ensure captcha images directory exists"""
        Path("captcha_images").mkdir(exist_ok=True)
    
    async def solve(self, page: Page, log_id: str) -> bool:
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
    
    async def _solve_manually(self, page: Page) -> bool:
        """Manual CAPTCHA solving - wait for user input"""
        print(f"   🖐️  MANUAL CAPTCHA MODE")
        print(f"   👀 Browser is visible - please solve the CAPTCHA")
        print(f"   ⏳ Waiting for you to type the CAPTCHA text...")
        
        # Wait for user to fill in the captcha field (up to 60 seconds)
        for i in range(60):
            await asyncio.sleep(1)
            
            try:
                captcha_value = await page.input_value(FORM_SELECTORS['captcha'])
                if captcha_value and len(captcha_value) > 0:
                    print(f"   ✅ CAPTCHA entered: {captcha_value}")
                    return True
            except:
                pass
        
        print(f"   ⏰ Timeout waiting for manual CAPTCHA input")
        return False
    
    async def _solve_with_ocr(self, page: Page, log_id: str) -> bool:
        """Automatic CAPTCHA solving using OCR"""
        print(f"   🤖 Attempting automatic OCR...")
        
        # Get the CAPTCHA image element
        captcha_img = await page.query_selector('.captcha')
        if not captcha_img:
            print(f"   ❌ CAPTCHA image not found")
            return False
        
        # Take screenshot of the CAPTCHA
        captcha_screenshot = await captcha_img.screenshot()
        
        # Save original
        captcha_path = f"captcha_images/{log_id}_original.png"
        with open(captcha_path, 'wb') as f:
            f.write(captcha_screenshot)
        
        # Load image
        image = Image.open(io.BytesIO(captcha_screenshot))
        
        # Try 3 preprocessing approaches (not too many)
        preprocessed_images = self._create_preprocessing_variants(image, log_id)
        
        # Collect all OCR results
        all_results = []
        for variant, name in preprocessed_images:
            results = self._ocr_multiple_attempts(variant)
            if self.debug:
                print(f"   📊 {name}: {results}")
            all_results.extend(results)
        
        # Select best result
        captcha_text = self._select_best_result(all_results)
        
        print(f"   ✅ Selected: '{captcha_text}' (length: {len(captcha_text)})")
        
        if len(captcha_text) == 0:
            print(f"   ❌ OCR failed - no valid result")
            print(f"   📁 Check: {captcha_path}")
            return False
        
        if len(captcha_text) < 4:
            print(f"   ⚠️  Short result - may be incorrect")
        
        # Fill in the CAPTCHA field
        await page.fill(FORM_SELECTORS['captcha'], captcha_text)
        print(f"   ✅ CAPTCHA filled")
        
        await asyncio.sleep(0.5)
        return True
    
    def _create_preprocessing_variants(self, image: Image, log_id: str) -> List[Tuple[Image.Image, str]]:
        """Create 3 good preprocessing variants"""
        variants = []
        
        # Variant 1: Original approach (what was working)
        original = self._preprocess_original(image)
        variants.append((original, "original"))
        if self.debug:
            original.save(f"captcha_images/{log_id}_1_original.png")
        
        # Variant 2: Higher upscale + threshold
        upscaled = self._preprocess_upscaled(image)
        variants.append((upscaled, "upscaled"))
        if self.debug:
            upscaled.save(f"captcha_images/{log_id}_2_upscaled.png")
        
        # Variant 3: Denoised version
        clean = self._preprocess_clean(image)
        variants.append((clean, "clean"))
        if self.debug:
            clean.save(f"captcha_images/{log_id}_3_clean.png")
        
        return variants
    
    def _preprocess_original(self, image: Image) -> Image:
        """Original preprocessing that was working"""
        # Upscale 3x
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Contrast boost
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.0)
        
        # Brightness
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.2)
        
        # Threshold
        threshold = 140
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        return image
    
    def _preprocess_upscaled(self, image: Image) -> Image:
        """Higher resolution + different threshold"""
        # Upscale 4x
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Strong contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.5)
        
        # Different threshold
        threshold = 130
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.5)
        
        return image
    
    def _preprocess_clean(self, image: Image) -> Image:
        """Noise reduction version"""
        # Upscale 3x
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Light smoothing to reduce noise
        image = image.filter(ImageFilter.SMOOTH_MORE)
        
        # Contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.8)
        
        # Threshold
        threshold = 135
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Clean up with mode filter
        image = image.filter(ImageFilter.ModeFilter(size=3))
        
        return image
    
    def _ocr_multiple_attempts(self, image: Image) -> List[str]:
        """Try multiple OCR configs - keep what works"""
        results = []
        
        # Attempt 1: Single line, alphanumeric only (BEST)
        try:
            text = pytesseract.image_to_string(
                image, 
                config='--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except:
            pass
        
        # Attempt 2: Single word
        try:
            text = pytesseract.image_to_string(
                image, 
                config='--psm 8 --oem 3'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except:
            pass
        
        # Attempt 3: Treat as uniform block
        try:
            text = pytesseract.image_to_string(
                image,
                config='--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except:
            pass
        
        return results
    
    def _select_best_result(self, all_results: List[str]) -> str:
        """Pick the best result - prefer consistency and reasonable length"""
        if not all_results:
            return ""
        
        # Count frequencies
        from collections import Counter
        counter = Counter(all_results)
        
        if self.debug:
            print(f"   📈 All results: {counter.most_common()}")
        
        # If same result appears 2+ times, use it
        for result, count in counter.most_common():
            if count >= 2 and 4 <= len(result) <= 8:
                return result
        
        # Filter to reasonable lengths (4-8 chars typical for captcha)
        reasonable = [r for r in all_results if 4 <= len(r) <= 8]
        
        if reasonable:
            # Pick most common from reasonable results
            reasonable_counter = Counter(reasonable)
            return reasonable_counter.most_common(1)[0][0]
        
        # Fallback: pick longest (but not crazy long)
        filtered = [r for r in all_results if len(r) <= 10]
        return max(filtered, key=len) if filtered else ""
    
    def get_stats(self) -> dict:
        """Get statistics about captcha solving"""
        return {
            "mode": "manual" if self.manual_mode else "automatic",
            "debug": self.debug
        }