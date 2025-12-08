import asyncio
import random
import requests
from typing import Optional, Dict, List
from datetime import datetime, timedelta


class ProxyManager:
    """Enhanced proxy manager with multiple sources - US ONLY"""
    
    def __init__(self, us_only=True):
        self.proxy_list: List[Dict] = []
        self.used_proxies: set = set()
        self.last_refresh = None
        self.refresh_interval = timedelta(minutes=30)
        self.us_only = us_only
    
    async def get_proxy(self) -> Optional[Dict]:
        """Get a fresh, unused US proxy with geographic info"""
        
        # Refresh proxy list if needed
        if self._needs_refresh():
            await self._refresh_proxy_list()
        
        # Find an unused US proxy
        available = [p for p in self.proxy_list 
                    if p['server'] not in self.used_proxies 
                    and p['country'] == 'US']
        
        if not available:
            print(f"   ⚠️  All US proxies used, refreshing list...")
            await self._refresh_proxy_list()
            available = [p for p in self.proxy_list 
                        if p['server'] not in self.used_proxies 
                        and p['country'] == 'US']
        
        if not available:
            print(f"   ❌ No US proxies available!")
            return None
        
        # Pick random US proxy
        proxy = random.choice(available)
        
        # Mark as used
        self.used_proxies.add(proxy['server'])
        
        # Fetch geographic info - if it fails or not US, remove it
        is_valid = await self._enrich_proxy_info(proxy)
        
        if not is_valid or proxy['country'] != 'US':
            # Remove bad proxy and try again
            self.mark_proxy_failed(proxy['server'])
            return await self.get_proxy()  # Recursively try next
        
        return proxy
    
    def _needs_refresh(self) -> bool:
        """Check if proxy list needs refreshing"""
        if not self.proxy_list:
            return True
        
        if not self.last_refresh:
            return True
        
        if datetime.now() - self.last_refresh > self.refresh_interval:
            return True
        
        us_proxies = [p for p in self.proxy_list if p['country'] == 'US']
        if len(us_proxies) < 10:
            return True
        
        return False
    
    async def _refresh_proxy_list(self):
        """Scrape proxies from MULTIPLE sources"""
        print(f"   🔄 Refreshing US proxy list...")
        
        new_proxies = []
        
        # Source 1: US-Proxy.org (PRIMARY - Best for US)
        new_proxies.extend(await self._scrape_us_proxy_org())
        
        # Source 2: Free-Proxy-List.net
        new_proxies.extend(await self._scrape_free_proxy_list())
        
        # Source 3: SSL-Proxies.org
        new_proxies.extend(await self._scrape_ssl_proxies())
        
        # Source 4: Proxy-List.download (NEW)
        new_proxies.extend(await self._scrape_proxy_list_download())
        
        # Source 5: GeoNode (NEW - Good quality)
        new_proxies.extend(await self._scrape_geonode())
        
        # Source 6: ProxyScrape (NEW - Large list)
        new_proxies.extend(await self._scrape_proxyscrape())
        
        # Source 7: GitHub Proxy Lists (NEW - Community maintained)
        new_proxies.extend(await self._scrape_github_proxies())
        
        # Remove duplicates
        unique_proxies = {}
        for p in new_proxies:
            if p['server'] not in unique_proxies:
                unique_proxies[p['server']] = p
        
        new_proxies = list(unique_proxies.values())
        
        # Filter to US only
        us_proxies = [p for p in new_proxies if p['country'] == 'US']
        
        if us_proxies:
            print(f"   ✅ Found {len(us_proxies)} US proxies")
            self.proxy_list = us_proxies
            self.last_refresh = datetime.now()
            self.used_proxies.clear()
        else:
            print(f"   ⚠️  No US proxies found!")
    
    async def _scrape_us_proxy_org(self) -> List[Dict]:
        """US-Proxy.org - PRIMARY SOURCE"""
        proxies = []
        try:
            from bs4 import BeautifulSoup
            
            url = "https://www.us-proxy.org/"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'class': 'table'})
                
                if table:
                    rows = table.find_all('tr')[1:]
                    for row in rows[:100]:
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            https = cols[6].text.strip()
                            
                            if https == 'yes':
                                proxies.append({
                                    'server': f'http://{ip}:{port}',
                                    'ip': ip,
                                    'port': port,
                                    'country': 'US',
                                    'city': None,
                                    'timezone': None
                                })
        except Exception as e:
            print(f"      ⚠️  us-proxy.org failed: {str(e)[:40]}")
        
        return proxies
    
    async def _scrape_free_proxy_list(self) -> List[Dict]:
        """Free-Proxy-List.net"""
        proxies = []
        try:
            from bs4 import BeautifulSoup
            
            url = "https://free-proxy-list.net/"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'class': 'table'})
                
                if table:
                    rows = table.find_all('tr')[1:]
                    for row in rows[:100]:
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
                                    'port': port,
                                    'country': 'US',
                                    'city': None,
                                    'timezone': None
                                })
        except Exception as e:
            print(f"      ⚠️  free-proxy-list failed: {str(e)[:40]}")
        
        return proxies
    
    async def _scrape_ssl_proxies(self) -> List[Dict]:
        """SSL-Proxies.org"""
        proxies = []
        try:
            from bs4 import BeautifulSoup
            
            url = "https://www.sslproxies.org/"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'class': 'table'})
                
                if table:
                    rows = table.find_all('tr')[1:]
                    for row in rows[:100]:
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            country = cols[3].text.strip()
                            
                            if country == 'US':
                                proxies.append({
                                    'server': f'http://{ip}:{port}',
                                    'ip': ip,
                                    'port': port,
                                    'country': 'US',
                                    'city': None,
                                    'timezone': None
                                })
        except Exception as e:
            print(f"      ⚠️  sslproxies failed: {str(e)[:40]}")
        
        return proxies
    
    async def _scrape_proxy_list_download(self) -> List[Dict]:
        """Proxy-List.download - NEW SOURCE"""
        proxies = []
        try:
            # They have direct txt files
            url = "https://www.proxy-list.download/api/v1/get?type=https&country=US"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                for line in lines[:200]:
                    if ':' in line:
                        ip, port = line.strip().split(':')
                        proxies.append({
                            'server': f'http://{ip}:{port}',
                            'ip': ip,
                            'port': port,
                            'country': 'US',
                            'city': None,
                            'timezone': None
                        })
        except Exception as e:
            print(f"      ⚠️  proxy-list.download failed: {str(e)[:40]}")
        
        return proxies
    
    async def _scrape_geonode(self) -> List[Dict]:
        """GeoNode - NEW SOURCE (Good quality)"""
        proxies = []
        try:
            # GeoNode has a nice API
            url = "https://proxylist.geonode.com/api/proxy-list?limit=200&page=1&sort_by=lastChecked&sort_type=desc&country=US&protocols=http%2Chttps"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for proxy in data.get('data', []):
                    ip = proxy.get('ip')
                    port = proxy.get('port')
                    if ip and port:
                        proxies.append({
                            'server': f'http://{ip}:{port}',
                            'ip': ip,
                            'port': str(port),
                            'country': 'US',
                            'city': proxy.get('city'),
                            'timezone': None
                        })
        except Exception as e:
            print(f"      ⚠️  geonode failed: {str(e)[:40]}")
        
        return proxies
    
    async def _scrape_proxyscrape(self) -> List[Dict]:
        """ProxyScrape - NEW SOURCE (Large lists)"""
        proxies = []
        try:
            # ProxyScrape API
            url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=US&ssl=yes&anonymity=all"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                for line in lines[:200]:
                    if ':' in line:
                        parts = line.strip().split(':')
                        if len(parts) == 2:
                            ip, port = parts
                            proxies.append({
                                'server': f'http://{ip}:{port}',
                                'ip': ip,
                                'port': port,
                                'country': 'US',
                                'city': None,
                                'timezone': None
                            })
        except Exception as e:
            print(f"      ⚠️  proxyscrape failed: {str(e)[:40]}")
        
        return proxies
    
    async def _scrape_github_proxies(self) -> List[Dict]:
        """GitHub proxy lists - NEW SOURCE (Community maintained)"""
        proxies = []
        try:
            # TheSpeedX/PROXY-List (popular GitHub repo)
            url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                # Check each proxy's country via API (sample only first 50 to avoid rate limits)
                for line in lines[:50]:
                    if ':' in line:
                        parts = line.strip().split(':')
                        if len(parts) == 2:
                            ip, port = parts
                            # Quick check if IP is US-based
                            if await self._quick_check_us_ip(ip):
                                proxies.append({
                                    'server': f'http://{ip}:{port}',
                                    'ip': ip,
                                    'port': port,
                                    'country': 'US',
                                    'city': None,
                                    'timezone': None
                                })
        except Exception as e:
            print(f"      ⚠️  github proxies failed: {str(e)[:40]}")
        
        return proxies
    
    async def _quick_check_us_ip(self, ip: str) -> bool:
        """Quick check if IP is US-based"""
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get('countryCode') == 'US'
        except:
            pass
        return False
    
    async def _enrich_proxy_info(self, proxy: Dict):
        """Fetch geographic info and timezone for proxy IP"""
        try:
            response = requests.get(
                f"http://ip-api.com/json/{proxy['ip']}",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    country_code = data.get('countryCode', '')
                    
                    # CRITICAL: If not US, remove from list completely
                    if country_code != 'US':
                        print(f"      ❌ Proxy {proxy['ip']} is {country_code}, removing")
                        proxy['country'] = country_code  # Mark as non-US
                        return False  # Signal to remove
                    
                    proxy['country'] = 'US'
                    proxy['city'] = data.get('city', 'Unknown')
                    proxy['region'] = data.get('regionName', 'Unknown')
                    proxy['timezone'] = data.get('timezone', 'America/New_York')
                    proxy['isp'] = data.get('isp', 'Unknown')
                    
                    print(f"   📍 US Proxy: {proxy['city']}, {proxy['region']} ({proxy['timezone']})")
                    return True  # Valid US proxy
        
        except Exception as e:
            proxy['timezone'] = 'America/New_York'
            proxy['city'] = 'Unknown'
            proxy['region'] = 'Unknown'
            return False  # Remove on error
    
    def mark_proxy_failed(self, proxy_server: str):
        """Mark a proxy as failed (remove from list)"""
        self.proxy_list = [p for p in self.proxy_list if p['server'] != proxy_server]
        self.used_proxies.discard(proxy_server)
        print(f"   🚫 Proxy {proxy_server} marked as failed and removed")
    
    def get_stats(self) -> Dict:
        """Get proxy manager statistics"""
        us_proxies = [p for p in self.proxy_list if p['country'] == 'US']
        
        return {
            'total_proxies': len(self.proxy_list),
            'us_proxies': len(us_proxies),
            'used_proxies': len(self.used_proxies),
            'available_us_proxies': len([p for p in us_proxies if p['server'] not in self.used_proxies]),
            'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None
        }