import re
from datetime import datetime
from functools import wraps
import time
import requests
from bs4 import BeautifulSoup
import dns.resolver
import whois
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import config
from selenium.webdriver.common.by import By
import logging
from selenium.webdriver.common.keys import Keys
import telegram

# Setup logging basic configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Token bot dari config
TOKEN = config.TELEGRAM_TOKEN

# Platform yang didukung untuk pencarian
SEARCH_PLATFORMS = [
    'twitter',
    'facebook',
    'instagram',
    'linkedin',
    'github',
    'medium',
    'youtube',
    'reddit'
]

# Setup logging
logger = logging.getLogger(__name__)

def get_platform_emoji(platform):
    """Return emoji for social media platform"""
    platform = platform.lower()
    emoji_map = {
        'facebook': '👥',
        'instagram': '📸',
        'twitter': '🐦',
        'github': '💻',
        'linkedin': '💼',
        'youtube': '🎥',
        'reddit': '🔥',
        'medium': '📝',
        'devto': '👨‍💻',
        'gitlab': '🦊',
        'tiktok': '🎵'
    }
    return emoji_map.get(platform, '🔍')

# Tambahkan variabel global untuk tracking
daily_users = set()
last_reset_date = datetime.now().date()
total_monthly_users = set()
last_monthly_reset = datetime.now().replace(day=1).date()

def escape_markdown(text):
    """Escape karakter markdown"""
    if not isinstance(text, str):
        return str(text)
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def setup_driver():
    """Setup Chrome WebDriver dengan konfigurasi optimal"""
    try:
        chrome_options = Options()
        
        # Tambahkan arguments dari config
        for arg in config.CHROME_SETTINGS['arguments']:
            chrome_options.add_argument(arg)
            
        # Set preferences jika ada di config
        if hasattr(config, 'CHROME_SETTINGS') and 'prefs' in config.CHROME_SETTINGS:
            chrome_options.add_experimental_option('prefs', config.CHROME_SETTINGS['prefs'])
        else:
            # Fallback ke konfigurasi default
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
            
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(config.CHROME_SETTINGS['timeouts']['pageLoad'])
        return driver
        
    except Exception as e:
        logger.error(f"Error setting up Chrome driver: {str(e)}")
        raise e

def search_profile(username, platform):
    """Cari profil dengan multiple metode pencarian yang lebih advanced"""
    driver = None
    results = {
        'found': False, 
        'data': {
            'username': username,
            'name': '',
            'bio': '',
            'url': '',
            'status': '',
            'possible_matches': []
        }, 
        'error': None
    }
    
    try:
        # 1. Coba pencarian API terlebih dahulu
        api_result = search_via_api(username, platform)
        if api_result.get('found'):
            return api_result
            
        # 2. Setup driver jika API gagal
        driver = setup_driver()
        if not driver:
            raise Exception("Gagal membuat WebDriver")
            
        wait = WebDriverWait(driver, config.CHROME_SETTINGS['timeouts']['pageLoad'])
            
        # 3. Gunakan Selenium dengan teknik advanced
        selenium_result = None
        if platform == "Instagram":
            selenium_result = search_instagram_advanced(driver, wait, username)
        elif platform == "Twitter": 
            selenium_result = search_twitter_advanced(driver, wait, username)
        elif platform == "Facebook":
            selenium_result = search_facebook_advanced(driver, wait, username)
        elif platform == "GitHub":
            selenium_result = search_github_advanced(driver, wait, username)
            
        if selenium_result and selenium_result.get('found'):
            return selenium_result
            
        # 4. Jika masih tidak ditemukan, lakukan OSINT tambahan
        if not results['found']:
            # Cek arsip web
            archived_results = check_web_archives(username, platform)
            if archived_results:
                results['data']['archived_data'] = archived_results
            
            # Cari username variations
            variations = generate_username_variations(username)
            possible_matches = []
            for var in variations[:5]:  # Cek 5 variasi pertama
                var_result = quick_check_username(var, platform)
                if var_result:
                    possible_matches.append(var_result)
            results['data']['possible_matches'] = possible_matches
            
            # Cek metadata tambahan
            metadata = gather_additional_metadata(username, platform)
            if metadata:
                results['data']['metadata'] = metadata
                
    except Exception as e:
        error_msg = f"Error in search_profile for {platform}: {str(e)}"
        logger.error(error_msg)
        results['error'] = error_msg
        
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {str(e)}")
    
    return results

