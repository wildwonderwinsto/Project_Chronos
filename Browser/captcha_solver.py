import asyncio
import io
import re
from pathlib import Path
from typing import Optional, List
from playwright.async_api import Page
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np
from config import FORM_SELECTORS


class CaptchaSolver:
    """CAPTCHA solver with dot removal, letter segmentation, and retry logic"""
    
    def __init__(self, manual_mode: bool = False, max_retries: int = 3):
        self.manual_mode = manual_mode
        self.max_retries = max_retries
        Path("captcha_images").mkdir(exist_ok=True)
    
    async def solve(self, page: Page, log_id: str) -> bool:
        """Solve the CAPTCHA with retry logic"""
        try:
            await page.wait_for_selector('.captcha', timeout=5000)
            
            if self.manual_mode:
                return await self._solve_manually(page)
            
            for attempt in range(self.max_retries):
                attempt_id = f"{log_id}_attempt{attempt}"
                print(f"   🔄 CAPTCHA attempt {attempt + 1}/{self.max_retries}")
                
                captcha_text = await self._ocr_captcha(page, attempt_id)
                
                if captcha_text and len(captcha_text) == 4:
                    print(f"   ✅ CAPTCHA read: '{captcha_text}'")
                    
                    await page.fill(FORM_SELECTORS['captcha'], '')
                    await asyncio.sleep(0.2)
                    await page.fill(FORM_SELECTORS['captcha'], captcha_text)
                    await asyncio.sleep(0.3)
                    
                    filled = await page.input_value(FORM_SELECTORS['captcha'])
                    if filled == captcha_text:
                        print(f"   ✅ CAPTCHA filled successfully")
                        return True
                else:
                    print(f"   ❌ OCR failed or result invalid: '{captcha_text}'")
                
                if attempt < self.max_retries - 1:
                    print(f"   🔄 Refreshing CAPTCHA...")
                    await self._refresh_captcha(page)
                    await asyncio.sleep(0.5)
            
            print(f"   ❌ All CAPTCHA attempts failed")
            return False
                
        except Exception as e:
            print(f"   ❌ CAPTCHA error: {e}")
            return False
    
    async def _refresh_captcha(self, page: Page) -> None:
        """Refresh the CAPTCHA image"""
        try:
            captcha_img = await page.query_selector('.captcha')
            if captcha_img:
                await captcha_img.click()
                await asyncio.sleep(0.3)
        except Exception:
            pass
    
    def _remove_dots_simple(self, image: Image.Image) -> Image.Image:
        """Remove small dot noise using morphological operations"""
        img_array = np.array(image)
        
        kernel_size = 2
        
        # Erode - removes small isolated pixels (dots)
        eroded = img_array.copy()
        for _ in range(kernel_size):
            temp = np.pad(eroded, 1, mode='constant', constant_values=255)
            eroded = np.minimum.reduce([
                temp[:-2, 1:-1], temp[2:, 1:-1],
                temp[1:-1, :-2], temp[1:-1, 2:],
                temp[1:-1, 1:-1]
            ])
        
        # Dilate - restore letter thickness
        dilated = eroded.copy()
        for _ in range(kernel_size + 1):
            temp = np.pad(dilated, 1, mode='constant', constant_values=255)
            dilated = np.maximum.reduce([
                temp[:-2, 1:-1], temp[2:, 1:-1],
                temp[1:-1, :-2], temp[1:-1, 2:],
                temp[1:-1, 1:-1]
            ])
        
        return Image.fromarray(dilated.astype(np.uint8))
    
    def _segment_letters(self, image: Image.Image) -> List[Image.Image]:
        """Segment image by finding actual letter boundaries using vertical projection"""
        img_array = np.array(image)
        height, width = img_array.shape
        
        # Calculate vertical projection (count black pixels per column)
        # Black pixels are 0, white are 255
        projection = np.sum(img_array < 128, axis=0)
        
        # Find letter regions (columns with black pixels)
        threshold = height * 0.05  # At least 5% of column height must be black
        in_letter = projection > threshold
        
        # Find transitions (start/end of letters)
        boundaries = []
        start = None
        
        for i in range(width):
            if in_letter[i] and start is None:
                start = i
            elif not in_letter[i] and start is not None:
                boundaries.append((start, i))
                start = None
        
        # Handle case where last letter extends to edge
        if start is not None:
            boundaries.append((start, width))
        
        # If we found exactly 4 letter regions, use them
        if len(boundaries) == 4:
            letters = []
            padding = 5
            for start, end in boundaries:
                left = max(0, start - padding)
                right = min(width, end + padding)
                letter_img = image.crop((left, 0, right, height))
                letters.append(letter_img)
            return letters
        
        # If letters are touching/merged, try to split merged regions
        if len(boundaries) < 4 and len(boundaries) > 0:
            letters = []
            padding = 5
            
            for start, end in boundaries:
                region_width = end - start
                # Estimate how many letters in this region
                avg_letter_width = width / 4
                num_letters = max(1, round(region_width / avg_letter_width))
                
                if num_letters == 1:
                    left = max(0, start - padding)
                    right = min(width, end + padding)
                    letters.append(image.crop((left, 0, right, height)))
                else:
                    # Split this region into estimated number of letters
                    sub_width = region_width / num_letters
                    for j in range(num_letters):
                        sub_start = int(start + j * sub_width)
                        sub_end = int(start + (j + 1) * sub_width)
                        left = max(0, sub_start - padding)
                        right = min(width, sub_end + padding)
                        letters.append(image.crop((left, 0, right, height)))
            
            # If we got 4 letters, return them
            if len(letters) == 4:
                return letters
        
        # Fallback: equal split if detection failed
        letters = []
        letter_width = width // 4
        padding = 10
        
        for i in range(4):
            start = max(0, i * letter_width - padding)
            end = min(width, (i + 1) * letter_width + padding)
            letters.append(image.crop((start, 0, end, height)))
        
        return letters
    
    def _deskew_letter(self, image: Image.Image) -> Image.Image:
        """Straighten a rotated letter"""
        img_array = np.array(image)
        coords = np.column_stack(np.where(img_array < 128))
        
        if len(coords) < 10:
            return image
        
        try:
            center = coords.mean(axis=0)
            centered = coords - center
            cov = np.cov(centered.T)
            
            if cov.shape == (2, 2):
                eigenvalues, eigenvectors = np.linalg.eig(cov)
                angle = np.degrees(np.arctan2(eigenvectors[0, 1], eigenvectors[0, 0]))
                
                if abs(angle) < 30 and abs(angle) > 2:
                    return image.rotate(-angle, fillcolor=255, expand=False)
        except Exception:
            pass
        
        return image
    
    def _ocr_single_letter(self, image: Image.Image) -> str:
        """OCR a single letter"""
        LETTERS_ONLY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        
        padded = ImageOps.expand(image, border=20, fill=255)
        
        for psm in [10, 8, 13]:
            try:
                text = pytesseract.image_to_string(
                    padded,
                    config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
                ).strip()
                
                cleaned = re.sub(r'[^A-Z]', '', text.upper())
                if cleaned:
                    return self._fix_confusions(cleaned[0])
            except Exception:
                pass
        
        return ''
    
    def _fix_confusions(self, char: str) -> str:
        """Fix common character confusions"""
        fixes = {
            '0': 'O', '1': 'I', '5': 'S', '8': 'B',
            '6': 'G', '2': 'Z', '4': 'A', '7': 'T',
        }
        return fixes.get(char, char)

    async def _ocr_captcha(self, page: Page, log_id: str) -> Optional[str]:
        """OCR the CAPTCHA using multiple methods"""
        try:
            captcha_img = await page.query_selector('.captcha')
            if not captcha_img:
                return None
            
            screenshot_bytes = await captcha_img.screenshot()
            
            with open(f"captcha_images/{log_id}_original.png", 'wb') as f:
                f.write(screenshot_bytes)
            
            image = Image.open(io.BytesIO(screenshot_bytes))
            
            # === PREPROCESSING ===
            width, height = image.size
            image = image.resize((width * 4, height * 4), Image.LANCZOS)
            image = image.convert('L')
            
            # Increase contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Binary threshold
            threshold = 160
            image = image.point(lambda p: 0 if p < threshold else 255)
            
            # Remove dots
            image = self._remove_dots_simple(image)
            
            # Cleanup
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # Ensure black text on white background
            pixels = list(image.getdata())
            if sum(pixels) / len(pixels) < 128:
                image = ImageOps.invert(image)
            
            image.save(f"captcha_images/{log_id}_processed.png")
            
            # === METHOD 1: Letter segmentation ===
            result_segmented = self._try_segmented_ocr(image, log_id)
            if result_segmented and len(result_segmented) == 4:
                print(f"   📝 Segmented: {result_segmented}")
                return result_segmented
            
            # === METHOD 2: Full image OCR ===
            result_full = self._try_full_ocr(image)
            if result_full and len(result_full) == 4:
                print(f"   📝 Full OCR: {result_full}")
                return result_full
            
            # === METHOD 3: Alternate preprocessing ===
            result_alt = self._try_alternate_preprocessing(screenshot_bytes, log_id)
            if result_alt and len(result_alt) == 4:
                print(f"   📝 Alternate: {result_alt}")
                return result_alt
            
            # Return best partial result
            for result in [result_segmented, result_full, result_alt]:
                if result and len(result) >= 3:
                    return result
            
            return None
            
        except Exception as e:
            print(f"   ❌ OCR error: {e}")
            return None
    
    def _try_segmented_ocr(self, image: Image.Image, log_id: str) -> Optional[str]:
        """OCR by segmenting into individual letters"""
        try:
            letters = self._segment_letters(image)
            result = ''
            
            for i, letter_img in enumerate(letters):
                letter_img = self._deskew_letter(letter_img)
                letter_img.save(f"captcha_images/{log_id}_letter{i}.png")
                
                char = self._ocr_single_letter(letter_img)
                if char:
                    result += char
            
            return result if result else None
        except Exception:
            return None
    
    def _try_full_ocr(self, image: Image.Image) -> Optional[str]:
        """OCR on the full image"""
        LETTERS_ONLY = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        best_result = None
        
        for psm in [7, 8, 13, 6]:
            try:
                text = pytesseract.image_to_string(
                    image,
                    config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist={LETTERS_ONLY}'
                )
                cleaned = re.sub(r'[^A-Z]', '', text.upper()).strip()
                
                if len(cleaned) == 4:
                    return cleaned
                
                if cleaned and (best_result is None or len(cleaned) > len(best_result)):
                    best_result = cleaned
                    
            except Exception:
                pass
        
        return best_result[:4] if best_result and len(best_result) > 4 else best_result
    
    def _try_alternate_preprocessing(self, screenshot_bytes: bytes, log_id: str) -> Optional[str]:
        """Try different preprocessing"""
        image = Image.open(io.BytesIO(screenshot_bytes))
        
        width, height = image.size
        image = image.resize((width * 3, height * 3), Image.LANCZOS)
        image = image.convert('L')
        
        # Sharpen to enhance edges
        image = image.filter(ImageFilter.SHARPEN)
        image = image.filter(ImageFilter.SHARPEN)
        
        # Different threshold
        image = image.point(lambda p: 0 if p < 140 else 255)
        
        # Stronger median filter
        image = image.filter(ImageFilter.MedianFilter(size=5))
        
        pixels = list(image.getdata())
        if sum(pixels) / len(pixels) < 128:
            image = ImageOps.invert(image)
        
        image.save(f"captcha_images/{log_id}_alt_processed.png")
        
        return self._try_full_ocr(image)

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
            except Exception:
                pass
        
        return False
