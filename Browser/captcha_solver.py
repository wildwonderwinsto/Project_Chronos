import asyncio
import io
import re
from pathlib import Path
from typing import List, Tuple, Optional
from playwright.async_api import Page
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from config import FORM_SELECTORS


class CaptchaSolver:
    """Enhanced CAPTCHA solver with automatic retry logic"""
    
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
    
    async def solve(self, page: Page, log_id: str, max_retries: int = 3) -> bool:
        """
        Solve the CAPTCHA with retry logic
        
        Args:
            page: Playwright page object
            log_id: Log ID for saving debug images
            max_retries: Maximum number of retry attempts
            
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
            
            # Validate result length
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
                    print(f"   ⚠️  Fill verification failed")
                    
            except Exception as e:
                print(f"   ❌ Failed to fill CAPTCHA: {e}")
            
            # If not last attempt, retry
            if attempt < max_retries - 1:
                print(f"   🔄 Retrying CAPTCHA (attempt {attempt + 2}/{max_retries})...")
                
                # Clear the field before retry
                try:
                    await page.fill(FORM_SELECTORS['captcha'], '')
                except:
                    pass
                
                await asyncio.sleep(1)
        
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
        
        Args:
            page: Playwright page
            log_id: Log ID for debug images
            attempt: Current attempt number (0-based)
            
        Returns:
            CAPTCHA text or None if failed
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
                # First attempt: Standard preprocessing
                preprocessed = self._preprocess_standard(image)
                strategy = "standard"
            elif attempt == 1:
                # Second attempt: Aggressive preprocessing
                preprocessed = self._preprocess_aggressive(image)
                strategy = "aggressive"
            else:
                # Third+ attempt: Clean preprocessing
                preprocessed = self._preprocess_clean(image)
                strategy = "clean"
            
            # Save preprocessed image for debugging
            preprocessed_path = f"captcha_images/{log_id}_attempt{attempt + 1}_{strategy}.png"
            preprocessed.save(preprocessed_path)
            
            if self.debug:
                print(f"      📁 Images saved: {captcha_path}, {preprocessed_path}")
            
            # Try multiple OCR configurations
            results = self._ocr_multiple_configs(preprocessed)
            
            if self.debug:
                print(f"      📊 OCR results ({strategy}): {results}")
            
            # Select best result
            best_result = self._select_best_result(results)
            
            return best_result
            
        except Exception as e:
            print(f"   ❌ OCR error: {e}")
            return None
    
    def _preprocess_standard(self, image: Image) -> Image:
        """Standard preprocessing (first attempt)"""
        # Upscale 3x
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.0)
        
        # Enhance brightness
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.2)
        
        # Threshold
        threshold = 140
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        return image
    
    def _preprocess_aggressive(self, image: Image) -> Image:
        """Aggressive preprocessing (second attempt)"""
        # Upscale 4x (higher resolution)
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Very strong contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(4.0)
        
        # Lower threshold (catch more detail)
        threshold = 130
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Extra sharpening
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(3.0)
        
        # Denoise with median filter
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        return image
    
    def _preprocess_clean(self, image: Image) -> Image:
        """Clean preprocessing with noise reduction (third attempt)"""
        # Upscale 3x
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.LANCZOS)
        
        # Grayscale
        image = image.convert('L')
        
        # Smooth first to reduce noise
        image = image.filter(ImageFilter.SMOOTH_MORE)
        
        # Moderate contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.5)
        
        # Mid-range threshold
        threshold = 135
        image = image.point(lambda p: 0 if p < threshold else 255)
        
        # Clean up with mode filter (removes salt-and-pepper noise)
        image = image.filter(ImageFilter.ModeFilter(size=3))
        
        # Light sharpening
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.5)
        
        return image
    
    def _ocr_multiple_configs(self, image: Image) -> List[str]:
        """Try multiple OCR configurations"""
        results = []
        
        # Config 1: Single line, alphanumeric only (BEST FOR CAPTCHA)
        try:
            text = pytesseract.image_to_string(
                image, 
                config='--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 1 failed: {e}")
        
        # Config 2: Single word
        try:
            text = pytesseract.image_to_string(
                image, 
                config='--psm 8 --oem 3'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 2 failed: {e}")
        
        # Config 3: Sparse text
        try:
            text = pytesseract.image_to_string(
                image,
                config='--psm 11 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 3 failed: {e}")
        
        # Config 4: Uniform block
        try:
            text = pytesseract.image_to_string(
                image,
                config='--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', text).strip()
            if cleaned and len(cleaned) >= 3:
                results.append(cleaned)
        except Exception as e:
            if self.debug:
                print(f"      ⚠️  Config 4 failed: {e}")
        
        return results
    
    def _select_best_result(self, results: List[str]) -> Optional[str]:
        """
        Select the best OCR result using multiple criteria
        
        Priority:
        1. Most frequent result (appears 2+ times)
        2. Result with reasonable length (4-8 chars)
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
        
        # Filter to reasonable lengths (4-8 chars typical for CAPTCHA)
        reasonable = [r for r in results if 4 <= len(r) <= 8]
        
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
        return results[0]
    
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


# Example usage
async def test_captcha_solver():
    """Test the CAPTCHA solver"""
    from playwright.async_api import async_playwright
    
    solver = CaptchaSolver(manual_mode=False, debug=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Navigate to your target URL
        await page.goto("YOUR_URL_HERE")
        
        # Try to solve CAPTCHA with 3 retries
        success = await solver.solve(page, "test_log_id", max_retries=3)
        
        print(f"\n{'='*70}")
        print(f"CAPTCHA SOLVER TEST RESULTS")
        print(f"{'='*70}")
        print(f"Success: {success}")
        print(f"Stats: {solver.get_stats()}")
        print(f"{'='*70}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_captcha_solver())