def search_via_api(username, platform):
    """Pencarian menggunakan API resmi platform"""
    results = {'found': False, 'data': {}}
    
    try:
        if platform == "Instagram":
            # Coba gunakan Instagram Basic Display API
            if config.INSTAGRAM_API_TOKEN:
                headers = {
                    'Authorization': f'Bearer {config.INSTAGRAM_API_TOKEN}',
                    'User-Agent': config.HEADERS['User-Agent']
                }
                
                try:
                    # Coba dapatkan user ID dulu
                    response = requests.get(
                        f"https://graph.instagram.com/me?fields=id,username&access_token={config.INSTAGRAM_API_TOKEN}",
                        headers=headers,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('id'):
                            # Gunakan ID untuk mendapatkan info detail
                            detail_response = requests.get(
                                f"https://graph.instagram.com/{data['id']}?fields=id,username,account_type,media_count,biography&access_token={config.INSTAGRAM_API_TOKEN}",
                                headers=headers,
                                timeout=10
                            )
                            
                            if detail_response.status_code == 200:
                                detail_data = detail_response.json()
                                results['found'] = True
                                results['data'] = {
                                    'username': detail_data.get('username'),
                                    'account_type': detail_data.get('account_type'),
                                    'media_count': detail_data.get('media_count'),
                                    'bio': detail_data.get('biography')
                                }
                except Exception as e:
                    logger.error(f"Instagram API error: {str(e)}")
                    # Fallback ke web scraping jika API gagal
                    pass
                    
        elif platform == "Twitter" and config.TWITTER_API_TOKEN:
            try:
                headers = {'Authorization': f'Bearer {config.TWITTER_API_TOKEN}'}
                response = requests.get(
                    f"{config.TWITTER_API_ENDPOINT}{username}",
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    results['found'] = True
                    results['data'] = extract_twitter_data(data)
            except Exception as e:
                logger.error(f"Twitter API error: {str(e)}")
                
    except Exception as e:
        logger.error(f"API search error for {platform}: {str(e)}")
        
    return results

def check_web_archives(username, platform):
    """Cek arsip web untuk profil"""
    archives = {}
    base_urls = {
        'Instagram': f'instagram.com/{username}',
        'Twitter': f'twitter.com/{username}',
        'Facebook': f'facebook.com/{username}',
        'GitHub': f'github.com/{username}'
    }
    
    try:
        if platform in base_urls:
            wayback_url = f'http://web.archive.org/cdx/search/cdx?url={base_urls[platform]}&output=json'
            
            # Konfigurasi session dengan retry
            session = requests.Session()
            retries = requests.adapters.Retry(
                total=3,  # Jumlah total retry
                backoff_factor=0.5,  # Waktu tunggu antara retry
                status_forcelist=[500, 502, 503, 504]  # Status code yang akan di-retry
            )
            session.mount('http://', requests.adapters.HTTPAdapter(max_retries=retries))
            session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
            
            # Tambahkan timeout yang lebih lama
            response = session.get(wayback_url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if len(data) > 1:  # Skip header row
                        archives['wayback_snapshots'] = []
                        # Ambil 4 snapshot terbaru
                        for row in data[1:5]:
                            try:
                                snapshot = {
                                    'timestamp': row[1],
                                    'url': f'http://web.archive.org/web/{row[1]}/{base_urls[platform]}'
                                }
                                archives['wayback_snapshots'].append(snapshot)
                            except (IndexError, TypeError):
                                continue
                except ValueError:
                    logger.error("Failed to parse Wayback Machine JSON response")
                    
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout while checking archives for {platform}: {username}")
        archives['error'] = "Timeout saat mengakses arsip"
    except requests.exceptions.RequestException as e:
        logger.error(f"Archive check error: {str(e)}")
        archives['error'] = f"Gagal mengakses arsip: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in archive check: {str(e)}")
        archives['error'] = "Terjadi kesalahan saat mengecek arsip"
        
    return archives

def gather_additional_metadata(username, platform):
    """Kumpulkan metadata tambahan tentang profil"""
    metadata = {}
    
    try:
        # 1. Cek mentions di Google
        google_url = f"https://www.google.com/search?q=site:{platform.lower()}.com+\"{username}\""
        response = requests.get(google_url, headers=config.HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('div', class_='g')
            metadata['google_mentions'] = [
                {
                    'title': result.find('h3').text if result.find('h3') else '',
                    'url': result.find('a')['href'] if result.find('a') else ''
                }
                for result in results[:3]
            ]
        
        # 2. Cek data DNS jika ada domain terkait
        try:
            domain = f"{username}.{platform.lower()}.com"
            dns_records = dns.resolver.resolve(domain, 'A')
            metadata['dns_info'] = {
                'domain': domain,
                'records': [str(record) for record in dns_records]
            }
        except:
            pass
        
        # 3. Cek informasi WHOIS jika ada domain
        try:
            whois_info = whois.whois(domain)
            if whois_info:
                metadata['whois_info'] = {
                    'registrar': whois_info.registrar,
                    'creation_date': str(whois_info.creation_date),
                    'expiration_date': str(whois_info.expiration_date)
                }
        except:
            pass
            
    except Exception as e:
        logger.error(f"Metadata gathering error: {str(e)}")
        
    return metadata

def quick_check_username(username, platform):
    """Cek cepat keberadaan username"""
    try:
        urls = {
            'Instagram': f'https://www.instagram.com/{username}/',
            'Twitter': f'https://twitter.com/{username}',
            'Facebook': f'https://www.facebook.com/{username}',
            'GitHub': f'https://github.com/{username}'
        }
        
        if platform in urls:
            response = requests.head(
                urls[platform],
                headers=config.HEADERS,
                timeout=5,
                allow_redirects=True
            )
            if response.status_code == 200:
                return {
                    'username': username,
                    'url': urls[platform],
                    'status': 'active'
                }
    except:
        pass
    return None

def search_direct(username, platform):
    """Coba pencarian langsung via API"""
    results = {'found': False, 'error': None}
    
    try:
        if platform == "Instagram":
            try:
                url = f"https://www.instagram.com/{username}/?__a=1&__d=1"
                response = requests.get(
                    url, 
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Cache-Control': 'max-age=0'
                    }
                )
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data and 'graphql' in data:
                            user = data['graphql']['user']
                            results = {
                                'found': True,
                                'url': f"https://www.instagram.com/{username}",
                                'username': username,
                                'data': {
                                    'name': user.get('full_name', ''),
                                    'bio': user.get('biography', ''),
                                    'followers': user.get('edge_followed_by', {}).get('count', 0)
                                }
                            }
                    except ValueError:
                        # JSON parsing failed, fallback to Selenium
                        pass
            except Exception as e:
                logger.error(f"Instagram API error: {str(e)}")
                # Don't raise, let Selenium handle it
                pass
        
        elif platform == "Twitter":
            if config.TWITTER_API_TOKEN:
                headers = {
                    'Authorization': f'Bearer {config.TWITTER_API_TOKEN}',
                    'User-Agent': 'v2UserLookupPython'
                }
                url = f"https://api.twitter.com/2/users/by/username/{username}"
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        results = {
                            'found': True,
                            'url': f"https://twitter.com/{username}",
                            'username': username,
                            'data': {
                                'name': data['data'].get('name', ''),
                                'description': data['data'].get('description', '')
                            }
                        }
                        
    except Exception as e:
        logger.error(f"Direct search error for {platform}: {str(e)}")
        # Don't raise exception, let the calling function handle it
        pass
        
    return results

def find_possible_matches(username, platform):
    """Cari kemungkinan profil terkait"""
    possible_matches = []
    
    try:
        # Generate variasi username
        variations = generate_username_variations(username)
        
        # Cari di Google
        search_query = f"site:{platform.lower()}.com {username}"
        google_url = f"https://www.google.com/search?q={search_query}"
        response = requests.get(google_url, headers=config.HEADERS)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('div', class_='g')
            
            for result in results[:5]:  # Ambil 5 hasil pertama
                link = result.find('a')
                if link and platform.lower() in link['href']:
                    title = result.find('h3')
                    if title:
                        possible_matches.append({
                            'url': link['href'],
                            'title': title.text,
                            'source': 'Google Search'
                        })
                        
        # Cari di platform spesifik
        if platform == "GitHub":
            # Cari repository atau user yang mirip
            search_url = f"https://api.github.com/search/users?q={username}"
            response = requests.get(search_url)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('items', [])[:3]:
                    possible_matches.append({
                        'url': item['html_url'],
                        'username': item['login'],
                        'source': 'GitHub API'
                    })
                    
    except Exception as e:
        logger.error(f"Error finding possible matches: {str(e)}")
        
    return possible_matches

def generate_username_variations(username):
    """Generate variasi username yang mungkin"""
    variations = set([username])
    
    # Split username
    parts = re.split(r'[._-]', username)
    
    # Tambah variasi dengan separator berbeda
    separators = ['', '.', '_', '-']
    for sep in separators:
        variations.add(sep.join(parts))
    
    # Tambah angka umum
    common_numbers = ['123', '1234', '321', '007']
    for num in common_numbers:
        variations.add(f"{username}{num}")
    
    # Tambah tahun
    current_year = datetime.now().year
    for year in range(current_year-5, current_year+1):
        variations.add(f"{username}{year}")
    
    # Tambah variasi capitalization
    variations.add(username.lower())
    variations.add(username.upper())
    variations.add(username.capitalize())
    
    return list(variations)

def format_search_results(results, platform):
    """Format hasil pencarian untuk ditampilkan"""
    if not results:
        return "❌ Terjadi kesalahan saat memformat hasil pencarian."
        
    try:
        formatted_text = ""
        platform_icons = {
            'Facebook': '👥',
            'Instagram': '📸', 
            'Twitter': '🐦',
            'GitHub': '💻',
            'LinkedIn': '💼'
        }
        icon = platform_icons.get(platform, '🔍')
        
        if results.get('found'):
            data = results['data']
            formatted_text += f"{icon} *Hasil Pencarian {platform}*\n\n"
            
            # Info utama
            if data.get('name'): 
                formatted_text += f"📝 *Nama:* {escape_markdown(data['name'])}\n"
            if data.get('username'):
                formatted_text += f"🔖 *Username:* {escape_markdown(data['username'])}\n" 
            if data.get('url'):
                formatted_text += f"🔗 *URL:* {escape_markdown(data['url'])}\n"
                
            # Info tambahan    
            if data.get('location'):
                formatted_text += f"📍 *Lokasi:* {escape_markdown(data['location'])}\n"
            if data.get('work'):
                formatted_text += f"💼 *Pekerjaan:* {escape_markdown(data['work'])}\n"
            if data.get('education'):
                formatted_text += f"🎓 *Pendidikan:* {escape_markdown(data['education'])}\n"
            if data.get('bio'):
                formatted_text += f"\n📋 *Bio:*\n{escape_markdown(data['bio'])}\n"
                
            # Statistik
            formatted_text += "\n📊 *Statistik:*\n"
            if data.get('friends'):
                formatted_text += f"👥 Teman: {data['friends']}\n"
            if data.get('followers'):
                formatted_text += f"👥 Pengikut: {data['followers']}\n"
            if data.get('posts'):
                formatted_text += f"📝 Post: {data['posts']}\n"
                
            # Status & metadata
            if data.get('verified'):
                formatted_text += "✅ Akun Terverifikasi\n"
            if data.get('created_at'):
                formatted_text += f"📅 Bergabung: {data['created_at']}\n"
                
            # Sumber data
            formatted_text += f"\n🔍 *Sumber:* "
            formatted_text += "🔌 API" if data.get('source') == 'api' else "🌐 Web"
        else:
            formatted_text += f"❌ *Profil tidak ditemukan di {platform}*\n\n"
            formatted_text += "💡 *Saran:*\n"
            formatted_text += "• Periksa ejaan username\n"
            formatted_text += "• Coba gunakan nama lengkap\n"
            formatted_text += "• Coba platform sosial media lain\n"
            
            # Tampilkan kemungkinan akun terkait jika ada
            if results.get('data', {}).get('possible_matches'):
                formatted_text += "\n🔍 *Mungkin yang Anda cari:*\n"
                for match in results['data']['possible_matches'][:3]:
                    formatted_text += f"• {escape_markdown(match.get('username', ''))}\n"
                    
        return formatted_text
        
    except Exception as e:
        logger.error(f"Error formatting search results: {str(e)}")
        return f"❌ Terjadi kesalahan saat memformat hasil: {str(e)}"

def verify_platform_status(platform):
    """Verifikasi status platform sebelum melakukan pencarian"""
    try:
        urls = {
            "Instagram": "https://www.instagram.com",
            "Twitter": "https://twitter.com",
            "Facebook": "https://www.facebook.com",
            "LinkedIn": "https://www.linkedin.com",
            "GitHub": "https://github.com"
        }
        
        if platform not in urls:
            return True  # Skip check untuk platform yang tidak terdaftar
            
        response = requests.head(urls[platform], timeout=5)
        return response.status_code == 200
    except:
        return False

class RateLimiter:
    def __init__(self):
        self.last_request = {}
        self.request_count = {}
        
    def can_make_request(self, platform):
        now = datetime.now()
        if platform not in self.last_request:
            self.last_request[platform] = now
            self.request_count[platform] = 1
            return True
            
        time_passed = (now - self.last_request[platform]).total_seconds()
        if time_passed > config.RATE_LIMIT['retry_after']:
            self.last_request[platform] = now
            self.request_count[platform] = 1
            return True
            
        if self.request_count[platform] < config.RATE_LIMIT['burst_limit']:
            self.request_count[platform] += 1
            return True
            
        return False

rate_limiter = RateLimiter()

def with_rate_limit(platform):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not config.RATE_LIMIT['enabled']:
                return func(*args, **kwargs)
                
            retry_count = 0
            while retry_count < config.REQUEST_SETTINGS['max_retries']:
                if rate_limiter.can_make_request(platform):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Error in {platform} request: {str(e)}")
                        retry_count += 1
                        if retry_count >= config.REQUEST_SETTINGS['max_retries']:
                            raise
                        time.sleep(config.REQUEST_SETTINGS['backoff_factor'] * (2 ** retry_count))
                else:
                    time.sleep(config.RATE_LIMIT['retry_after'])
                    retry_count += 1
            
            raise Exception(f"Rate limit exceeded for {platform}")
        return wrapper
    return decorator

@with_rate_limit("Instagram")
def search_instagram(username):
    return search_profile(username, "Instagram")

@with_rate_limit("Twitter")
def search_twitter(username):
    return search_profile(username, "Twitter")

@with_rate_limit("Facebook")
def search_facebook(username):
    return search_profile(username, "Facebook")

@with_rate_limit("LinkedIn")
def search_linkedin(username):
    return search_profile(username, "LinkedIn")

@with_rate_limit("GitHub")
def search_github(username):
    return search_profile(username, "GitHub")

def basic_osint_search(username):
    """Pencarian OSINT dasar untuk username"""
    results = {
        'found': False,
        'data': {},
        'possible_matches': []
    }
    
    try:
        # Coba cari di platform utama
        twitter_results = search_twitter(username)
        if twitter_results.get('found'):
            results['found'] = True
            results['data']['twitter'] = twitter_results['data']
            
        instagram_results = search_instagram(username)
        if instagram_results.get('found'):
            results['found'] = True
            results['data']['instagram'] = instagram_results['data']
            
        github_results = search_github(username)
        if github_results.get('found'):
            results['found'] = True
            results['data']['github'] = github_results['data']
            
        # Tambahkan pencarian platform lain sesuai kebutuhan
            
        return results
    except Exception as e:
        logger.error(f"Error in basic OSINT search: {str(e)}")
        return {'found': False, 'error': str(e)}

def search_name_across_platforms(full_name):
    """
    Melakukan pencarian nama lengkap di berbagai platform dengan metode intensif
    """
    results = {
        'found': False,
        'platforms': {},
        'possible_matches': [],
        'metadata': {}
    }
    
    try:
        # 1. Normalisasi nama
        name_parts = full_name.lower().split()
        possible_usernames = []
        
        # Generate kemungkinan username
        possible_usernames.extend([
            ''.join(name_parts),  # johndoe
            '.'.join(name_parts),  # john.doe
            '_'.join(name_parts),  # john_doe
            name_parts[0] + name_parts[-1],  # johndoe
            name_parts[0][0] + name_parts[-1],  # jdoe
            name_parts[0] + name_parts[-1][0],  # johnd
        ])
        
        # 2. Cari di setiap platform
        for platform in SEARCH_PLATFORMS:
            platform_results = {'found': False, 'data': []}
            
            try:
                # Coba cari dengan nama lengkap
                if platform == 'facebook':
                    results_fb = search_facebook_advanced(None, None, full_name)
                    if results_fb.get('found'):
                        platform_results['found'] = True
                        platform_results['data'].append(results_fb['data'])
                        
                elif platform == 'linkedin':
                    results_li = search_linkedin_advanced(full_name)
                    if results_li.get('status') == 'success':
                        platform_results['found'] = True
                        platform_results['data'].append(results_li['data'])
                        
                # Coba setiap kemungkinan username
                for username in possible_usernames:
                    if platform == 'twitter':
                        results_tw = search_twitter(username)
                    elif platform == 'instagram':
                        results_ig = search_instagram(username)
                    elif platform == 'github':
                        results_gh = search_github(username)
                        
                    if results.get('found'):
                        platform_results['found'] = True
                        platform_results['data'].append(results.get('data', {}))
                        
            except Exception as e:
                logger.error(f"Error searching {platform}: {str(e)}")
                continue
                
            if platform_results['found']:
                results['found'] = True
                results['platforms'][platform] = platform_results['data']
                
        # 3. Tambahkan metadata tambahan
        try:
            # Cek Google untuk informasi publik
            google_results = search_google(full_name)
            if google_results:
                results['metadata']['google'] = google_results
                
            # Cek LinkedIn untuk informasi profesional
            linkedin_results = search_linkedin_advanced(full_name)
            if linkedin_results.get('status') == 'success':
                results['metadata']['professional'] = linkedin_results['data']
                
            # Cek situs berita
            news_results = search_news(full_name)
            if news_results:
                results['metadata']['news'] = news_results
                
        except Exception as e:
            logger.error(f"Error gathering metadata: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in name search across platforms: {str(e)}")
        results['error'] = str(e)
        
    return results

def search_google(query):
    """Mencari informasi di Google"""
    results = []
    try:
        search_url = f"https://www.google.com/search?q={query}"
        response = requests.get(search_url, headers=config.HEADERS)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            search_results = soup.find_all('div', class_='g')
            
            for result in search_results[:5]:  # Ambil 5 hasil pertama
                title = result.find('h3')
                link = result.find('a')
                snippet = result.find('div', class_='VwiC3b')
                
                if title and link and snippet:
                    results.append({
                        'title': title.text,
                        'url': link['href'],
                        'snippet': snippet.text
                    })
                    
    except Exception as e:
        logger.error(f"Error in Google search: {str(e)}")
        
    return results

def search_news(query):
    """Mencari berita terkait nama"""
    results = []
    try:
        search_url = f"https://www.google.com/search?q={query}&tbm=nws"
        response = requests.get(search_url, headers=config.HEADERS)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            news_results = soup.find_all('div', class_='g')
            
            for result in news_results[:3]:  # Ambil 3 berita teratas
                title = result.find('h3')
                link = result.find('a')
                snippet = result.find('div', class_='VwiC3b')
                
                if title and link and snippet:
                    results.append({
                        'title': title.text,
                        'url': link['href'],
                        'snippet': snippet.text
                    })
                    
    except Exception as e:
        logger.error(f"Error in news search: {str(e)}")
        
    return results

def format_name_search_results(results):
    """Format hasil pencarian berdasarkan nama lengkap"""
    if not results:
        return "❌ Terjadi kesalahan saat memformat hasil pencarian nama."
        
    try:
        formatted_text = "👤 *HASIL PENCARIAN NAMA*\n" + "="*30 + "\n\n"
        
        if not results.get('found'):
            formatted_text += "❌ *Tidak ditemukan hasil yang cocok*\n\n"
            formatted_text += "💡 *Saran:*\n"
            formatted_text += "• Coba gunakan nama lengkap\n"
            formatted_text += "• Periksa ejaan nama\n"
            formatted_text += "• Coba gunakan variasi nama\n"
            return formatted_text
            
        # Format hasil per platform
        if results.get('platforms'):
            for platform, data in results['platforms'].items():
                if data:  # Pastikan data tidak None
                    formatted_text += f"{get_platform_emoji(platform)} *{platform.upper()}*\n"
                    
                    for profile in data:
                        if isinstance(profile, dict):  # Pastikan profile adalah dictionary
                            formatted_text += "├─ 👤 "
                            if profile.get('name'):
                                formatted_text += f"*{escape_markdown(profile['name'])}*"
                            if profile.get('username'):
                                formatted_text += f" (@{escape_markdown(profile['username'])})"
                            formatted_text += "\n"
                            
                            if profile.get('bio'):
                                formatted_text += f"├─ 📝 {escape_markdown(profile['bio'][:100])}...\n"
                            if profile.get('location'):
                                formatted_text += f"├─ 📍 {escape_markdown(profile['location'])}\n"
                            if profile.get('work'):
                                formatted_text += f"├─ 💼 {escape_markdown(profile['work'])}\n"
                            if profile.get('education'):
                                formatted_text += f"├─ 🎓 {escape_markdown(profile['education'])}\n"
                                
                            # Statistik profil
                            stats = []
                            if profile.get('followers'): 
                                stats.append(f"👥 {profile['followers']} pengikut")
                            if profile.get('friends'): 
                                stats.append(f"👥 {profile['friends']} teman")
                            if profile.get('posts'): 
                                stats.append(f"📝 {profile['posts']} post")
                            if stats:
                                formatted_text += f"├─ 📊 {' | '.join(stats)}\n"
                                
                            if profile.get('url'):
                                formatted_text += f"└─ 🔗 {escape_markdown(profile['url'])}\n"
                            formatted_text += "\n"
                        
        # Tampilkan kemungkinan profil terkait
        if results.get('possible_matches'):
            formatted_text += "\n🔍 *Profil Terkait:*\n"
            for match in results['possible_matches'][:3]:
                formatted_text += f"• {escape_markdown(match.get('name', ''))} "
                if match.get('platform'):
                    formatted_text += f"({get_platform_emoji(match['platform'])} {match['platform']})\n"
                else:
                    formatted_text += "\n"
                    
        # Tampilkan metadata tambahan jika ada
        if results.get('metadata'):
            formatted_text += "\nℹ️ *Informasi Tambahan:*\n"
            for key, value in results['metadata'].items():
                if isinstance(value, dict):
                    formatted_text += f"• {key}:\n"
                    for k, v in value.items():
                        formatted_text += f"  - {escape_markdown(str(k))}: {escape_markdown(str(v))}\n"
                else:
                    formatted_text += f"• {key}: {escape_markdown(str(value))}\n"
                
        return formatted_text
        
    except Exception as e:
        logger.error(f"Error formatting name search results: {str(e)}")
        return f"❌ Terjadi kesalahan saat memformat hasil: {str(e)}"

def search_instagram_advanced(driver, wait, username):
    """
    Pencarian lanjutan untuk profil Instagram menggunakan multiple metode dan fallback.
    
    Args:
        driver: Instance WebDriver Selenium
        wait: Instance WebDriverWait
        username: Username Instagram yang akan dicari
        
    Returns:
        dict: Hasil pencarian dengan format lengkap
    """
    results = {
        'found': False,
        'data': {
            'username': username,
            'url': f"https://www.instagram.com/{username}/",
            'status': 'searching'
        },
        'error': None
    }
    
    try:
        # 1. Coba akses dengan multiple user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1'
        ]
        
        for user_agent in user_agents:
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            driver.get(results['data']['url'])
            time.sleep(3)
            
            if "Sorry, this page isn't available." not in driver.page_source and "Page Not Found" not in driver.page_source:
                break
                
        # 2. Cek apakah profil ditemukan
        if "Sorry, this page isn't available." not in driver.page_source and "Page Not Found" not in driver.page_source:
            results['found'] = True
            results['data']['status'] = 'found'
            
            # 3. Multiple selector strategies untuk setiap elemen
            selectors = {
                'name': [
                    "h2._aacl._aacs._aact._aacx._aada",
                    "h1._aacl._aacs._aact._aacx._aada",
                    "//h1[contains(@class, 'x1lliihq')]",
                    "//h2[contains(@class, 'x1lliihq')]",
                    "//div[contains(@class, '_aa_c')]//span"
                ],
                'bio': [
                    "div._aa_c",
                    "//div[contains(@class, '_aa_c')]",
                    "//div[contains(@class, 'x7a106')]//span",
                    "//div[contains(@class, 'xieb3on')]"
                ],
                'stats': [
                    "span._ac2a",
                    "//span[contains(@class, '_ac2a')]",
                    "//span[contains(@class, 'x1lliihq')]",
                    "//div[contains(@class, '_aa_7')]//span"
                ],
                'profile_pic': [
                    "img._aadp",
                    "//img[contains(@class, '_aadp')]",
                    "//img[contains(@alt, 'profile picture')]",
                    "//div[contains(@class, '_aarf')]//img"
                ]
            }
            
            # 4. Fungsi helper untuk mencoba multiple selectors
            def try_selectors(selector_list, by_xpath=False):
                for selector in selector_list:
                    try:
                        if by_xpath:
                            element = driver.find_element(By.XPATH, selector)
                        else:
                            element = driver.find_element(By.CSS_SELECTOR, selector)
                        return element
                    except:
                        continue
                return None
            
            # 5. Ambil nama dengan multiple attempts
            try:
                name_element = try_selectors(selectors['name']) or try_selectors(selectors['name'], True)
                if name_element:
                    results['data']['name'] = name_element.text.strip()
                else:
                    # Fallback: Coba ambil dari meta tags
                    try:
                        name = driver.find_element(By.XPATH, "//meta[@property='og:title']").get_attribute('content')
                        if name:
                            results['data']['name'] = name.split('(')[0].strip()
                    except:
                        results['data']['name'] = username
            except:
                results['data']['name'] = username
                
            # 6. Ambil bio dengan multiple attempts
            try:
                bio_element = try_selectors(selectors['bio']) or try_selectors(selectors['bio'], True)
                if bio_element:
                    results['data']['bio'] = bio_element.text.strip()
                else:
                    # Fallback: Coba ambil dari meta description
                    try:
                        bio = driver.find_element(By.XPATH, "//meta[@property='og:description']").get_attribute('content')
                        if bio:
                            results['data']['bio'] = bio
                    except:
                        results['data']['bio'] = "Bio tidak tersedia"
            except:
                results['data']['bio'] = "Bio tidak tersedia"
                
            # 7. Ambil statistik dengan multiple attempts
            try:
                stats_elements = driver.find_elements(By.CSS_SELECTOR, selectors['stats'][0])
                if not stats_elements:
                    for selector in selectors['stats'][1:]:
                        stats_elements = driver.find_elements(By.XPATH, selector)
                        if stats_elements and len(stats_elements) >= 3:
                            break
                
                if stats_elements and len(stats_elements) >= 3:
                    # Parse angka dengan handling berbagai format
                    def parse_count(text):
                        try:
                            text = text.lower().strip()
                            if 'k' in text:
                                return int(float(text.replace('k', '')) * 1000)
                            elif 'm' in text:
                                return int(float(text.replace('m', '')) * 1000000)
                            else:
                                return int(text.replace(',', '').replace('.', ''))
                        except:
                            return 0
                    
                    results['data']['posts'] = parse_count(stats_elements[0].text)
                    results['data']['followers'] = parse_count(stats_elements[1].text)
                    results['data']['following'] = parse_count(stats_elements[2].text)
            except:
                results['data']['posts'] = 0
                results['data']['followers'] = 0
                results['data']['following'] = 0
                
            # 8. Cek verifikasi dan privasi dengan multiple metode
            try:
                results['data']['is_verified'] = any([
                    "verified" in driver.page_source.lower(),
                    len(driver.find_elements(By.CSS_SELECTOR, "span[title='Verified']")) > 0,
                    len(driver.find_elements(By.XPATH, "//*[contains(@aria-label, 'Verified')]")) > 0
                ])
                
                results['data']['is_private'] = any([
                    "This Account is Private" in driver.page_source,
                    "Akun Ini Privat" in driver.page_source,
                    len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Private Account')]")) > 0,
                    len(driver.find_elements(By.XPATH, "//*[contains(text(), 'Akun Privat')]")) > 0
                ])
            except:
                results['data']['is_verified'] = False
                results['data']['is_private'] = False
                
            # 9. Ambil URL profil dan kategori dengan multiple attempts
            try:
                external_url_elements = driver.find_elements(By.XPATH, "//a[contains(@rel, 'me') or contains(@rel, 'nofollow')]")
                for element in external_url_elements:
                    url = element.get_attribute('href')
                    if url and not url.startswith('https://www.instagram.com'):
                        results['data']['external_url'] = url
                        break
            except:
                results['data']['external_url'] = None
                
            # 10. Ambil foto profil dengan multiple attempts
            try:
                profile_pic_element = try_selectors(selectors['profile_pic']) or try_selectors(selectors['profile_pic'], True)
                if profile_pic_element:
                    results['data']['profile_pic'] = profile_pic_element.get_attribute('src')
                else:
                    # Fallback: Coba ambil dari meta image
                    try:
                        profile_pic = driver.find_element(By.XPATH, "//meta[@property='og:image']").get_attribute('content')
                        if profile_pic:
                            results['data']['profile_pic'] = profile_pic
                    except:
                        results['data']['profile_pic'] = None
            except:
                results['data']['profile_pic'] = None
                
            # 11. Tambahan: Coba ambil kategori/jenis akun
            try:
                category_elements = driver.find_elements(By.XPATH, 
                    "//*[contains(@class, 'x1lliihq') and contains(text(), 'Creator') or contains(text(), 'Business')]"
                )
                if category_elements:
                    results['data']['category'] = category_elements[0].text.strip()
                else:
                    results['data']['category'] = "Personal Account"
            except:
                results['data']['category'] = "Personal Account"
                
        else:
            results['data']['status'] = 'not_found'
            results['error'] = f"Profil Instagram @{username} tidak ditemukan"
            
    except Exception as e:
        logger.error(f"Error saat mengakses profil Instagram {username}: {str(e)}")
        results['error'] = f"Gagal mengakses profil Instagram: {str(e)}"
        results['data']['status'] = 'error'
        
    return results

def search_linkedin_advanced(driver, wait, username):
    """Pencarian profil LinkedIn dengan metode advanced"""
    results = {
        'found': False,
        'data': {
            'username': username,
            'name': '',
            'headline': '',
            'location': '',
            'company': '',
            'education': '',
            'connections': '',
            'url': '',
            'profile_image': ''
        },
        'error': None
    }
    
    try:
        # Login ke LinkedIn jika kredensial tersedia
        if hasattr(config, 'LINKEDIN_EMAIL') and hasattr(config, 'LINKEDIN_PASSWORD'):
            driver.get('https://www.linkedin.com/login')
            wait.until(EC.presence_of_element_located((By.ID, 'username'))).send_keys(config.LINKEDIN_EMAIL)
            wait.until(EC.presence_of_element_located((By.ID, 'password'))).send_keys(config.LINKEDIN_PASSWORD)
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))).click()
            time.sleep(3)  # Tunggu login selesai
            
        # Coba akses profil langsung
        profile_url = f'https://www.linkedin.com/in/{username}'
        driver.get(profile_url)
        time.sleep(2)
        
        # Cek apakah profil ditemukan
        if 'Page not found' not in driver.title and 'This profile is not available' not in driver.page_source:
            results['found'] = True
            results['data']['url'] = profile_url
            
            try:
                # Ambil nama
                name_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.text-heading-xlarge')))
                results['data']['name'] = name_elem.text.strip()
                
                # Ambil headline
                headline_elem = driver.find_element(By.CSS_SELECTOR, '.text-body-medium')
                if headline_elem:
                    results['data']['headline'] = headline_elem.text.strip()
                
                # Ambil lokasi
                location_elem = driver.find_element(By.CSS_SELECTOR, '.text-body-small.inline.t-black--light.break-words')
                if location_elem:
                    results['data']['location'] = location_elem.text.strip()
                
                # Ambil info perusahaan saat ini
                try:
                    company_elem = driver.find_element(By.CSS_SELECTOR, 'div[aria-label="Current company"]')
                    results['data']['company'] = company_elem.text.strip()
                except:
                    pass
                
                # Ambil info pendidikan
                try:
                    education_elem = driver.find_element(By.CSS_SELECTOR, 'div[aria-label="Education"]')
                    results['data']['education'] = education_elem.text.strip()
                except:
                    pass
                
                # Ambil jumlah koneksi
                try:
                    connections_elem = driver.find_element(By.CSS_SELECTOR, '.t-bold')
                    if 'connections' in connections_elem.text.lower():
                        results['data']['connections'] = connections_elem.text.strip()
                except:
                    pass
                
                # Ambil foto profil
                try:
                    img_elem = driver.find_element(By.CSS_SELECTOR, '.pv-top-card-profile-picture__image')
                    results['data']['profile_image'] = img_elem.get_attribute('src')
                except:
                    pass
                    
            except Exception as e:
                logger.warning(f"Error extracting LinkedIn profile details: {str(e)}")
                
        else:
            # Jika profil tidak ditemukan, coba cari melalui pencarian LinkedIn
            driver.get('https://www.linkedin.com/search/results/people/')
            time.sleep(2)
            
            search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input.search-global-typeahead__input')))
            search_box.send_keys(username)
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)
            
            # Cek hasil pencarian pertama
            try:
                first_result = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.entity-result__title-text a')))
                results['found'] = True
                results['data']['url'] = first_result.get_attribute('href')
                results['data']['name'] = first_result.text.strip()
                
                # Ambil headline dari hasil pencarian
                try:
                    headline = driver.find_element(By.CSS_SELECTOR, '.entity-result__primary-subtitle').text.strip()
                    results['data']['headline'] = headline
                except:
                    pass
                    
                # Ambil lokasi dari hasil pencarian
                try:
                    location = driver.find_element(By.CSS_SELECTOR, '.entity-result__secondary-subtitle').text.strip()
                    results['data']['location'] = location
                except:
                    pass
            except:
                results['error'] = 'Profil tidak ditemukan'
                
    except Exception as e:
        logger.error(f"Error in LinkedIn search: {str(e)}")
        results['error'] = f"Terjadi error: {str(e)}"
        
    return results

