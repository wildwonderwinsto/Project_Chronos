import random
import asyncio
import aiohttp
import json
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pathlib import Path


class ProxyManager:
    """Smart proxy manager - gets proxies in small batches, tests as it goes"""
    
    def __init__(self, min_working_proxies=10):
        self.working_proxies: List[Dict] = []
        self.failed_proxies: Dict[str, datetime] = {}
        self.used_this_session: set = set()
        self.cache_file = Path("working_proxies.json")
        self.min_working_proxies = min_working_proxies
        
        # Failed proxy cooldown - retry after 1 hour
        self.failed_cooldown = timedelta(hours=1)
        
        self._load_cache()
    
    def _load_cache(self):
        """Load cached proxies"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.working_proxies = data.get('proxies', [])
                    self.working_proxies = [p for p in self.working_proxies if self._validate_proxy(p)]
                    print(f"   📦 Loaded {len(self.working_proxies)} cached proxies")
            except Exception as e:
                print(f"   ⚠️  Cache load failed: {e}")
                self.working_proxies = []
    
    def _validate_proxy(self, proxy: Dict) -> bool:
        """Check proxy has required fields"""
        required = ['server', 'ip', 'country', 'city', 'state', 'timezone']
        return all(key in proxy for key in required)
    
    def _save_cache(self):
        """Save proxies to cache"""
        try:
            sorted_proxies = sorted(
                self.working_proxies,
                key=lambda p: (p.get('state', ''), p.get('city', ''))
            )
            with open(self.cache_file, 'w') as f:
                json.dump({
                    'last_updated': datetime.now().isoformat(),
                    'total_proxies': len(sorted_proxies),
                    'proxies': sorted_proxies
                }, f, indent=2)
        except Exception as e:
            print(f"   ⚠️  Cache save failed: {e}")
    
    def _clean_failed_proxies(self):
        """Remove old entries from failed proxies"""
        now = datetime.now()
        expired = [k for k, v in self.failed_proxies.items() if now - v > self.failed_cooldown]
        for k in expired:
            del self.failed_proxies[k]
    
    async def get_proxy(self) -> Optional[Dict]:
        """Get a proxy - refreshes if needed"""
        self._clean_failed_proxies()
        
        # Get available proxies
        available = [
            p for p in self.working_proxies
            if p['server'] not in self.failed_proxies
            and p['server'] not in self.used_this_session
        ]
        
        # If none available, reset session
        if not available:
            self.used_this_session.clear()
            available = [
                p for p in self.working_proxies
                if p['server'] not in self.failed_proxies
            ]
        
        # If still not enough, get more
        if len(available) < self.min_working_proxies:
            print(f"   ⚠️  Only {len(available)} proxies available, getting more...")
            await self._get_batch_of_proxies(batch_size=50)
            
            # Refresh available list
            available = [
                p for p in self.working_proxies
                if p['server'] not in self.failed_proxies
                and p['server'] not in self.used_this_session
            ]
        
        if not available:
            return None
        
        proxy = random.choice(available)
        self.used_this_session.add(proxy['server'])
        return proxy
    
    async def _get_batch_of_proxies(self, batch_size=50):
        """Get a small batch of proxies, enrich them, and add to working list"""
        print(f"   🔄 Fetching batch of {batch_size} new proxies...")
        
        async with aiohttp.ClientSession() as session:
            # Scrape proxies
            results = await asyncio.gather(
                self._scrape_proxyscrape(session),
                self._scrape_geonode(session),
                self._scrape_proxylist_download(session),
                return_exceptions=True
            )
        
        # Collect
        all_proxies = []
        for result in results:
            if isinstance(result, list):
                all_proxies.extend(result)
        
        # Dedupe
        seen_ips = {p['ip'] for p in self.working_proxies}
        new_proxies = []
        for p in all_proxies:
            if p['ip'] not in seen_ips and p['server'] not in self.failed_proxies:
                seen_ips.add(p['ip'])
                new_proxies.append(p)
        
        if not new_proxies:
            print(f"   ❌ No new proxies found!")
            return
        
        # Limit to batch size
        new_proxies = new_proxies[:batch_size]
        print(f"   📊 Got {len(new_proxies)} new proxies to check")
        
        # Enrich with GeoIP (small batches)
        enriched = []
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(new_proxies), 10):
                batch = new_proxies[i:i+10]
                
                tasks = [self._enrich_proxy(session, p) for p in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, dict) and result.get('country') == 'US':
                        enriched.append(result)
                
                # Rate limit
                if i + 10 < len(new_proxies):
                    await asyncio.sleep(1.5)
        
        print(f"   ✅ Added {len(enriched)} US proxies")
        self.working_proxies.extend(enriched)
        self._save_cache()
    
    async def _enrich_proxy(self, session: aiohttp.ClientSession, proxy: Dict) -> Dict:
        """Add GeoIP data"""
        defaults = {
            'country': 'US',
            'city': 'Unknown',
            'state': 'Unknown',
            'timezone': 'America/New_York',
            'isp': 'Unknown'
        }
        
        try:
            url = f"http://ip-api.com/json/{proxy['ip']}?fields=status,countryCode,regionName,city,timezone,isp"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('status') == 'success':
                        return {
                            **proxy,
                            'country': data.get('countryCode', 'US'),
                            'city': data.get('city', 'Unknown'),
                            'state': data.get('regionName', 'Unknown'),
                            'timezone': data.get('timezone', 'America/New_York'),
                            'isp': data.get('isp', 'Unknown')
                        }
        except Exception:
            pass
        
        return {**proxy, **defaults}
    
    async def _fetch_url(self, session: aiohttp.ClientSession, url: str, timeout: int = 10) -> Optional[str]:
        """Fetch URL"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            pass
        return None
    
    async def _scrape_proxyscrape(self, session: aiohttp.ClientSession) -> List[Dict]:
        """ProxyScrape API"""
        proxies = []
        try:
            url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=US&ssl=yes&anonymity=all"
            text = await self._fetch_url(session, url)
            if text:
                for line in text.strip().split('\n')[:100]:  # Limit to 100
                    if ':' in line:
                        parts = line.strip().split(':')
                        if len(parts) == 2:
                            ip, port = parts[0], parts[1]
                            if ip and port.isdigit():
                                proxies.append({'server': f'http://{ip}:{port}', 'ip': ip})
            print(f"      ✓ proxyscrape: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ proxyscrape: {e}")
        return proxies
    
    async def _scrape_geonode(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Geonode API"""
        proxies = []
        try:
            url = "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc&country=US&protocols=http%2Chttps"
            text = await self._fetch_url(session, url, timeout=15)
            if text:
                data = json.loads(text)
                for p in data.get('data', [])[:100]:  # Limit to 100
                    ip = p.get('ip')
                    port = p.get('port')
                    if ip and port:
                        proxies.append({'server': f"http://{ip}:{port}", 'ip': ip})
            print(f"      ✓ geonode: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ geonode: {e}")
        return proxies
    
    async def _scrape_proxylist_download(self, session: aiohttp.ClientSession) -> List[Dict]:
        """proxy-list.download"""
        proxies = []
        try:
            url = "https://www.proxy-list.download/api/v1/get?type=http&country=US"
            text = await self._fetch_url(session, url)
            if text:
                for line in text.strip().split('\n')[:100]:  # Limit to 100
                    if ':' in line:
                        parts = line.strip().split(':')
                        if len(parts) == 2:
                            ip, port = parts[0], parts[1]
                            if ip and port.isdigit():
                                proxies.append({'server': f'http://{ip}:{port}', 'ip': ip})
            print(f"      ✓ proxy-list.download: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ proxy-list.download: {e}")
        return proxies
    
    def mark_proxy_failed(self, proxy_server: str):
        """Mark proxy as failed"""
        self.failed_proxies[proxy_server] = datetime.now()
        self.working_proxies = [p for p in self.working_proxies if p['server'] != proxy_server]
        self._save_cache()
    
    def mark_proxy_success(self, proxy_server: str):
        """Mark proxy as successful"""
        if proxy_server in self.failed_proxies:
            del self.failed_proxies[proxy_server]