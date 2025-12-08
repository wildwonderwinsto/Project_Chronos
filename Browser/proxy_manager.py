import asyncio
import random
import requests
from typing import Optional, Dict, List
from datetime import datetime, timedelta


class ProxyManager:
    """Manages free proxy scraping, validation, and rotation - US ONLY"""
    
    def __init__(self, us_only=True):
        self.proxy_list: List[Dict] = []
        self.used_proxies: set = set()
        self.last_refresh = None
        self.refresh_interval = timedelta(minutes=30)
        self.us_only = us_only  # Enforce US-only proxies
    
    async def get_proxy(self) -> Optional[Dict]:
        """
        Get a fresh, unused US proxy with geographic info
        Returns: {
            'server': 'http://ip:port',
            'ip': '1.2.3.4',
            'port': '8080',
            'country': 'US',
            'city': 'New York',
            'timezone': 'America/New_York'
        }
        """
        
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
        
        # Mark as used (1-Entry-Per-IP policy)
        self.used_proxies.add(proxy['server'])
        
        # Fetch geographic info
        await self._enrich_proxy_info(proxy)
        
        return proxy
    
    def _needs_refresh(self) -> bool:
        """Check if proxy list needs refreshing"""
        if not self.proxy_list:
            return True
        
        if not self.last_refresh:
            return True
        
        if datetime.now() - self.last_refresh > self.refresh_interval:
            return True
        
        # Check if we have enough US proxies
        us_proxies = [p for p in self.proxy_list if p['country'] == 'US']
        if len(us_proxies) < 5:
            return True
        
        return False
    
    async def _refresh_proxy_list(self):
        """Scrape and validate US proxies only"""
        print(f"   🔄 Refreshing US proxy list...")
        
        new_proxies = []
        
        # Source 1: US Proxies (primary source)
        new_proxies.extend(await self._scrape_us_proxies())
        
        # Source 2: Free Proxy List (filter for US)
        new_proxies.extend(await self._scrape_free_proxy_list())
        
        # Source 3: SSL Proxies (filter for US)
        new_proxies.extend(await self._scrape_ssl_proxies())
        
        # Filter to US only
        us_proxies = [p for p in new_proxies if p['country'] == 'US']
        
        if us_proxies:
            print(f"   ✅ Found {len(us_proxies)} US proxies")
            self.proxy_list = us_proxies
            self.last_refresh = datetime.now()
            self.used_proxies.clear()  # Reset used proxies on refresh
        else:
            print(f"   ⚠️  No US proxies found!")
            # Keep old list if we had US proxies before
            if not self.proxy_list:
                print(f"   ⚠️  Will attempt direct connection (no proxy)")
    
    async def _scrape_free_proxy_list(self) -> List[Dict]:
        """Scrape from free-proxy-list.net - US ONLY"""
        proxies = []
        
        try:
            from bs4 import BeautifulSoup
            
            url = "https://free-proxy-list.net/"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'class': 'table'})
                
                if table:
                    rows = table.find_all('tr')[1:]  # Skip header
                    
                    for row in rows[:50]:  # Check more rows
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            country = cols[3].text.strip()
                            https = cols[6].text.strip()
                            
                            # Only US proxies with HTTPS
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
            print(f"      ⚠️  Free-proxy-list scrape failed: {str(e)[:50]}")
        
        return proxies
    
    async def _scrape_ssl_proxies(self) -> List[Dict]:
        """Scrape from sslproxies.org - US ONLY"""
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
                    
                    for row in rows[:50]:  # Check more rows
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            country = cols[3].text.strip()
                            
                            # Only US proxies
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
            print(f"      ⚠️  SSL-proxies scrape failed: {str(e)[:50]}")
        
        return proxies
    
    async def _scrape_us_proxies(self) -> List[Dict]:
        """Scrape US proxies from us-proxy.org - PRIMARY SOURCE"""
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
                    
                    for row in rows[:100]:  # Get all available US proxies
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            ip = cols[0].text.strip()
                            port = cols[1].text.strip()
                            https = cols[6].text.strip()
                            
                            # All proxies from us-proxy.org are US-based
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
            print(f"      ⚠️  US-proxy scrape failed: {str(e)[:50]}")
        
        return proxies
    
    async def _enrich_proxy_info(self, proxy: Dict):
        """Fetch geographic info and timezone for US proxy IP"""
        try:
            # Use ip-api.com to get location info
            response = requests.get(
                f"http://ip-api.com/json/{proxy['ip']}",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    # Verify it's actually US
                    country_code = data.get('countryCode', '')
                    
                    if country_code != 'US':
                        print(f"      ⚠️  Proxy {proxy['ip']} is not US ({country_code}), marking as invalid")
                        proxy['country'] = country_code
                        return
                    
                    proxy['country'] = 'US'
                    proxy['city'] = data.get('city', 'Unknown')
                    proxy['region'] = data.get('regionName', 'Unknown')
                    proxy['timezone'] = data.get('timezone', 'America/New_York')
                    proxy['isp'] = data.get('isp', 'Unknown')
                    
                    print(f"   📍 US Proxy: {proxy['city']}, {proxy['region']} ({proxy['timezone']})")
        
        except Exception as e:
            # If geolocation fails, use default US timezone
            proxy['timezone'] = 'America/New_York'
            proxy['city'] = 'Unknown'
            proxy['region'] = 'Unknown'
            print(f"      ⚠️  Geolocation failed, using default US timezone")
    
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