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
                    continue
                
                # Build selector for this action
                selector = f'a[data-action-id="{action_id}"]'
                
                # Check if the action link exists
                element = await page.query_selector(selector)
                
                if not element:
                    print(f"         ⚠️  Action {action_id} link not found")
                    continue
                
                # Click the action
                print(f"         🖱️  Clicking action {action_id}...")
                
                if await self._click_action(page, selector):
                    # Verify it was marked complete
                    if await self._is_already_complete(page, action_id):
                        actions_completed += 1
                        print(f"         ✅ Action {action_id} completed!")
                    else:
                        print(f"         ⚠️  Action {action_id} might not have registered")
                    
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
    
    async def _click_action(self, page: Page, selector: str):
        """Click an action link, handling popup if it opens"""
        try:
            # Try to catch popup and close it
            async with page.expect_popup(timeout=5000) as popup_info:
                await page.click(selector, timeout=3000)
            
            popup = await popup_info.value
            await asyncio.sleep(0.3)
            await popup.close()
            print(f"         ✓ Popup opened and closed")
            
        except Exception:
            # Click might not open popup (might just register)
            print(f"         ℹ️  No popup (might be registered anyway)")
        
        # Wait for the action to register
        await asyncio.sleep(0.5)
        return True