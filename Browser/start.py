import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now import without dots
from Browser.browser_engine import BrowserEngine


async def test_auto_mode():
    """Test with automatic OCR CAPTCHA solving"""
    
    print("\n" + "="*70)
    print("🧪 TESTING BROWSER ENGINE - AUTOMATIC OCR MODE")
    print("="*70)
    print("\n⚠️  Make sure you have pytesseract installed:")
    print("     pip install pytesseract pillow")
    print("     (Also install Tesseract OCR on your system)")
    print("\nStarting test in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    engine = BrowserEngine(manual_captcha=False, test_mode=False)
    success, log_id = await engine.run_single_attempt()
    
    print("\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    print(f"   Success: {success}")
    print(f"   Log ID: {log_id}")
    print("\n✅ Check Supabase and captcha_images/ folder!")
    print("="*70)


async def test_manual_mode():
    """Test with manual CAPTCHA solving"""
    
    print("\n" + "="*70)
    print("🧪 TESTING BROWSER ENGINE - MANUAL CAPTCHA MODE")
    print("="*70)
    print("\n🖐️  Browser will stay open for you to solve CAPTCHA manually")
    print("   Just type the CAPTCHA text and the bot will continue")
    print("\nStarting test in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    engine = BrowserEngine(manual_captcha=True, test_mode=False)
    success, log_id = await engine.run_single_attempt()
    
    print("\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    print(f"   Success: {success}")
    print(f"   Log ID: {log_id}")
    print("\n✅ Check Supabase to see the logged attempt!")
    print("="*70)


async def test_dry_run():
    """Test mode - fills form but DOESN'T submit (for testing)"""
    
    print("\n" + "="*70)
    print("🧪 DRY RUN MODE - NO SUBMISSION")
    print("="*70)
    print("\n✅ This will fill the form but NOT submit it")
    print("   Browser stays open for 30 seconds so you can inspect")
    print("   No database logs are created")
    print("\nStarting test in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    engine = BrowserEngine(manual_captcha=False, test_mode=True)
    success, log_id = await engine.run_single_attempt()
    
    print("\n" + "="*70)
    print("📊 DRY RUN COMPLETE")
    print("="*70)
    print(f"   Form filled successfully: {success}")
    print("\n✅ Check captcha_images/ to see OCR results!")
    print("="*70)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "manual":
            asyncio.run(test_manual_mode())
        elif mode == "test":
            asyncio.run(test_dry_run())
        else:
            print("❌ Unknown mode. Use: manual, test, or no argument for auto")
            print("\nAvailable commands:")
            print("  python test_runners.py          # Auto OCR mode (submits)")
            print("  python test_runners.py manual   # Manual CAPTCHA mode (submits)")
            print("  python test_runners.py test     # Dry run mode (NO submit)")
    else:
        asyncio.run(test_auto_mode())

#python Browser/start.py test