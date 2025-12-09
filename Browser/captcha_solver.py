import asyncio
import io
import re
from pathlib import Path
from typing import List, Tuple, Optional
from playwright.async_api import Page
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from config import FORM_SELECTORS


class CaptchaSolver:
    """Enhanced CAPTCHA solver - LETTERS ONLY, with retry logic"""
    
    def __init__(self, manual_mode: bool = False, debug: bool = False):
        self.manual_mode = manual_mode
        self.debug = debug
        self._ensure_captcha_dir()
        
        # Statistics
        self.total_attempts = 0
        self.total_successes = 0
        self.ocr_results_history = []
    
    def _ensure_captcha_dir(self):
        """Ensure captcha images directory exists"""
        Path("captcha_images").mkdir(exist_ok=True)
    
    async def solve(self, page: Page, log_id: str, max_retries: int = 5) -> bool:
        """
        Solve the CAPTCHA with retry logic
        
        Args:
            page: Playwright page object
            log_id: Log ID for saving debug images
            max_retries: Maximum number of retry attempts (default 5)
            
        Returns:
            True if CAPTCHA solved successfully, False otherwise
        """
        try:
            # Wait for CAPTCHA image to load
            await page.wait_for_selector('.captcha', timeout=5000)
            
            if self.manual_mode:
                return await self._solve_manually(page)
            else:
                return await self._solve_with_retry(page, log_id, max_retries)
                
        except Exception as e:
            print(f"   ❌ CAPTCHA solving error: {e}")
            return False
    
    async def _solve_with_retry(self, page: Page, log_id: str, max_retries: int) -> bool:
        """
        Attempt to solve CAPTCHA with multiple retries
        Uses different preprocessing strategies on each retry
        """
        
        for attempt in range(max_retries):
            self.total_attempts += 1
            
            print(f"   🤖 CAPTCHA attempt {attempt + 1}/{max_retries}...")
            
            # Get CAPTCHA text using OCR
            captcha_text = await self._ocr_captcha(page, log_id, attempt)
            
            if not captcha_text:
                print(f"   ❌ OCR returned empty result")
                if attempt < max_retries - 1:
                    print(f"   🔄 Retrying with different preprocessing...")
                    await asyncio.sleep(1)
                continue
            
            # Validate result length (typical CAPTCHA is 4-8 letters)
            if len(captcha_text) < 3:
                print(f"   ⚠️  Result too short ({len(captcha_text)} chars)")
                if attempt < max_retries - 1:
                    print(f"   🔄 Retrying...")
                    await asyncio.sleep(1)
                continue
            
            if len(captcha_text) > 10:
                print(f"   ⚠️  Result too long ({len(captcha_text)} chars), truncating")
                captcha_text = captcha_text[:8]
            
            # Fill in the CAPTCHA field
            print(f"   ✅ Selected: '{captcha_text}' (length: {len(captcha_text)})")
            
            try:
                # Clear field first
                await page.fill(FORM_SELECTORS['captcha'], '')
                await asyncio.sleep(0.2)
                
                # Fill with OCR result
                await page.fill(FORM_SELECTORS['captcha'], captcha_text)
                print(f"   ✅ CAPTCHA filled successfully")
                
                # Small delay to ensure it's registered
                await asyncio.sleep(0.5)
                
                # Verify it was filled
                filled_value = await page.input_value(FORM_SELECTORS['captcha'])
                if filled_value == captcha_text:
                    self.total_successes += 1
                    self.ocr_results_history.append({
                        'attempt': attempt + 1,
                        'result': captcha_text,
                        'success': True
                    })
                    return True
                else:
                    print(f"   ⚠️  Fill verification failed (expected: '{captcha_text}', got: '{filled_value}')")
                    
            except Exception as e:
                print(f"   ❌ Failed to fill CAPTCHA: {e}")
            
            # If not last attempt, retry
            if attempt < max_retries - 1:
                print(f"   🔄 Retrying CAPTCHA (attempt {attempt + 2}/{max_retries})...")
                await asyncio.sleep(1.5)
        
        # All retries failed
        print(f"   ❌ CAPTCHA failed after {max_retries} attempts")
        self.ocr_results_history.append({
            'attempts': max_retries,
            'success': False
        })
        return False
    
    async def _ocr_captcha(self, page: Page, log_id: str, attempt: int) -> Optional[str]:
        """
        Perform OCR on CAPTCHA image with strategy based on attempt number
        LETTERS ONLY - no numbers
        
        Args:
            page: Playwright page
            log_id: Log ID for debug images
            attempt: Current attempt number (0-based)
            
        Returns:
            CAPTCHA text (letters only) or None if failed
        """
        try:
            # Get the CAPTCHA image element
            captcha_img = await page.query_selector('.captcha')
            if not captcha_img:
                print(f"   ❌ CAPTCHA image not found")
                return None
            
            # Take screenshot of the CAPTCHA
            captcha_screenshot = await captcha_img.screenshot()
            
            # Save original for debugging
            captcha_path = f"captcha_images/{log_id}_attempt{attempt + 1}_original.png"
            with open(captcha_path, 'wb') as f:
                f.write(captcha_screenshot)
            
            # Open with PIL
            image = Image.open(io.BytesIO(captcha_screenshot))
            
            # Use different preprocessing strategy based on attempt
            if attempt == 0:
                preprocessed = self._preprocess_high_contrast(image)
                strategy = "high_contrast"
            elif attempt == 1:
                preprocessed = self._preprocess_ultra_sharp(image)
                strategy = "ultra_sharp"
            elif attempt == 2:
                preprocessed = self._preprocess_denoised(image)
                strategy = "denoised"
            elif attempt == 3:
                preprocessed = self._preprocess_inverted(image)
                strategy = "inverted"
            else:
                preprocessed = self._preprocess_adaptive_threshold(image)
                strategy = "adaptive"
            
            # Save preprocessed image for debugging
            preprocessed_path = f"captcha_images/{log_id}_attempt{attempt + 1}_{strategy}.png"
            preprocessed.save(preprocessed_path)
            
            if self.debug:
                print(f"      📁 Images saved: {captcha_path}, {preprocessed_path}")
            
            # Try multiple OCR configurations
            results = self._ocr_multiple_configs(preprocessed)
            
            if self.debug:
                print(f"      📊 OCR results ({strategy}): {results}")
            
            # Select best result (letters only)
            best_result = self._select_best_result(results)
            
            return best_result
            
        except Exception as e:
            print(f"   ❌ OCR error: {e}")
            return None
    
    def _preprocess_high_contrast(self, image: Image) -> Image:
        """High contrast preprocessing (attempt 1)"""
        # Upscale 4x for better detail
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.LANCZOS)
        
        # Convert to grayscale
        image = image.convert('L')
        
        # Very high contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(4.0)
        
        # Brightness adjustment
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.3)
        
        # Binary threshold
        threshold = 128
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Heavy sharpening
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(3.0)
        
        return image
    
    def _preprocess_ultra_sharp(self, image: Image) -> Image:
        """Ultra sharp preprocessing (attempt 2)"""
        # Upscale 5x
        width, height = image.size
        image = image.resize((width * 5, height * 5), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Unsharp mask filter (brings out edges)
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
        # High contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.5)
        
        # Binary threshold - lower to catch more detail
        threshold = 120
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Edge enhancement
        image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)
        
        return image
    
    def _preprocess_denoised(self, image: Image) -> Image:
        """Denoised preprocessing (attempt 3)"""
        # Upscale 4x
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Smooth to reduce noise FIRST
        image = image.filter(ImageFilter.SMOOTH_MORE)
        
        # Moderate contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.0)
        
        # Median filter to remove salt-and-pepper noise
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        # Binary threshold
        threshold = 130
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Light sharpening
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        return image
    
    def _preprocess_inverted(self, image: Image) -> Image:
        """Inverted colors preprocessing (attempt 4)"""
        # Upscale 4x
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # High contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.5)
        
        # INVERT colors (white becomes black, black becomes white)
        image = ImageOps.invert(image)
        
        # Binary threshold
        threshold = 128
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.5)
        
        return image
    
    def _preprocess_adaptive_threshold(self, image: Image) -> Image:
        """Adaptive threshold preprocessing (attempt 5)"""
        # Upscale 4x
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Strong contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(4.5)
        
        # Try a different threshold value
        threshold = 140
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Denoise
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        # Extra sharpening
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(3.5)
        
        return image
    
    def _ocr_multiple_configs(self, image: Image) -> List[str]:
        """Try multiple OCR configurations - LETTERS ONLY"""
        results = []
        
        # CRITICAL: Whitelist ONLY letters (uppercase and lowercase)
        LETTERS_ONLY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        
        # Config 1: Single line, letters only (BEST FOR CAPTCHA)
        try:
            text = pytesseract.image_to_string(
                image, 
                config=f'--psm 7 --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
            )
            cleaned = re.sub(r'[^a-zA-Z]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 1 failed: {e}")
        
        # Config 2: Single word, letters only
        try:
            text = pytesseract.image_to_string(
                image, 
                config=f'--psm 8 --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
            )
            cleaned = re.sub(r'[^a-zA-Z]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 2 failed: {e}")
        
        # Config 3: Sparse text, letters only
        try:
            text = pytesseract.image_to_string(
                image,
                config=f'--psm 11 --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
            )
            cleaned = re.sub(r'[^a-zA-Z]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 3 failed: {e}")
        
        # Config 4: Uniform block, letters only
        try:
            text = pytesseract.image_to_string(
                image,
                config=f'--psm 6 --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
            )
            cleaned = re.sub(r'[^a-zA-Z]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 4 failed: {e}")
        
        # Config 5: Raw line, letters only
        try:
            text = pytesseract.image_to_string(
                image,
                config=f'--psm 13 --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
            )
            cleaned = re.sub(r'[^a-zA-Z]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 5 failed: {e}")
        
        return results
    
    def _select_best_result(self, results: List[str]) -> Optional[str]:
        """
        Select the best OCR result using multiple criteria
        
        Priority:
        1. Most frequent result (appears 2+ times)
        2. Result with reasonable length (4-7 chars typical)
        3. Longest result that's not too long
        """
        if not results:
            return None
        
        # Count frequencies
        from collections import Counter
        counter = Counter(results)
        
        # If same result appears 2+ times, high confidence
        for result, count in counter.most_common():
            if count >= 2 and 4 <= len(result) <= 8:
                if self.debug:
                    print(f"      ✅ High confidence: '{result}' (appears {count}x)")
                return result
        
        # Filter to reasonable lengths (4-7 chars typical for CAPTCHA)
        reasonable = [r for r in results if 4 <= len(r) <= 7]
        
        if reasonable:
            # Pick most common from reasonable results
            reasonable_counter = Counter(reasonable)
            best = reasonable_counter.most_common(1)[0][0]
            if self.debug:
                print(f"      📊 Reasonable length: '{best}'")
            return best
        
        # Fallback: pick longest result under 10 chars
        filtered = [r for r in results if len(r) <= 10]
        if filtered:
            best = max(filtered, key=len)
            if self.debug:
                print(f"      🔄 Fallback: '{best}' (longest)")
            return best
        
        # Last resort: return first result
        if self.debug:
            print(f"      ⚠️  Last resort: '{results[0]}'")
        return results[0] if results else None
    
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
    
    def get_stats(self) -> dict:
        """Get CAPTCHA solver statistics"""
        success_rate = (self.total_successes / self.total_attempts * 100) if self.total_attempts > 0 else 0
        
        return {
            "mode": "manual" if self.manual_mode else "automatic",
            "debug": self.debug,
            "total_attempts": self.total_attempts,
            "total_successes": self.total_successes,
            "success_rate": round(success_rate, 2),
            "recent_results": self.ocr_results_history[-10:]  # Last 10 results
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self.total_attempts = 0
        self.total_successes = 0
        self.ocr_results_history = []