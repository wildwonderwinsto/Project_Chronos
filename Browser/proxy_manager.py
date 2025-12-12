import random
import asyncio
import aiohttp
import json
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pathlib import Path


class ProxyManager:
    """Improved proxy manager with better scraping and smarter caching"""
    
    def __init__(self):
        self.working_proxies: List[Dict] = []
        self.failed_proxies: Dict[str, datetime] = {}  # Track when proxy failed
        self.used_this_session: set = set()
        self.cache_file = Path("working_proxies.json")
        self.last_refresh = None
        
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
        """Remove old entries from failed proxies (allow retry after cooldown)"""
        now = datetime.now()
        expired = [k for k, v in self.failed_proxies.items() if now - v > self.failed_cooldown]
        for k in expired:
            del self.failed_proxies[k]
    
    async def get_proxy(self) -> Optional[Dict]:
        """Get a proxy to use"""
        self._clean_failed_proxies()
        
        # Get available proxies (not failed, not used this session)
        available = [
            p for p in self.working_proxies
            if p['server'] not in self.failed_proxies
            and p['server'] not in self.used_this_session
        ]
        
        # If none available, reset session usage
        if not available:
            self.used_this_session.clear()
            available = [
                p for p in self.working_proxies
                if p['server'] not in self.failed_proxies
            ]
        
        # If still none, need to refresh
        if not available:
            print(f"   ⚠️  No available proxies, refreshing...")
            await self._refresh_proxy_list()
            available = [
                p for p in self.working_proxies
                if p['server'] not in self.failed_proxies
            ]
        
        if not available:
            return None
        
        proxy = random.choice(available)
        self.used_this_session.add(proxy['server'])
        return proxy
    
    async def _fetch_url(self, session: aiohttp.ClientSession, url: str, timeout: int = 10) -> Optional[str]:
        """Fetch URL content"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            pass
        return None
    
    async def _get_geoip(self, session: aiohttp.ClientSession, ip: str) -> Dict:
        """Get GeoIP data for an IP"""
        defaults = {
            'country': 'US',
            'city': 'Unknown',
            'state': 'Unknown', 
            'timezone': 'America/New_York',
            'isp': 'Unknown'
        }
        
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,countryCode,regionName,city,timezone,isp"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('status') == 'success':
                        return {
                            'country': data.get('countryCode', 'US'),
                            'city': data.get('city', 'Unknown'),
                            'state': data.get('regionName', 'Unknown'),
                            'timezone': data.get('timezone', 'America/New_York'),
                            'isp': data.get('isp', 'Unknown')
                        }
        except Exception:
            pass
        
        return defaults
    
    async def _refresh_proxy_list(self):
        """Scrape fresh proxies from multiple sources"""
        print(f"   🔄 Scraping fresh proxies...")
        
        async with aiohttp.ClientSession() as session:
            # Run all scrapers in parallel
            results = await asyncio.gather(
                self._scrape_proxyscrape(session),
                self._scrape_geonode(session),
                self._scrape_proxylist_download(session),
                self._scrape_hidemy(session),
                self._scrape_spys(session),
                return_exceptions=True
            )
        
        # Collect all proxies
        all_proxies = []
        for result in results:
            if isinstance(result, list):
                all_proxies.extend(result)
        
        # Deduplicate by IP
        seen_ips = set()
        unique_proxies = []
        for p in all_proxies:
            if p['ip'] not in seen_ips:
                seen_ips.add(p['ip'])
                unique_proxies.append(p)
        
        print(f"   📊 Found {len(unique_proxies)} unique proxies")
        
        if not unique_proxies:
            print(f"   ❌ No proxies found from any source!")
            return
        
        # Limit to reasonable number (rate limits on GeoIP APIs)
        MAX_PROXIES = 10
        if len(unique_proxies) > MAX_PROXIES:
            print(f"   ⚠️  Limiting to {MAX_PROXIES} proxies (too many for GeoIP lookup)")
            unique_proxies = unique_proxies[:MAX_PROXIES]
        
        # Enrich with GeoIP (batch with rate limiting)
        print(f"   🌍 Getting location data for {len(unique_proxies)} proxies...")
        enriched = []
        
        # Enrich with GeoIP (batch with rate limiting)
        print(f"   🌍 Getting location data...")
        enriched = []
        
        async with aiohttp.ClientSession() as session:
            # Process in batches of 10 to respect rate limits
            batch_size = 10
            for i in range(0, len(unique_proxies), batch_size):
                batch = unique_proxies[i:i+batch_size]
                
                tasks = []
                for proxy in batch:
                    tasks.append(self._enrich_proxy(session, proxy))
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, dict) and result.get('country') == 'US':
                        enriched.append(result)
                
                # Rate limit: ip-api allows 45 requests/minute
                if i + batch_size < len(unique_proxies):
                    await asyncio.sleep(1.5)
        
        print(f"   ✅ {len(enriched)} verified US proxies with location data")
        
        # Merge with existing (keep old ones that aren't failed)
        existing_servers = {p['server'] for p in enriched}
        for old_proxy in self.working_proxies:
            if old_proxy['server'] not in existing_servers:
                if old_proxy['server'] not in self.failed_proxies:
                    enriched.append(old_proxy)
        
        self.working_proxies = enriched
        self.last_refresh = datetime.now()
        self._save_cache()
        
        print(f"   💾 Total proxies in cache: {len(self.working_proxies)}")
    
    async def _enrich_proxy(self, session: aiohttp.ClientSession, proxy: Dict) -> Dict:
        """Add GeoIP data to proxy"""
        geo = await self._get_geoip(session, proxy['ip'])
        return {**proxy, **geo}
    
    async def _scrape_proxyscrape(self, session: aiohttp.ClientSession) -> List[Dict]:
        """ProxyScrape API - usually has lots of proxies"""
        proxies = []
        try:
            urls = [
                "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=US&ssl=yes&anonymity=all",
                "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=US&ssl=all&anonymity=elite",
            ]
            for url in urls:
                text = await self._fetch_url(session, url)
                if text:
                    for line in text.strip().split('\n'):
                        if ':' in line:
                            parts = line.strip().split(':')
                            if len(parts) == 2:
                                ip, port = parts[0], parts[1]
                                if ip and port.isdigit():
                                    proxies.append({
                                        'server': f'http://{ip}:{port}',
                                        'ip': ip
                                    })
            print(f"      ✓ proxyscrape: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ proxyscrape: {e}")
        return proxies
    
    async def _scrape_geonode(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Geonode API - good quality proxies"""
        proxies = []
        try:
            url = "https://proxylist.geonode.com/api/proxy-list?limit=200&page=1&sort_by=lastChecked&sort_type=desc&country=US&protocols=http%2Chttps"
            text = await self._fetch_url(session, url, timeout=15)
            if text:
                data = json.loads(text)
                for p in data.get('data', []):
                    ip = p.get('ip')
                    port = p.get('port')
                    if ip and port:
                        proxies.append({
                            'server': f"http://{ip}:{port}",
                            'ip': ip
                        })
            print(f"      ✓ geonode: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ geonode: {e}")
        return proxies
    
    async def _scrape_proxylist_download(self, session: aiohttp.ClientSession) -> List[Dict]:
        """proxy-list.download - text list"""
        proxies = []
        try:
            urls = [
                "https://www.proxy-list.download/api/v1/get?type=http&country=US",
                "https://www.proxy-list.download/api/v1/get?type=https&country=US",
            ]
            for url in urls:
                text = await self._fetch_url(session, url)
                if text:
                    for line in text.strip().split('\n'):
                        if ':' in line:
                            parts = line.strip().split(':')
                            if len(parts) == 2:
                                ip, port = parts[0], parts[1]
                                if ip and port.isdigit():
                                    proxies.append({
                                        'server': f'http://{ip}:{port}',
                                        'ip': ip
                                    })
            print(f"      ✓ proxy-list.download: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ proxy-list.download: {e}")
        return proxies
    
    async def _scrape_hidemy(self, session: aiohttp.ClientSession) -> List[Dict]:
        """hidemy.name - requires parsing"""
        proxies = []
        try:
            from bs4 import BeautifulSoup
            url = "https://hidemy.name/en/proxy-list/?country=US&type=hs#list"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    table = soup.find('table')
                    if table:
                        for row in table.find_all('tr')[1:]:
                            cols = row.find_all('td')
                            if len(cols) >= 2:
                                ip = cols[0].text.strip()
                                port = cols[1].text.strip()
                                if ip and port.isdigit():
                                    proxies.append({
                                        'server': f'http://{ip}:{port}',
                                        'ip': ip
                                    })
            print(f"      ✓ hidemy: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ hidemy: {e}")
        return proxies
    
    async def _scrape_spys(self, session: aiohttp.ClientSession) -> List[Dict]:
        """spys.one - lots of proxies"""
        proxies = []
        try:
            url = "https://spys.me/proxy.txt"
            text = await self._fetch_url(session, url)
            if text:
                for line in text.strip().split('\n'):
                    if ':' in line and 'US-' in line:
                        parts = line.split(' ')[0].split(':')
                        if len(parts) == 2:
                            ip, port = parts[0], parts[1]
                            if ip and port.isdigit():
                                proxies.append({
                                    'server': f'http://{ip}:{port}',
                                    'ip': ip
                                })
            print(f"      ✓ spys.me: {len(proxies)}")
        except Exception as e:
            print(f"      ✗ spys.me: {e}")
        return proxies
    
    def mark_proxy_failed(self, proxy_server: str):
        """Mark proxy as failed (will be retried after cooldown)"""
        self.failed_proxies[proxy_server] = datetime.now()
        # Remove from working list
        self.working_proxies = [p for p in self.working_proxies if p['server'] != proxy_server]
        self._save_cache()
    
    def mark_proxy_success(self, proxy_server: str):
        """Mark proxy as successful"""
        # Remove from failed if it was there
        if proxy_server in self.failed_proxies:
            del self.failed_proxies[proxy_server]
