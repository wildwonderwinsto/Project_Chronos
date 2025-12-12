import random
import requests
import json
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from pathlib import Path


class ProxyManager:
    """Enhanced proxy manager with GeoIP lookup and better error handling"""
    
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
                    # Ensure all proxies have required fields
                    self.working_proxies = [p for p in self.working_proxies if self._validate_proxy_dict(p)]
                    print(f"   ✅ Loaded {len(self.working_proxies)} cached working proxies")
            except Exception as e:
                print(f"   ⚠️  Failed to load cache: {e}")
                self.working_proxies = []
    
    def _validate_proxy_dict(self, proxy: Dict) -> bool:
        """Ensure proxy dict has all required fields"""
        required = ['server', 'ip', 'country', 'city', 'state', 'timezone']
        return all(key in proxy for key in required)
    
    def _save_cache(self):
        """Save working proxies to cache with nice formatting"""
        try:
            # Sort proxies by state, then city for easier reading
            sorted_proxies = sorted(
                self.working_proxies,
                key=lambda p: (p.get('state', 'ZZZ'), p.get('city', 'ZZZ'))
            )
            
            with open(self.cache_file, 'w') as f:
                json.dump({
                    'last_updated': datetime.now().isoformat(),
                    'total_proxies': len(sorted_proxies),
                    'proxies': sorted_proxies
                }, f, indent=2, sort_keys=False)
            
            print(f"   💾 Saved {len(sorted_proxies)} proxies to cache")
        except Exception as e:
            print(f"   ⚠️  Failed to save cache: {e}")
    
    def _enrich_proxy_with_geoip(self, proxy_dict: Dict) -> Dict:
        """
        Enrich proxy with geographic data using free GeoIP API
        Falls back to defaults if API fails
        """
        ip = proxy_dict.get('ip')
        
        # Default values
        defaults = {
            'country': 'US',
            'city': 'Unknown',
            'state': 'Unknown',
            'timezone': 'America/New_York',
            'isp': 'Unknown'
        }
        
        # Try multiple free GeoIP services
        geoip_services = [
            f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,timezone,isp",
            f"https://ipapi.co/{ip}/json/",
        ]
        
        for service_url in geoip_services:
            try:
                response = requests.get(service_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse based on service
                    if 'ip-api.com' in service_url:
                        if data.get('status') == 'success' and data.get('countryCode') == 'US':
                            return {
                                **proxy_dict,
                                'country': 'US',
                                'city': data.get('city', 'Unknown'),
                                'state': data.get('regionName', data.get('region', 'Unknown')),
                                'timezone': data.get('timezone', 'America/New_York'),
                                'isp': data.get('isp', 'Unknown')
                            }
                    
                    elif 'ipapi.co' in service_url:
                        if data.get('country_code') == 'US':
                            return {
                                **proxy_dict,
                                'country': 'US',
                                'city': data.get('city', 'Unknown'),
                                'state': data.get('region', 'Unknown'),
                                'timezone': data.get('timezone', 'America/New_York'),
                                'isp': data.get('org', 'Unknown')
                            }
                        
            except Exception as e:
                continue
        
        # If all services fail, return with defaults
        print(f"      ⚠️  GeoIP lookup failed for {ip}, using defaults")
        return {**proxy_dict, **defaults}
    
    async def get_proxy(self) -> Optional[Dict]:
        """Get a working proxy - prioritizes cached working ones"""
        
        # Refresh if needed
        if self._needs_refresh():
            await self._refresh_proxy_list()
        
        # If still no proxies, raise error
        if not self.working_proxies:
            raise Exception("No working proxies available! Cannot proceed.")
        
        # Try to get from working proxies first
        available = [p for p in self.working_proxies 
                    if p['server'] not in self.used_this_session 
                    and p['server'] not in self.failed_proxies]
        
        if not available:
            # Reset session usage
            print(f"   🔄 All proxies used this session, resetting...")
            self.used_this_session.clear()
            available = [p for p in self.working_proxies 
                        if p['server'] not in self.failed_proxies]
        
        if not available:
            raise Exception("All cached proxies have failed! Refreshing...")
        
        proxy = random.choice(available)
        self.used_this_session.add(proxy['server'])
        
        return proxy
    
    def _needs_refresh(self) -> bool:
        """Check if we need to find new proxies"""
        if not self.working_proxies:
            return True
        if not self.last_refresh:
            return True
        if datetime.now() - self.last_refresh > timedelta(hours=24):
            return True
        return False
    
    async def _refresh_proxy_list(self):
        """Scrape new proxies from free sources and enrich with GeoIP"""
        print(f"   🔄 Searching for new US proxies with location data...")
        
        new_proxies = []
        
        # Source 1: US-Proxy.org
        new_proxies.extend(await self._scrape_us_proxy_org())
        
        # Source 2: Free-Proxy-List
        new_proxies.extend(await self._scrape_free_proxy_list())
        
        # Source 3: ProxyScrape
        new_proxies.extend(await self._scrape_proxyscrape())
        
        print(f"   📊 Found {len(new_proxies)} potential US proxies")
        
        # Enrich with GeoIP data
        enriched_count = 0
        for proxy in new_proxies:
            if proxy['server'] not in [p['server'] for p in self.working_proxies]:
                if proxy['server'] not in self.failed_proxies:
                    # Enrich with GeoIP
                    enriched = self._enrich_proxy_with_geoip(proxy)
                    # Only add if it's confirmed US
                    if enriched['country'] == 'US':
                        self.working_proxies.append(enriched)
                        enriched_count += 1
        
        print(f"   ✅ Added {enriched_count} new verified US proxies with location data")
        
        # Limit cache size to 1000 proxies
        if len(self.working_proxies) > 1000:
            self.working_proxies = self.working_proxies[-1000:]
        
        self.last_refresh = datetime.now()
        self._save_cache()
        
        print(f"   💾 Total working proxies in cache: {len(self.working_proxies)}")
    
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
                    for row in table.find_all('tr')[1:100]:
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            https = cols[6].text.strip()
                            if https == 'yes':
                                proxies.append({
                                    'server': f'http://{ip}:{port}',
                                    'ip': ip,
                                    'country': 'US'
                                })
            print(f"      ✓ us-proxy.org: {len(proxies)} proxies")
        except Exception as e:
            print(f"      ✗ us-proxy.org failed: {e}")
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
                    for row in table.find_all('tr')[1:100]:
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
                                    'country': 'US'
                                })
            print(f"      ✓ free-proxy-list: {len(proxies)} proxies")
        except Exception as e:
            print(f"      ✗ free-proxy-list failed: {e}")
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
                                'country': 'US'
                            })
            print(f"      ✓ proxyscrape: {len(proxies)} proxies")
        except Exception as e:
            print(f"      ✗ proxyscrape failed: {e}")
        return proxies
    
    def mark_proxy_failed(self, proxy_server: str):
        """Mark proxy as permanently failed"""
        self.failed_proxies.add(proxy_server)
        self.working_proxies = [p for p in self.working_proxies if p['server'] != proxy_server]
        self._save_cache()
    
    def mark_proxy_success(self, proxy_server: str):
        """Mark proxy as working (already in list, just save cache)"""
        self._save_cache()