def search_twitter_advanced(driver, wait, username):
    """Pencarian advanced untuk Twitter"""
    results = {
        'found': False,
        'data': {
            'username': username,
            'name': '',
            'bio': '',
            'url': f"https://twitter.com/{username}",
            'status': '',
            'followers': 0,
            'following': 0,
            'tweets': 0
        },
        'error': None
    }
    
    try:
        driver.get(results['data']['url'])
        
        try:
            wait.until(EC.presence_of_element_located(('css selector', 'div[data-testid="primaryColumn"]')))
            results['found'] = True
            
            try:
                results['data']['name'] = driver.find_element('css selector', 'div[data-testid="UserName"] span').text.strip()
            except: pass
            
            try:
                results['data']['bio'] = driver.find_element('css selector', 'div[data-testid="UserDescription"]').text.strip()
            except: pass
            
            # Default ke public karena Twitter profiles biasanya public
            results['data']['status'] = 'public'
            
            # Coba ambil statistik
            try:
                stats = driver.find_elements('css selector', 'div[data-testid="UserProfileStats"] span')
                for stat in stats:
                    text = stat.text.lower()
                    if 'followers' in text:
                        results['data']['followers'] = text.split()[0]
                    elif 'following' in text:
                        results['data']['following'] = text.split()[0]
                    elif 'tweets' in text:
                        results['data']['tweets'] = text.split()[0]
            except: pass
            
        except TimeoutException:
            results['error'] = "Halaman tidak dapat dimuat"
            
    except Exception as e:
        results['error'] = str(e)
        
    return results

