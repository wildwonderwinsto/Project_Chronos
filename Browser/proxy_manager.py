import random
import requests
import json
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pathlib import Path


class ProxyManager:
    """Proxy manager that caches working proxies and reuses them"""
    
    def __init__(self):
        self.working_proxies: List[Dict] = []
        self.failed_proxies: set = set()
        self.used_this_session: set = set()
        self.cache_file = Path("working_proxies.json")
        self.last_refresh = None
        self.refresh_interval = timedelta(hours=6)
        
        # Load cached working proxies
        self._load_cache()
    
    def _load_cache(self):
        """Load previously working proxies from cache"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.working_proxies = data.get('proxies', [])
                    print(f"   ✅ Loaded {len(self.working_proxies)} cached working proxies")
            except:
                pass
    
    def _save_cache(self):
        """Save working proxies to cache"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({
                    'proxies': self.working_proxies,
                    'last_updated': datetime.now().isoformat()
                }, f)
        except:
            pass
    
    async def get_proxy(self) -> Optional[Dict]:
        """Get a working proxy - prioritizes cached working ones"""
        
        # Refresh if needed
        if self._needs_refresh():
            await self._refresh_proxy_list()
        
        # Try to get from working proxies first
        available = [p for p in self.working_proxies 
                    if p['server'] not in self.used_this_session 
                    and p['server'] not in self.failed_proxies]
        
        if not available:
            # Reset session usage
            self.used_this_session.clear()
            available = [p for p in self.working_proxies 
                        if p['server'] not in self.failed_proxies]
        
        if not available:
            raise Exception("No working proxies available!")
        
        proxy = random.choice(available)
        self.used_this_session.add(proxy['server'])
        
        print(f"   🌐 Using proxy: {proxy['ip']} (US)")
        return proxy
    
    def _needs_refresh(self) -> bool:
        """Check if we need to find new proxies"""
        # Only refresh if cache is empty or very old
        if not self.working_proxies:
            return True
        if not self.last_refresh:
            return True
        if datetime.now() - self.last_refresh > timedelta(hours=24):
            return True
        return False
    
    async def _refresh_proxy_list(self):
        """Scrape new proxies from free sources"""
        print(f"   🔄 Searching for new working proxies...")
        
        new_proxies = []
        
        # Source 1: US-Proxy.org
        new_proxies.extend(await self._scrape_us_proxy_org())
        
        # Source 2: Free-Proxy-List
        new_proxies.extend(await self._scrape_free_proxy_list())
        
        # Source 3: ProxyScrape
        new_proxies.extend(await self._scrape_proxyscrape())
        
        # Add new proxies to working list (if not already there)
        for proxy in new_proxies:
            if proxy['server'] not in [p['server'] for p in self.working_proxies]:
                if proxy['server'] not in self.failed_proxies:
                    self.working_proxies.append(proxy)
        
        # Limit cache size to 2000 proxies
        if len(self.working_proxies) > 2000:
            self.working_proxies = self.working_proxies[-2000:]
        
        self.last_refresh = datetime.now()
        self._save_cache()
        
        print(f"   ✅ Total working proxies: {len(self.working_proxies)}")
    
    async def _scrape_us_proxy_org(self) -> List[Dict]:
        """Scrape US-Proxy.org"""
        proxies = []
        try:
            from bs4 import BeautifulSoup
            response = requests.get("https://www.us-proxy.org/", timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'class': 'table'})
                if table:
                    for row in table.find_all('tr')[1:50]:
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            https = cols[6].text.strip()
                            if https == 'yes':
                                proxies.append({
                                    'server': f'http://{ip}:{port}',
                                    'ip': ip,
                                    'country': 'US',
                                    'timezone': 'America/New_York'
                                })
        except:
            pass
        return proxies
    
    async def _scrape_free_proxy_list(self) -> List[Dict]:
        """Scrape Free-Proxy-List.net"""
        proxies = []
        try:
            from bs4 import BeautifulSoup
            response = requests.get("https://free-proxy-list.net/", timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'class': 'table'})
                if table:
                    for row in table.find_all('tr')[1:50]:
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            country = cols[3].text.strip()
                            https = cols[6].text.strip()
                            if country == 'US' and https == 'yes':
                                proxies.append({
                                    'server': f'http://{ip}:{port}',
                                    'ip': ip,
                                    'country': 'US',
                                    'timezone': 'America/New_York'
                                })
        except:
            pass
        return proxies
    
    async def _scrape_proxyscrape(self) -> List[Dict]:
        """Scrape ProxyScrape API"""
        proxies = []
        try:
            url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=US&ssl=yes&anonymity=all"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                for line in response.text.strip().split('\n')[:100]:
                    if ':' in line:
                        parts = line.strip().split(':')
                        if len(parts) == 2:
                            ip, port = parts
                            proxies.append({
                                'server': f'http://{ip}:{port}',
                                'ip': ip,
                                'country': 'US',
                                'timezone': 'America/New_York'
                            })
        except:
            pass
        return proxies
    
    def mark_proxy_failed(self, proxy_server: str):
        """Mark proxy as permanently failed"""
        self.failed_proxies.add(proxy_server)
        self.working_proxies = [p for p in self.working_proxies if p['server'] != proxy_server]
        self._save_cache()
    
    def mark_proxy_success(self, proxy_server: str):
        """Mark proxy as working (already in list, just save cache)"""
        self._save_cache()