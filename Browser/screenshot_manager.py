from playwright.async_api import Page


class ScreenshotManager:
    """Handles screenshot capture for debugging"""
    
    async def capture(self, page: Page, log_id: str):
        """
        Capture screenshot for debugging
        Returns: filename or None if failed
        """
        try:
            filename = f"screenshots/{log_id}.png"
            await page.screenshot(path=filename, full_page=True)
            print(f"      📸 Screenshot saved: {filename}")
            return filename
        except Exception as e:
            print(f"      ⚠️  Failed to capture screenshot: {e}")
            return None