def search_facebook_advanced(driver, wait, username):
    """
    Mencari profil Facebook dengan metode lanjutan.
    Mencoba beberapa metode pencarian dan mengumpulkan data detail.
    """
    results = {
        'found': False,
        'data': {},
        'related_accounts': [],
        'error': None
    }
    
    try:
        # 1. Coba akses profil langsung
        profile_url = f"https://www.facebook.com/{username}"
        driver.get(profile_url)
        time.sleep(2)  # Tunggu loading
        
        # Cek apakah halaman berhasil dimuat
        if "Halaman tidak dapat dimuat" not in driver.page_source:
            results['found'] = True
            results['data'] = {
                'username': username,
                'url': profile_url,
                'status': 'found via direct access'
            }
            
            try:
                # Coba ambil nama
                name_element = wait.until(EC.presence_of_element_located((By.XPATH, "//h1")))
                results['data']['name'] = name_element.text.strip()
            except:
                results['data']['name'] = "Tidak ditemukan"
                
            try:
                # Coba ambil lokasi
                location_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Tinggal di') or contains(text(), 'Lives in')]")
                if location_elements:
                    results['data']['location'] = location_elements[0].text.replace("Tinggal di ", "").replace("Lives in ", "").strip()
                else:
                    # Coba cari di bagian About/Tentang
                    driver.get(f"{profile_url}/about")
                    time.sleep(2)
                    location_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Kota') or contains(text(), 'City')]")
                    if location_elements:
                        results['data']['location'] = location_elements[0].text.replace("Kota ", "").replace("City ", "").strip()
            except:
                results['data']['location'] = "Tidak ditemukan"
                
            try:
                # Coba ambil pekerjaan
                work_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Bekerja di') or contains(text(), 'Works at')]")
                if work_elements:
                    results['data']['work'] = work_elements[0].text.replace("Bekerja di ", "").replace("Works at ", "").strip()
                else:
                    # Coba cari di bagian About/Tentang
                    driver.get(f"{profile_url}/about")
                    time.sleep(2)
                    work_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Pekerjaan') or contains(text(), 'Work')]")
                    if work_elements:
                        results['data']['work'] = work_elements[0].text.replace("Pekerjaan ", "").replace("Work ", "").strip()
            except:
                results['data']['work'] = "Tidak ditemukan"
                
            try:
                # Coba ambil pendidikan
                edu_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Bersekolah di') or contains(text(), 'Studied at')]")
                if edu_elements:
                    results['data']['education'] = edu_elements[0].text.replace("Bersekolah di ", "").replace("Studied at ", "").strip()
                else:
                    # Coba cari di bagian About/Tentang
                    driver.get(f"{profile_url}/about")
                    time.sleep(2)
                    edu_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Pendidikan') or contains(text(), 'Education')]")
                    if edu_elements:
                        results['data']['education'] = edu_elements[0].text.replace("Pendidikan ", "").replace("Education ", "").strip()
            except:
                results['data']['education'] = "Tidak ditemukan"
                
            try:
                # Coba ambil jumlah teman
                friends_element = driver.find_elements(By.XPATH, "//div[contains(text(), 'teman') or contains(text(), 'friends')]")
                if friends_element:
                    friends_count = re.search(r'\d+', friends_element[0].text)
                    if friends_count:
                        results['data']['friends'] = friends_count.group()
                    else:
                        results['data']['friends'] = "Tidak dapat dilihat"
                else:
                    results['data']['friends'] = "Tidak dapat dilihat"
            except:
                results['data']['friends'] = "Tidak dapat dilihat"
                
            # Cek status profil (public/private)
            try:
                if "Tidak Dapat Dilihat" in driver.page_source or "Content Not Found" in driver.page_source:
                    results['data']['status'] = "private"
                else:
                    results['data']['status'] = "public"
            except:
                results['data']['status'] = "unknown"
                
        # 2. Jika tidak ditemukan, coba cari dengan nama
        if not results['found']:
            search_url = f"https://www.facebook.com/search/people/?q={username}"
            driver.get(search_url)
            time.sleep(2)
            
            try:
                # Ambil semua hasil pencarian (maksimal 5)
                search_results = wait.until(EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[contains(@class, 'x1yztbdb')]//a[contains(@class, 'x1i10hfl')]")
                ))[:5]
                
                for result in search_results:
                    try:
                        profile_link = result.get_attribute('href')
                        if profile_link and not profile_link.endswith('#'):
                            # Kunjungi setiap profil
                            driver.get(profile_link)
                            time.sleep(2)
                            
                            profile_data = {
                                'username': profile_link.split('/')[-1],
                                'url': profile_link,
                                'name': result.text.strip(),
                                'status': 'found via search'
                            }
                            
                            # Coba ambil data tambahan seperti sebelumnya
                            try:
                                location_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Tinggal di')]")
                                if location_elements:
                                    profile_data['location'] = location_elements[0].text.replace("Tinggal di ", "").strip()
                            except: pass
                            
                            try:
                                work_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Bekerja di')]")
                                if work_elements:
                                    profile_data['work'] = work_elements[0].text.replace("Bekerja di ", "").strip()
                            except: pass
                            
                            try:
                                edu_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Bersekolah di')]")
                                if edu_elements:
                                    profile_data['education'] = edu_elements[0].text.replace("Bersekolah di ", "").strip()
                            except: pass
                            
                            try:
                                friends_element = driver.find_elements(By.XPATH, "//div[contains(text(), 'teman')]")
                                if friends_element:
                                    friends_count = re.search(r'\d+', friends_element[0].text)
                                    if friends_count:
                                        profile_data['friends'] = friends_count.group()
                            except: pass
                            
                            results['related_accounts'].append(profile_data)
                            
                    except Exception as profile_error:
                        logger.error(f"Error processing profile: {str(profile_error)}")
                        continue
                        
                if results['related_accounts']:
                    results['found'] = True
                    # Gunakan akun pertama sebagai data utama jika belum ada
                    if not results['data']:
                        results['data'] = results['related_accounts'][0]
                        
            except Exception as search_error:
                logger.error(f"Error in search method: {str(search_error)}")
                results['error'] = "Gagal melakukan pencarian"
                
    except Exception as e:
        logger.error(f"Error in Facebook advanced search: {str(e)}")
        results['error'] = "Terjadi kesalahan saat mencari profil"
        
    finally:
        return results

