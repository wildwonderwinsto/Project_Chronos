import asyncio
from playwright.async_api import Page


class SocialActionsHandler:
    """Handles social action links (Instagram, TikTok, Facebook, etc.)"""
    
    # Action IDs from the HTML
    ACTION_IDS = ['1765', '1766', '1767', '1768', '1769', '1770', '1771', '1772']
    
    async def handle_actions(self, page: Page):
        """Click social action links to mark them as complete"""
        actions_completed = 0
        
        print(f"      🔗 Processing {len(self.ACTION_IDS)} social actions...")
        
        for action_id in self.ACTION_IDS:
            try:
                if await self._is_already_complete(page, action_id):
                    print(f"         ✓ Action {action_id} already complete")
                    actions_completed += 1
                    continue
                
                # Build selector for this action
                selector = f'a[data-action-id="{action_id}"]'
                
                # Check if the action link exists
                element = await page.query_selector(selector)
                
                if not element:
                    print(f"         ⚠️  Action {action_id} link not found")
                    continue
                
                # Click the action - fast version
                print(f"         🖱️  Clicking action {action_id}...")
                
                if await self._click_action_fast(page, selector, action_id):
                    actions_completed += 1
                    
            except Exception as e:
                print(f"         ❌ Error with action {action_id}: {str(e)[:50]}")
                continue
        
        print(f"      📊 Completed {actions_completed}/{len(self.ACTION_IDS)} social actions")
    
    async def _is_already_complete(self, page: Page, action_id: str):
        """Check if an action is already marked as complete"""
        return await page.evaluate(f'''
            () => {{
                const tick = document.getElementById('tick_{action_id}');
                if (tick) {{
                    const style = window.getComputedStyle(tick);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                }}
                return false;
            }}
        ''')
    
    async def _click_action_fast(self, page: Page, selector: str, action_id: str):
        """Click action and immediately close popup without waiting for load"""
        try:
            # Start listening for popup
            popup_promise = page.wait_for_event('popup', timeout=2000)
            
            # Click the link
            await page.click(selector, timeout=2000)
            
            # Try to get and close popup immediately
            try:
                popup = await popup_promise
                # Don't wait for load, just close immediately
                await popup.close()
            except:
                # Popup might not have opened or already closed
                pass
            
            # Small delay to let action register
            await asyncio.sleep(0.3)
            
            # Check if it registered
            if await self._is_already_complete(page, action_id):
                print(f"         ✅ Action {action_id} completed!")
                return True
            else:
                print(f"         ℹ️  Action {action_id} clicked (might register)")
                return True  # Count it anyway since we clicked
                
        except Exception as e:
            print(f"         ℹ️  Action {action_id} click attempted")
            return False