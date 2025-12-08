import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional
import pytz
from pathlib import Path

# Add Browser to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from Browser.browser_engine import BrowserEngine
from config import SCHEDULING, SCHEDULE_TIMEZONE


class ChronoScheduler:
    """
    The Chrono-Logic Engine
    Manages automated scheduling with circadian rhythm, volume ramp-up, and panic mode
    """
    def _update_bot_status(self):
        """Update bot status in database for dashboard"""
        try:
            from supabase import create_client
            import os
            
            supabase = create_client(
                os.getenv('SUPABASE_URL'),
                os.getenv('SUPABASE_KEY')
            )
            
            # Update or insert status
            status_data = {
                'status': 'PANIC_MODE' if self.in_panic_mode else 'RUNNING',
                'current_mode': self._last_mode if hasattr(self, '_last_mode') else 'DAY',
                'total_attempts': self.total_attempts,
                'total_successes': self.total_successes,
                'total_failures': self.total_failures,
                'consecutive_failures': self.consecutive_failures,
                'last_attempt_time': datetime.now(pytz.timezone(SCHEDULE_TIMEZONE)).isoformat(),
                'target_frequency': self._last_frequency if hasattr(self, '_last_frequency') else 0,
                'updated_at': datetime.now(pytz.timezone(SCHEDULE_TIMEZONE)).isoformat()
            }
            
            # Try to update first
            result = supabase.table('bot_status').select('id').limit(1).execute()
            
            if result.data:
                # Update existing
                supabase.table('bot_status').update(status_data).eq('id', result.data[0]['id']).execute()
            else:
                # Insert new
                supabase.table('bot_status').insert(status_data).execute()
                
        except Exception as e:
            print(f"   ⚠️  Failed to update bot status: {e}") 


    def __init__(self, use_proxies=True, manual_captcha=False):
        self.use_proxies = use_proxies
        self.manual_captcha = manual_captcha
        
        # Tracking
        self.total_attempts = 0
        self.total_successes = 0
        self.total_failures = 0
        self.consecutive_failures = 0
        
        # State
        self.in_panic_mode = False
        self.start_time = datetime.now(pytz.timezone(SCHEDULE_TIMEZONE))
        
        print(f"\n{'='*70}")
        print(f"⏰ CHRONO-LOGIC ENGINE INITIALIZED")
        print(f"{'='*70}")
        print(f"   Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"   Termination: {SCHEDULING['termination_date']} {SCHEDULING['termination_time']}")
        print(f"   Proxies: {'Enabled' if use_proxies else 'Disabled'}")
        print(f"   CAPTCHA: {'Manual' if manual_captcha else 'Automatic OCR'}")
        print(f"{'='*70}\n")
    
    async def run(self):
        """Main scheduling loop"""
        
        print(f"🚀 Starting automated scheduling loop...\n")
        
        while True:
            # Check termination condition
            if self._should_terminate():
                await self._terminate()
                break
            
            # Check panic mode
            if self._should_enter_panic_mode():
                await self._enter_panic_mode()
            
            # Calculate next run time
            delay_seconds = self._calculate_delay()
            
            # Display schedule info
            self._print_status(delay_seconds)
            
            # Wait for next run
            print(f"   ⏳ Sleeping for {self._format_duration(delay_seconds)}...")
            await asyncio.sleep(delay_seconds)
            
            # Run attempt
            await self._run_attempt()
            self._update_bot_status()
    def _should_terminate(self) -> bool:
        """Check if we've reached termination date"""
        now = datetime.now(pytz.timezone(SCHEDULE_TIMEZONE))
        termination_dt = datetime.strptime(
            f"{SCHEDULING['termination_date']} {SCHEDULING['termination_time']}",
            "%Y-%m-%d %H:%M:%S"
        )
        termination_dt = pytz.timezone(SCHEDULE_TIMEZONE).localize(termination_dt)
        
        return now >= termination_dt
    
    async def _terminate(self):
        """Execute termination protocol"""
        print(f"\n{'='*70}")
        print(f"💀 TERMINATION PROTOCOL ACTIVATED")
        print(f"{'='*70}")
        print(f"   Deadline Reached: December 31, 2025 11:59 PM EST")
        print(f"   Total Runtime: {self._format_duration((datetime.now(pytz.timezone(SCHEDULE_TIMEZONE)) - self.start_time).total_seconds())}")
        print(f"\n📊 FINAL STATISTICS:")
        print(f"   Total Attempts: {self.total_attempts}")
        print(f"   Successes: {self.total_successes}")
        print(f"   Failures: {self.total_failures}")
        print(f"   Success Rate: {(self.total_successes / self.total_attempts * 100) if self.total_attempts > 0 else 0:.1f}%")
        print(f"\n🎬 Project Chronos has completed its mission.")
        print(f"{'='*70}\n")
        
        # Could send Discord/email notification here
    
    def _calculate_delay(self) -> float:
        """
        Calculate delay until next attempt based on:
        - Time of day (day/night mode)
        - Date (volume ramp-up)
        - Day of week (weekend boost)
        - Stochastic jitter
        """
        
        now = datetime.now(pytz.timezone(SCHEDULE_TIMEZONE))
        
        # Step 1: Determine base frequency (entries per hour)
        is_day_time = SCHEDULING['day_start_hour'] <= now.hour < SCHEDULING['day_end_hour']
        
        if is_day_time:
            base_frequency = SCHEDULING['day_mode_base_frequency']
            mode = "DAY"
        else:
            base_frequency = SCHEDULING['night_mode_base_frequency']
            mode = "NIGHT"
        
        # Step 2: Apply volume ramp-up multiplier
        ramp_multiplier = self._calculate_ramp_multiplier(now)
        
        # Step 3: Apply weekend boost
        is_weekend = now.weekday() >= 5  # Saturday=5, Sunday=6
        weekend_multiplier = SCHEDULING['weekend_multiplier'] if is_weekend else 1.0
        
        # Step 4: Calculate final frequency
        final_frequency = base_frequency * ramp_multiplier * weekend_multiplier
        
        # Step 5: Convert frequency to delay (seconds between entries)
        # frequency = entries/hour → delay = 3600 / frequency
        base_delay = 3600 / final_frequency
        
        # Step 6: Apply stochastic jitter
        jitter_min = base_delay * SCHEDULING['jitter_min_factor']
        jitter_max = base_delay * SCHEDULING['jitter_max_factor']
        actual_delay = random.uniform(jitter_min, jitter_max)
        
        # Store for status display
        self._last_mode = mode
        self._last_ramp = ramp_multiplier
        self._last_weekend = is_weekend
        self._last_frequency = final_frequency
        
        return actual_delay
    
    def _calculate_ramp_multiplier(self, now: datetime) -> float:
        """
        Calculate volume ramp-up multiplier based on how close we are to deadline
        Returns 1.0 at start, gradually increases to 4.0 near deadline
        """
        
        start_date = datetime.strptime(SCHEDULING['ramp_start_date'], "%Y-%m-%d")
        start_date = pytz.timezone(SCHEDULE_TIMEZONE).localize(start_date)
        
        end_date = datetime.strptime(SCHEDULING['termination_date'], "%Y-%m-%d")
        end_date = pytz.timezone(SCHEDULE_TIMEZONE).localize(end_date)
        
        total_days = (end_date - start_date).days
        days_elapsed = (now - start_date).days
        
        if days_elapsed < 0:
            days_elapsed = 0
        if days_elapsed > total_days:
            days_elapsed = total_days
        
        # Calculate progress (0.0 to 1.0)
        progress = days_elapsed / total_days if total_days > 0 else 0
        
        # Smooth ramp-up curve (quadratic easing)
        # Starts at casual_multiplier, ends at aggressive_multiplier
        casual = SCHEDULING['casual_multiplier']
        aggressive = SCHEDULING['aggressive_multiplier']
        
        # Use sine curve for smooth acceleration
        import math
        curve_progress = math.sin(progress * math.pi / 2)  # 0 to 1, smooth curve
        
        multiplier = casual + (aggressive - casual) * curve_progress
        
        # Final day boost
        if (end_date - now).days == 0:
            multiplier *= SCHEDULING['final_day_multiplier']
        
        return multiplier
    
    def _should_enter_panic_mode(self) -> bool:
        """Check if we should enter panic mode"""
        if self.in_panic_mode:
            return False
        
        return self.consecutive_failures >= SCHEDULING['panic_failure_threshold']
    
    async def _enter_panic_mode(self):
        """Enter panic mode - long cool-down"""
        self.in_panic_mode = True
        
        cooldown_minutes = random.randint(
            SCHEDULING['panic_cooldown_minutes'],
            SCHEDULING['panic_cooldown_max_minutes']
        )
        
        print(f"\n{'='*70}")
        print(f"🚨 PANIC MODE ACTIVATED")
        print(f"{'='*70}")
        print(f"   Reason: {self.consecutive_failures} consecutive failures")
        print(f"   Action: Cooling down for {cooldown_minutes} minutes")
        print(f"   Strategy: Allowing target site's rate limits to reset")
        print(f"{'='*70}\n")
        
        await asyncio.sleep(cooldown_minutes * 60)
        
        print(f"\n✅ Panic mode cool-down complete. Resuming operations...\n")
        
        self.in_panic_mode = False
        self.consecutive_failures = 0  # Reset counter
    
    async def _run_attempt(self):
        """Execute a single attempt"""
        
        print(f"\n{'='*70}")
        print(f"🎬 ATTEMPT #{self.total_attempts + 1}")
        print(f"{'='*70}")
        
        engine = BrowserEngine(
            manual_captcha=self.manual_captcha,
            test_mode=False
        )
        
        success, log_id = await engine.run_single_attempt()
        
        # Update statistics
        self.total_attempts += 1
        
        if success:
            self.total_successes += 1
            self.consecutive_failures = 0
            print(f"✅ Success! (Total: {self.total_successes}/{self.total_attempts})")
        else:
            self.total_failures += 1
            self.consecutive_failures += 1
            print(f"❌ Failed (Consecutive: {self.consecutive_failures})")
        
        print(f"{'='*70}\n")
    
    def _print_status(self, delay_seconds: float):
        """Print current status before sleeping"""
        now = datetime.now(pytz.timezone(SCHEDULE_TIMEZONE))
        next_run = now + timedelta(seconds=delay_seconds)
        
        print(f"\n📊 SCHEDULER STATUS")
        print(f"   Current Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"   Mode: {self._last_mode}")
        print(f"   Ramp Multiplier: {self._last_ramp:.2f}x")
        print(f"   Weekend Boost: {'Yes' if self._last_weekend else 'No'}")
        print(f"   Target Frequency: {self._last_frequency:.2f} entries/hour")
        print(f"   Next Run: {next_run.strftime('%H:%M:%S')}")
        print(f"   Statistics: {self.total_successes}✅ / {self.total_failures}❌ / {self.total_attempts} total")
    
    def _format_duration(self, seconds: float) -> str:
        """Format seconds into human-readable duration"""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            return f"{int(seconds / 60)} minutes"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"


# Test function
async def test_scheduler():
    """Test the scheduler with a few runs"""
    
    print("\n" + "="*70)
    print("🧪 TESTING CHRONO-LOGIC ENGINE")
    print("="*70)
    print("\n⚠️  This will run 3 automated attempts to test scheduling")
    print("   Press Ctrl+C to stop at any time")
    print("\nStarting in 3 seconds...\n")
    
    await asyncio.sleep(3)
    
    scheduler = ChronoScheduler(use_proxies=True, manual_captcha=False)
    
    # Override to run just 3 attempts for testing
    for i in range(3):
        delay = scheduler._calculate_delay()
        scheduler._print_status(delay)
        
        # Shorten delay for testing (max 30 seconds)
        test_delay = min(delay, 30)
        print(f"   ⏳ Test mode: Sleeping for {test_delay:.0f} seconds (normal would be {delay:.0f}s)...\n")
        await asyncio.sleep(test_delay)
        
        await scheduler._run_attempt()
    
    print("\n✅ Scheduler test complete!\n")


async def run_production():
    """Run scheduler in production mode (forever)"""
    
    scheduler = ChronoScheduler(use_proxies=True, manual_captcha=False)
    await scheduler.run()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_scheduler())
    else:
        print("\n⚠️  Starting in PRODUCTION mode - will run until Dec 31, 2025")
        print("   Use 'python scheduler_engine.py test' to run test mode")
        print("   Press Ctrl+C to stop\n")
        
        try:
            asyncio.run(run_production())
        except KeyboardInterrupt:
            print("\n\n⛔ Scheduler stopped by user\n")

#python scheduler_engine.py test
#source .venv/bin/activate