def search_github_advanced(driver, wait, username):
    """Pencarian advanced untuk GitHub"""
    results = {'found': False, 'data': {}, 'error': None}
    try:
        url = f"https://github.com/{username}"
        driver.get(url)
        
        try:
            wait.until(EC.presence_of_element_located(('css selector', '.vcard-names')))
            results['found'] = True
            
            profile_data = {
                'username': username,
                'url': url,
                'name': driver.find_element('css selector', '.vcard-fullname').text.strip(),
                'bio': driver.find_element('css selector', '.user-profile-bio').text.strip(),
                'status': 'public'
            }
            
            results['data'] = profile_data
            
        except TimeoutException:
            results['error'] = "Halaman tidak dapat dimuat"
            
    except Exception as e:
        results['error'] = str(e)
        
    return results

def extract_twitter_data(data):
    """
    Mengekstrak data dari respons Twitter API
    """
    try:
        if not data:
            return None
            
        result = {
            'username': data.get('screen_name', ''),
            'name': data.get('name', ''),
            'bio': data.get('description', ''),
            'followers': data.get('followers_count', 0),
            'following': data.get('friends_count', 0),
            'tweets': data.get('statuses_count', 0),
            'verified': data.get('verified', False),
            'created_at': data.get('created_at', ''),
            'location': data.get('location', ''),
            'url': f"https://twitter.com/{data.get('screen_name', '')}"
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error extracting Twitter data: {str(e)}")
        return None

def search_linkedin_selenium(driver, wait, full_name):
    """Pencarian profil LinkedIn menggunakan Selenium"""
    results = {'found': False, 'data': {}, 'error': None}
    
    try:
        # Format nama untuk pencarian
        search_query = full_name.replace(' ', '%20')
        url = f"https://www.linkedin.com/search/results/people/?keywords={search_query}"
        driver.get(url)
        
        try:
            # Tunggu hasil pencarian muncul
            wait.until(EC.presence_of_element_located(('css selector', '.search-results-container')))
            
            # Cari profil pertama yang cocok
            profile_cards = driver.find_elements('css selector', '.search-result__info')
            if profile_cards:
                first_profile = profile_cards[0]
                
                profile_data = {
                    'name': first_profile.find_element('css selector', '.actor-name').text.strip(),
                    'headline': first_profile.find_element('css selector', '.subline-level-1').text.strip(),
                    'location': first_profile.find_element('css selector', '.subline-level-2').text.strip(),
                    'url': first_profile.find_element('css selector', 'a').get_attribute('href'),
                    'status': 'public'
                }
                
                results['found'] = True
                results['data'] = profile_data
                
        except TimeoutException:
            results['error'] = "Halaman tidak dapat dimuat"
            
    except Exception as e:
        results['error'] = str(e)
        
    return results

def format_detailed_results(results):
    """Format hasil pencarian detail"""
    try:
        text = "📊 *HASIL DETAIL PENCARIAN*\n"
        text += "━━━━━━━━━━━━━━━\n\n"
        
        if results.get('found'):
            profile = results.get('data', {})
            
            # Info Dasar
            text += "👤 *INFO DASAR*\n"
            if profile.get('username'):
                text += f"• Username: `{escape_markdown(profile['username'])}`\n"
            if profile.get('name'):
                text += f"• Nama: `{escape_markdown(profile['name'])}`\n"
            if profile.get('url'):
                text += f"• URL: `{escape_markdown(profile['url'])}`\n"
            if profile.get('status'):
                icon = "🔒" if profile['status'].lower() == 'private' else "🔓"
                text += f"• Status: {icon} `{escape_markdown(profile['status'])}`\n"
            text += "\n"
            
            # Bio & Deskripsi
            if profile.get('bio'):
                text += "📝 *BIO/DESKRIPSI*\n"
                text += f"`{escape_markdown(profile['bio'])}`\n\n"
            
            # Statistik
            stats = []
            if profile.get('followers'): stats.append(f"👥 Followers: {profile['followers']}")
            if profile.get('following'): stats.append(f"👣 Following: {profile['following']}")
            if profile.get('posts'): stats.append(f"📱 Posts: {profile['posts']}")
            if profile.get('friends'): stats.append(f"👥 Friends: {profile['friends']}")
            if profile.get('tweets'): stats.append(f"🐦 Tweets: {profile['tweets']}")
            
            if stats:
                text += "📊 *STATISTIK*\n"
                text += "• " + "\n• ".join([f"`{escape_markdown(stat)}`" for stat in stats]) + "\n\n"
            
            # Metadata tambahan
            if profile.get('metadata'):
                text += "ℹ️ *METADATA TAMBAHAN*\n"
                for key, value in profile['metadata'].items():
                    if isinstance(value, dict):
                        text += f"• {key}:\n"
                        for k, v in value.items():
                            text += f"  \\- {k}: `{escape_markdown(str(v))}`\n"
                    else:
                        text += f"• {key}: `{escape_markdown(str(value))}`\n"
                text += "\n"
            
            # Kemungkinan profil terkait
            if profile.get('possible_matches'):
                text += "🔍 *PROFIL TERKAIT*\n"
                for match in profile['possible_matches'][:3]:
                    text += f"• Username: `{escape_markdown(match.get('username', ''))}`\n"
                    if match.get('url'): 
                        text += f"  URL: `{escape_markdown(match['url'])}`\n"
                text += "\n"
                
        else:
            text += "❌ *PROFIL TIDAK DITEMUKAN*\n"
            if results.get('error'):
                text += f"\n⚠️ *Error:* `{escape_markdown(results['error'])}`\n"
            
        return text
    except Exception as e:
        logger.error(f"Error formatting detailed results: {str(e)}")
        return "❌ *Terjadi kesalahan saat memformat hasil detail*"

def start(update, context):
    """Handler untuk command /start"""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Sosmed Finder", callback_data='sosmed_finder'),
            InlineKeyboardButton("👥 Cari Nama", callback_data='search_name')
        ],
        [
            InlineKeyboardButton("🌐 Basic OSINT", callback_data='basic_osint'),
            InlineKeyboardButton("⚙️ Advanced", callback_data='advanced')
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data='help')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "*🤖 SELAMAT DATANG DI OSINT BOT*\n\n"
        "Bot ini akan membantu Anda mencari informasi tentang:\n"
        "• Username di berbagai platform\n"
        "• Nama lengkap seseorang\n"
        "• Data OSINT dasar\n\n"
        "Silakan pilih menu di bawah ini:",
        parse_mode='MarkdownV2',
        reply_markup=reply_markup
    )

