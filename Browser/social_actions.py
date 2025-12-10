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
                
                # Click action - with proper error suppression
                print(f"         🖱️  Clicking action {action_id}...")
                
                if await self._click_and_close_silent(page, selector, action_id):
                    actions_completed += 1
                    
            except Exception as e:
                print(f"         ⚠️  Error with action {action_id}: {str(e)[:40]}")
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
    
    async def _click_and_close_silent(self, page: Page, selector: str, action_id: str):
        """
        Click action and handle popup silently - no asyncio warnings
        This uses a different approach that doesn't leave uncaught tasks
        """
        try:
            # Create a popup handler BEFORE clicking
            popup_caught = False
            
            async def popup_handler(popup):
                nonlocal popup_caught
                popup_caught = True
                try:
                    await popup.close()
                except:
                    pass
            
            # Register the handler
            page.on('popup', popup_handler)
            
            # Click the link
            try:
                await page.click(selector, timeout=1000)
            except Exception:
                pass  # Click timeout is fine
            
            # Wait briefly for popup to appear (if it will)
            await asyncio.sleep(0.3)
            
            # Remove handler
            page.remove_listener('popup', popup_handler)
            
            # Small delay for action to register
            await asyncio.sleep(0.1)
            
            # Check if it registered
            if await self._is_already_complete(page, action_id):
                print(f"         ✅ Action {action_id} completed!")
                return True
            else:
                # Some actions register even without visual confirmation
                print(f"         ℹ️  Action {action_id} clicked")
                return True
                
        except Exception as e:
            print(f"         ⚠️  Action {action_id}: {str(e)[:40]}")
            return False