def help_command(update, context):
    """Handler untuk command /help"""
    update.message.reply_text(
        "*📖 PANDUAN PENGGUNAAN BOT*\n\n"
        "*Commands:*\n"
        "• `/f username` \\- cari Facebook\n"
        "• `/i username` \\- cari Instagram\n"
        "• `/t username` \\- cari Twitter\n"
        "• `/l username` \\- cari LinkedIn\n"
        "• `/g username` \\- cari GitHub\n"
        "• `/m username` \\- cari Medium\n\n"
        "*Tips:*\n"
        "• Gunakan username yang tepat\n"
        "• Tambahkan @ di depan username untuk akurasi lebih baik\n"
        "• Gunakan tanda kutip untuk nama lengkap\n",
        parse_mode='MarkdownV2'
    )

def facebook_search(update, context):
    """Handler untuk command /f"""
    if len(context.args) < 1:
        update.message.reply_text(
            "❌ *Format Salah*\n\n"
            "Gunakan format: `/f username`\n"
            "Contoh: `/f johndoe`",
            parse_mode='MarkdownV2'
        )
        return
        
    username = context.args[0]
    temp_message = update.message.reply_text(
        f"🔍 *Mencari profil Facebook:* `{escape_markdown(username)}`\\.\\.\\.",
        parse_mode='MarkdownV2'
    )
    
    try:
        results = search_facebook(username)
        formatted_results = format_search_results(results, "Facebook")
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_fb_{username}'),
                InlineKeyboardButton("📊 Detail", callback_data=f'detail_fb_{username}')
            ],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        temp_message.edit_text(
            formatted_results,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in Facebook search: {str(e)}")
        temp_message.edit_text(
            f"❌ *Terjadi kesalahan:* `{escape_markdown(str(e))}`",
            parse_mode='MarkdownV2'
        )

def instagram_search(update, context):
    """Handler untuk command /i"""
    if len(context.args) < 1:
        update.message.reply_text(
            "❌ *Format Salah*\n\n"
            "Gunakan format: `/i username`\n"
            "Contoh: `/i johndoe`",
            parse_mode='MarkdownV2'
        )
        return
        
    username = context.args[0]
    temp_message = update.message.reply_text(
        f"🔍 *Mencari profil Instagram:* `{escape_markdown(username)}`\\.\\.\\.",
        parse_mode='MarkdownV2'
    )
    
    try:
        results = search_instagram(username)
        formatted_results = format_search_results(results, "Instagram")
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_ig_{username}'),
                InlineKeyboardButton("📊 Detail", callback_data=f'detail_ig_{username}')
            ],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        temp_message.edit_text(
            formatted_results,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in Instagram search: {str(e)}")
        temp_message.edit_text(
            f"❌ *Terjadi kesalahan:* `{escape_markdown(str(e))}`",
            parse_mode='MarkdownV2'
        )

def twitter_search(update, context):
    """Handler untuk command /t"""
    if len(context.args) < 1:
        update.message.reply_text(
            "❌ *Format Salah*\n\n"
            "Gunakan format: `/t username`\n"
            "Contoh: `/t johndoe`",
            parse_mode='MarkdownV2'
        )
        return
        
    username = context.args[0]
    temp_message = update.message.reply_text(
        f"🔍 *Mencari profil Twitter:* `{escape_markdown(username)}`\\.\\.\\.",
        parse_mode='MarkdownV2'
    )
    
    try:
        results = search_twitter(username)
        formatted_results = format_search_results(results, "Twitter")
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_tw_{username}'),
                InlineKeyboardButton("📊 Detail", callback_data=f'detail_tw_{username}')
            ],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        temp_message.edit_text(
            formatted_results,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in Twitter search: {str(e)}")
        temp_message.edit_text(
            f"❌ *Terjadi kesalahan:* `{escape_markdown(str(e))}`",
            parse_mode='MarkdownV2'
        )

def menu_command(update, context):
    """Menampilkan menu utama bot"""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Sosmed Finder", callback_data='sosmed_finder'),
            InlineKeyboardButton("👥 Cari Nama", callback_data='search_name')
        ],
        [
            InlineKeyboardButton("🌐 Basic OSINT", callback_data='basic_osint'),
            InlineKeyboardButton("⚙️ Advanced", callback_data='advanced')
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data='help')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "*🤖 OSINT BOT MENU*\n\n"
        "*Basic Commands:*\n"
        "• /cari [query] - Pencarian umum\n"
        "• /ig [username] - Cek Instagram\n"
        "• /email [email] - Validasi email\n"
        "• /deep [query] - Deep OSINT search\n\n"
        "*Advanced Commands:*\n"
        "• /scan [domain/IP] - Advanced scanning\n"
        "• /breach [email] - Cek data breach\n"
        "• /domain [domain] - Domain intelligence\n"
        "• /phone [nomor] - Phone intelligence\n\n"
        "Pilih menu di bawah untuk informasi lebih lanjut 👇"
    )
    
    update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def button(update, context):
    """Handle button clicks"""
    query = update.callback_query
    query.answer()
    
    # Menu Sosmed Finder
    if query.data == 'sosmed_finder':
        text = (
            "*🔍 SOSMED FINDER*\n\n"
            "Pilih platform untuk mencari username:\n\n"
            "• `/f username` - Cari di Facebook\n"
            "• `/i username` - Cari di Instagram\n"
            "• `/t username` - Cari di Twitter\n"
            "• `/g username` - Cari di GitHub\n"
            "• `/l username` - Cari di LinkedIn\n\n"
            "Contoh: `/i johndoe`"
        )
        keyboard = [
            [
                InlineKeyboardButton("Facebook", callback_data='search_fb'),
                InlineKeyboardButton("Instagram", callback_data='search_ig')
            ],
            [
                InlineKeyboardButton("Twitter", callback_data='search_tw'),
                InlineKeyboardButton("GitHub", callback_data='search_gh')
            ],
            [
                InlineKeyboardButton("LinkedIn", callback_data='search_li'),
                InlineKeyboardButton("🔙 Kembali", callback_data='menu')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')

    # Menu Utama
    elif query.data == 'menu':
        keyboard = [
            [
                InlineKeyboardButton("🔍 Sosmed Finder", callback_data='sosmed_finder'),
                InlineKeyboardButton("👥 Cari Nama", callback_data='search_name')
            ],
            [
                InlineKeyboardButton("🌐 Basic OSINT", callback_data='basic_osint'),
                InlineKeyboardButton("⚙️ Advanced", callback_data='advanced')
            ],
            [
                InlineKeyboardButton("ℹ️ Help", callback_data='help')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = (
            "*🤖 SELAMAT DATANG DI OSINT BOT*\n\n"
            "Bot ini akan membantu Anda mencari informasi tentang:\n"
            "• Username di berbagai platform\n"
            "• Nama lengkap seseorang\n"
            "• Data OSINT dasar\n\n"
            "Silakan pilih menu di bawah ini:"
        )
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')

    # Menu Pencarian Nama
    elif query.data == 'search_name':
        text = (
            "*🔍 PENCARIAN NAMA*\n\n"
            "Untuk memulai pencarian nama, gunakan format berikut:\n\n"
            "• `/nama John Doe` - Contoh: `/nama Steve Jobs`\n\n"
            "*Informasi yang akan didapat:*\n"
            "• Nama lengkap\n"
            "• Lokasi\n"
            "• Pekerjaan\n"
            "• Pendidikan\n"
            "• Social Media\n"
            "• Status profil"
        )
        keyboard = [
            [
                InlineKeyboardButton("📖 Tutorial", callback_data='tutorial_name'),
                InlineKeyboardButton("❓ FAQ", callback_data='faq_name')
            ],
            [
                InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data='menu')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')

    # Handle tombol pencarian platform spesifik
    elif query.data.startswith('search_'):
        platform = query.data.split('_')[1]
        text = (
            f"*🔍 PENCARIAN DI {platform.upper()}*\n\n"
            "Untuk memulai pencarian, kirim username dengan format:\n\n"
        )
        
        if platform == 'fb':
            text += "• `/f username` - Contoh: `/f johndoe`\n\n"
            text += "*Informasi yang akan didapat:*\n"
            text += "• Nama lengkap\n• Lokasi\n• Pekerjaan\n• Pendidikan\n• Jumlah teman\n• Status profil"
        elif platform == 'ig':
            text += "• `/i username` - Contoh: `/i johndoe`\n\n"
            text += "*Informasi yang akan didapat:*\n"
            text += "• Nama lengkap\n• Bio\n• Jumlah followers\n• Jumlah following\n• Jumlah post\n• Status profil"
        elif platform == 'tw':
            text += "• `/t username` - Contoh: `/t johndoe`\n\n"
            text += "*Informasi yang akan didapat:*\n"
            text += "• Nama lengkap\n• Bio\n• Jumlah followers\n• Jumlah following\n• Jumlah tweets\n• Status verifikasi"
        elif platform == 'gh':
            text += "• `/g username` - Contoh: `/g johndoe`\n\n"
            text += "*Informasi yang akan didapat:*\n"
            text += "• Nama lengkap\n• Bio\n• Repositories\n• Followers\n• Following\n• Kontribusi"
        elif platform == 'li':
            text += "• `/l username` - Contoh: `/l johndoe`\n\n"
            text += "*Informasi yang akan didapat:*\n"
            text += "• Nama lengkap\n• Headline\n• Pengalaman\n• Pendidikan\n• Skills\n• Koneksi"
            
        keyboard = [
            [
                InlineKeyboardButton("📖 Tutorial", callback_data=f'tutorial_{platform}'),
                InlineKeyboardButton("❓ FAQ", callback_data=f'faq_{platform}')
            ],
            [
                InlineKeyboardButton("🔙 Kembali", callback_data='sosmed_finder'),
                InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')

    # Handle tutorial untuk setiap platform
    elif query.data.startswith('tutorial_'):
        platform = query.data.split('_')[1]
        text = f"*📖 TUTORIAL PENCARIAN {platform.upper()}*\n\n"
        
        if platform == 'fb':
            text += (
                "*Langkah-langkah:*\n"
                "1. Gunakan command `/f username`\n"
                "2. Username bisa berupa:\n"
                "   • Username Facebook\n"
                "   • Nama profil\n"
                "   • ID Facebook\n\n"
                "*Tips:*\n"
                "• Pastikan username sudah benar\n"
                "• Coba variasi username\n"
                "• Gunakan nama lengkap jika perlu"
            )
        elif platform == 'ig':
            text += (
                "*Langkah-langkah:*\n"
                "1. Gunakan command `/i username`\n"
                "2. Username harus:\n"
                "   • Tanpa karakter @\n"
                "   • Tanpa spasi\n"
                "   • Sesuai profil Instagram\n\n"
                "*Tips:*\n"
                "• Cek spelling username\n"
                "• Perhatikan underscore (_)\n"
                "• Coba cari di bio Instagram"
            )
        elif platform == 'tw':
            text += (
                "*Langkah-langkah:*\n"
                "1. Gunakan command `/t username`\n"
                "2. Username Twitter:\n"
                "   • Tanpa @\n"
                "   • Case sensitive\n"
                "   • Max 15 karakter\n\n"
                "*Tips:*\n"
                "• Cek handle Twitter\n"
                "• Perhatikan huruf besar/kecil\n"
                "• Cari di bio Twitter"
            )
        elif platform == 'gh':
            text += (
                "*Langkah-langkah:*\n"
                "1. Gunakan command `/g username`\n"
                "2. Username GitHub:\n"
                "   • Case sensitive\n"
                "   • Tanpa spasi\n"
                "   • Alfanumerik & dash\n\n"
                "*Tips:*\n"
                "• Cek URL GitHub\n"
                "• Lihat kontributor repo\n"
                "• Cari di organisasi"
            )
        elif platform == 'li':
            text += (
                "*Langkah-langkah:*\n"
                "1. Gunakan command `/l username`\n"
                "2. Username LinkedIn:\n"
                "   • Dari URL profil\n"
                "   • Nama-nama profil\n"
                "   • Email profil\n\n"
                "*Tips:*\n"
                "• Gunakan nama lengkap\n"
                "• Cek URL profil\n"
                "• Cari di perusahaan"
            )
            
        keyboard = [
            [
                InlineKeyboardButton("🔍 Mulai Cari", callback_data=f'search_{platform}'),
                InlineKeyboardButton("❓ FAQ", callback_data=f'faq_{platform}')
            ],
            [
                InlineKeyboardButton("🔙 Kembali", callback_data=f'search_{platform}'),
                InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')

    # Handle FAQ untuk setiap platform
    elif query.data.startswith('faq_'):
        platform = query.data.split('_')[1]
        text = f"*❓ FAQ PENCARIAN {platform.upper()}*\n\n"
        
        if platform == 'fb':
            text += (
                "*Q: Mengapa profil tidak ditemukan?*\n"
                "A: • Profil mungkin private\n"
                "   • Username salah\n"
                "   • Profil sudah dihapus\n\n"
                "*Q: Apakah bisa cari dengan email?*\n"
                "A: Ya, gunakan format `/f email@domain.com`\n\n"
                "*Q: Data apa saja yang bisa didapat?*\n"
                "A: • Info profil dasar\n"
                "   • Foto profil (jika public)\n"
                "   • Status aktivitas\n"
                "   • Informasi publik lainnya"
            )
        elif platform == 'ig':
            text += (
                "*Q: Profil private bisa dicek?*\n"
                "A: Hanya info dasar yang tersedia\n\n"
                "*Q: Bisa lihat story/highlight?*\n"
                "A: Tidak, hanya info profil publik\n\n"
                "*Q: Berapa lama hasil search valid?*\n"
                "A: Data real-time saat pencarian\n\n"
                "*Q: Bisa cari dengan nama lengkap?*\n"
                "A: Gunakan `/cari` untuk pencarian nama"
            )
        elif platform == 'tw':
            text += (
                "*Q: Akun suspended bisa dicek?*\n"
                "A: Tidak, hanya akun aktif\n\n"
                "*Q: Bisa lihat tweet protected?*\n"
                "A: Tidak, hanya tweet publik\n\n"
                "*Q: Data real-time?*\n"
                "A: Ya, menggunakan Twitter API\n\n"
                "*Q: Bisa cek follower/following?*\n"
                "A: Ya, jumlah dan status verifikasi"
            )
        elif platform == 'gh':
            text += (
                "*Q: Private repo bisa dilihat?*\n"
                "A: Tidak, hanya repo publik\n\n"
                "*Q: Bisa cek organisasi?*\n"
                "A: Ya, jika status publik\n\n"
                "*Q: Data kontribusi akurat?*\n"
                "A: Ya, dari GitHub API\n\n"
                "*Q: Bisa cek gist?*\n"
                "A: Ya, gist publik termasuk"
            )
        elif platform == 'li':
            text += (
                "*Q: Perlu login LinkedIn?*\n"
                "A: Tidak, pencarian tanpa login\n\n"
                "*Q: Info pekerjaan akurat?*\n"
                "A: Sesuai update terakhir profil\n\n"
                "*Q: Bisa lihat koneksi?*\n"
                "A: Hanya jumlah, tidak detail\n\n"
                "*Q: Data endorsement tersedia?*\n"
                "A: Ya, jika profil publik"
            )
            
        keyboard = [
            [
                InlineKeyboardButton("🔍 Mulai Cari", callback_data=f'search_{platform}'),
                InlineKeyboardButton("📖 Tutorial", callback_data=f'tutorial_{platform}')
            ],
            [
                InlineKeyboardButton("🔙 Kembali", callback_data=f'search_{platform}'),
                InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')

    # Handle refresh dan detail view
    elif query.data.startswith(('refresh_', 'detail_')):
        action, platform, username = query.data.split('_')
        
        if action == 'refresh':
            if platform == 'fb':
                results = search_facebook(username)
            elif platform == 'ig':
                results = search_instagram(username)
            elif platform == 'tw':
                results = search_twitter(username)
            elif platform == 'gh':
                results = search_github(username)
            elif platform == 'li':
                results = search_linkedin_selenium(None, None, username)
                
            formatted_results = format_search_results(results, platform)
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_{platform}_{username}'),
                    InlineKeyboardButton("📊 Detail", callback_data=f'detail_{platform}_{username}')
                ],
                [
                    InlineKeyboardButton("🔙 Kembali", callback_data=f'search_{platform}'),
                    InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=formatted_results, reply_markup=reply_markup, parse_mode='MarkdownV2')
            
        elif action == 'detail':
            if platform == 'fb':
                results = search_facebook(username)
            elif platform == 'ig':
                results = search_instagram(username)
            elif platform == 'tw':
                results = search_twitter(username)
            elif platform == 'gh':
                results = search_github(username)
            elif platform == 'li':
                results = search_linkedin_selenium(None, None, username)
                
            formatted_results = format_detailed_results(results)
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_{platform}_{username}'),
                    InlineKeyboardButton("🔙 Kembali", callback_data=f'search_{platform}')
                ],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(text=formatted_results, reply_markup=reply_markup, parse_mode='MarkdownV2')

    else:
        query.edit_message_text(
            "*⚙️ Fitur Dalam Pengembangan*\n\n"
            "Mohon maaf, fitur ini sedang dalam tahap pengembangan.\n"
            "Silakan coba fitur lain yang tersedia.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Kembali ke Menu", callback_data='menu')
            ]])
        )

def cari_command(update, context):
    """Handler untuk command /cari [query]"""
    if not context.args:
        update.message.reply_text(
            "❌ Format: /cari [query]\n"
            "Contoh:\n"
            "• /cari John Doe\n"
            "• /cari johndoe123"
        )
        return
    
    query = ' '.join(context.args)
    status_message = update.message.reply_text("🔍 Memulai pencarian...")
    
    try:
        # Track penggunaan command
        track_user(update.effective_user.id, update.effective_user.username)
        
        # Lakukan pencarian
        results = deep_osint_search(query)
        formatted_text = format_search_results(results, "Social Media")
        
        # Edit pesan dengan hasil
        status_message.edit_text(formatted_text, parse_mode='Markdown')
        
        # Tambahkan tombol aksi
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_search_{query}'),
                InlineKeyboardButton("📊 Detail", callback_data=f'search_detail_{query}')
            ],
            [
                InlineKeyboardButton("🏠 Menu", callback_data='menu')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "✨ Pencarian selesai! Pilih aksi selanjutnya:",
            reply_markup=reply_markup
        )
            
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        status_message.edit_text(f"❌ Error: {str(e)}")

def track_user(user_id, username=None):
    """Melacak pengguna yang menggunakan bot"""
    global daily_users, total_monthly_users
    
    # Reset jika sudah hari baru
    current_date = datetime.now().date()
    if current_date > last_reset_date:
        daily_users.clear()
        
    # Reset jika sudah bulan baru    
    if current_date.replace(day=1) > last_monthly_reset:
        total_monthly_users.clear()
    
    # Tambahkan ke statistik
    daily_users.add(user_id)
    total_monthly_users.add(user_id)
    
    # Log aktivitas
    user_info = f"ID: {user_id}"
    if username:
        user_info += f", Username: @{username}"
    logger.info(f"Pengguna menggunakan bot - {user_info}")

def deep_osint_search(query):
    """Melakukan pencarian OSINT mendalam"""
    results = {
        'found': False,
        'data': {},
        'error': None
    }
    
    try:
        # Cari di social media
        social_results = {}
        for platform in SEARCH_PLATFORMS:
            try:
                if platform == 'twitter':
                    platform_results = search_twitter(query)
                elif platform == 'facebook':
                    platform_results = search_facebook(query)
                elif platform == 'instagram':
                    platform_results = search_instagram(query)
                elif platform == 'github':
                    platform_results = search_github(query)
                
                if platform_results.get('found'):
                    results['found'] = True
                    social_results[platform] = platform_results['data']
            except Exception as e:
                logger.error(f"Error searching {platform}: {str(e)}")
                continue
        
        if social_results:
            results['data']['social_media'] = social_results
            
        # Cari kemungkinan username terkait
        variations = generate_username_variations(query)
        possible_matches = []
        for var in variations[:5]:
            for platform in SEARCH_PLATFORMS:
                match = quick_check_username(var, platform)
                if match:
                    possible_matches.append(match)
        
        if possible_matches:
            results['data']['possible_matches'] = possible_matches
            
        # Cek arsip web
        for platform in SEARCH_PLATFORMS:
            archived = check_web_archives(query, platform)
            if archived and not archived.get('error'):
                if 'archived_data' not in results['data']:
                    results['data']['archived_data'] = {}
                results['data']['archived_data'][platform] = archived
                
        # Tambahkan metadata
        for platform in SEARCH_PLATFORMS:
            metadata = gather_additional_metadata(query, platform)
            if metadata:
                if 'metadata' not in results['data']:
                    results['data']['metadata'] = {}
                results['data']['metadata'][platform] = metadata
                
    except Exception as e:
        logger.error(f"Deep search error: {str(e)}")
        results['error'] = str(e)
        
    return results

def error_handler(update, context):
    """Menangani error yang terjadi saat bot berjalan"""
    try:
        logger.error(f"Update {update} caused error {context.error}")
        
        error_message = "❌ *Terjadi Kesalahan*\n\n"
        
        if isinstance(context.error, TimeoutException):
            error_message += "Timeout saat mengakses halaman. Silakan coba lagi."
        elif isinstance(context.error, WebDriverException):
            error_message += "Gagal mengakses browser. Silakan coba lagi."
        else:
            error_message += f"Error: {str(context.error)}"
            
        if update.effective_message:
            update.effective_message.reply_text(
                error_message,
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}")

def search_name_command(update, context):
    """Handle command /nama untuk mencari berdasarkan nama lengkap"""
    if not context.args:
        update.message.reply_text(
            "⚠️ Format yang benar: /nama <nama_lengkap>\n\n"
            "Contoh:\n"
            "/nama John Doe\n"
            "/nama Mark Zuckerberg"
        )
        return
    
    full_name = ' '.join(context.args)
    update.message.reply_text(f"🔍 Mencari informasi untuk nama: {full_name}...")
    
    try:
        results = search_name_across_platforms(full_name)
        formatted_text = format_name_search_results(results)  # Menghapus parameter full_name
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_name_{full_name}'),
                InlineKeyboardButton("📊 Detail", callback_data=f'detail_name_{full_name}')
            ],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data='menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            formatted_text,
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in name search: {str(e)}")
        update.message.reply_text(
            f"❌ *Terjadi kesalahan:* `{escape_markdown(str(e))}`",
            parse_mode='MarkdownV2'
        )

def setup_bot():
    """Setup bot instance"""
    try:
        bot = telegram.Bot(token=config.TELEGRAM_TOKEN)
        return bot
    except Exception as e:
        logger.error(f"Error setting up bot: {str(e)}")
        raise e

def setup_handlers(dp):
    """Setup message handlers"""
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("menu", menu_command))
    dp.add_handler(CommandHandler("cari", cari_command))
    dp.add_handler(CommandHandler("nama", search_name_command))
    dp.add_handler(CommandHandler("f", facebook_search))
    dp.add_handler(CommandHandler("i", instagram_search))
    dp.add_handler(CommandHandler("t", twitter_search))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_error_handler(error_handler)

def main():
    """Run bot in polling mode for local development"""
    try:
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher
        setup_handlers(dp)
        logger.info("Bot started in polling mode...")
        updater.start_polling()
        updater.idle()
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        raise e

if __name__ == '__main__':
    main()