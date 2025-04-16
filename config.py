# config.py
# Simpen semua konfigurasi di sini, biar gampang diedit

# Token bot dari BotFather
TELEGRAM_TOKEN = ""

# API Keys
HUNTER_IO_API_KEY = ""
HIBP_API_KEY = ""  # Have I Been Pwned API key
DEHASHED_API_KEY = ""  # DeHashed API key
EMAILREP_API_KEY = ""  # EmailRep API key
SHODAN_API_KEY = ""  # Shodan API key
ABUSEIPDB_API_KEY = ""  # AbuseIPDB API key
NUMVERIFY_API_KEY = ""  # NumVerify API key untuk tracking lokasi realtime
CENSYS_API_ID = ""  # Censys API ID
CENSYS_API_SECRET = ""  # Censys API Secret
WAPPALYZER_API_KEY = ""  # Wappalyzer API key

# Social Media API Keys
TWITTER_API_KEY = ""  # Twitter API Key
TWITTER_API_SECRET = ""  # Twitter API Secret
TWITTER_BEARER_TOKEN = None  # Ganti dengan token Twitter Anda

GITHUB_API_TOKEN = None  # Ganti dengan token GitHub Anda

INSTAGRAM_API_KEY = None  # Ganti dengan API key Instagram Anda
INSTAGRAM_APP_SECRET = ""  # Instagram App Secret

LINKEDIN_API_KEY = ""  # LinkedIn API Key
LINKEDIN_API_SECRET = ""  # LinkedIn API Secret

FACEBOOK_APP_ID = ""  # Facebook App ID
FACEBOOK_APP_SECRET = ""  # Facebook App Secret

YOUTUBE_API_KEY = None  # Ganti dengan API key YouTube Anda

TIKTOK_API_KEY = ""  # TikTok API Key
TIKTOK_API_SECRET = ""  # TikTok API Secret

REDDIT_CLIENT_ID = None  # Ganti dengan client ID Reddit Anda
REDDIT_CLIENT_SECRET = None  # Ganti dengan client secret Reddit Anda

GITLAB_API_TOKEN = None  # Ganti dengan token GitLab Anda

MEDIUM_API_TOKEN = None  # Ganti dengan token Medium Anda

DEVTO_API_KEY = None  # Ganti dengan API key Dev.to Anda

# Search Settings
DEEP_SEARCH_TIMEOUT = 30  # Timeout untuk deep search dalam detik
MAX_BREACH_RESULTS = 10  # Maksimum hasil data breach yang ditampilkan
SEARCH_PLATFORMS = [
    'twitter',
    'instagram',
    'github',
    'reddit',
    'linkedin',
    'facebook',
    'tiktok',
    'youtube',
    'gitlab',
    'medium',
    'devto'
]

# API Endpoints
API_ENDPOINTS = {
    'twitter': 'https://api.twitter.com/2/users/by/username/{}',
    'github': 'https://api.github.com/users/{}',
    'instagram': 'https://graph.instagram.com/{}',
    'youtube': 'https://www.googleapis.com/youtube/v3/channels?part=snippet&forUsername={}',
    'reddit': 'https://www.reddit.com/user/{}/about.json',
    'gitlab': 'https://gitlab.com/api/v4/users?username={}',
    'medium': 'https://api.medium.com/v1/users/{}',
    'devto': 'https://dev.to/api/users/by_username?url={}'
}

# Header buat scraping
SCRAPE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

# URL untuk pencarian
GOOGLE_SEARCH_URL = "https://www.google.com/search?q={query}"
INSTAGRAM_BASE_URL = "https://www.instagram.com/{username}/"
DEHASHED_API_URL = "https://api.dehashed.com/search?query={query}"
EMAILREP_API_URL = "https://emailrep.io/{email}"
ABUSEIPDB_API_URL = "https://api.abuseipdb.com/api/v2/check"

# Default email domain
DEFAULT_EMAIL_DOMAIN = "gmail.com"

# Timeout dan retry settings
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 1

# Proxy settings (uncomment dan sesuaikan jika diperlukan)
PROXY_SETTINGS = {
    "http": None,  # "socks5h://127.0.0.1:9050" # Contoh untuk Tor
    "https": None  # "socks5h://127.0.0.1:9050"
}

# Selenium settings
SELENIUM_SETTINGS = {
    "page_load_timeout": 30,
    "implicit_wait": 10,
    "explicit_wait": 15,
    "headless": True,
    "disable_gpu": True,
    "disable_webgl": True,
    "no_sandbox": True,
    "disable_dev_shm": True
}

# Request settings
REQUEST_SETTINGS = {
    "timeout": 30,
    "max_retries": 3,
    "backoff_factor": 0.5,
    "verify_ssl": True,
    "allow_redirects": True
}

# Rate limiting
RATE_LIMIT = {
    "enabled": True,
    "requests_per_second": 1,
    "burst_limit": 3,
    "retry_after": 5
}

# Error messages
ERROR_MESSAGES = {
    "api_key_missing": "❌ API key tidak ditemukan di config",
    "request_failed": "❌ Gagal melakukan request ke server",
    "parsing_error": "❌ Gagal memproses data",
    "not_found": "❌ Data tidak ditemukan",
    "rate_limit": "❌ Terlalu banyak request, coba lagi nanti",
    "timeout": "❌ Pencarian timeout, coba lagi",
    "proxy_error": "❌ Error koneksi proxy",
    "breach_error": "❌ Gagal mengecek data breach",
    "unknown": "❌ Terjadi error yang tidak diketahui"
}

# Search result settings
MAX_SOCIAL_RESULTS = 5  # Maksimum hasil pencarian social media
MAX_EMAIL_RESULTS = 5   # Maksimum hasil pencarian email
MAX_PHONE_RESULTS = 3   # Maksimum hasil pencarian nomor telepon

# Advanced OSINT Settings
ADVANCED_SCAN_TIMEOUT = 60  # Timeout untuk advanced scan dalam detik
MAX_PORTS_TO_SCAN = 1000  # Maksimum port yang akan di-scan
SUBDOMAIN_SCAN_DEPTH = 2  # Kedalaman pencarian subdomain
VULNERABILITY_SEVERITY_THRESHOLD = 7.0  # Minimum CVSS score untuk alert
TECH_STACK_DETECTION = True  # Enable/disable deteksi teknologi
SSL_CERT_CHECK = True  # Enable/disable pengecekan sertifikat SSL
DNS_RECORD_TYPES = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'SOA']  # Record DNS yang dicek

# Network Scan Settings
NMAP_SCAN_TYPES = {
    'quick': '-F -T4',  # Fast scan
    'full': '-sS -sV -T4 -A',  # Full scan with service detection
    'stealth': '-sS -T2'  # Stealth scan
}

# API Tokens
TWITTER_API_TOKEN = "YOUR_TWITTER_API_TOKEN"
GITHUB_API_TOKEN = "YOUR_GITHUB_API_TOKEN" 
INSTAGRAM_API_TOKEN = "YOUR_INSTAGRAM_API_TOKEN"
YOUTUBE_API_TOKEN = "YOUR_YOUTUBE_API_TOKEN"
REDDIT_API_TOKEN = "YOUR_REDDIT_API_TOKEN"
GITLAB_API_TOKEN = "YOUR_GITLAB_API_TOKEN"
MEDIUM_API_TOKEN = "YOUR_MEDIUM_API_TOKEN"
DEVTO_API_TOKEN = "YOUR_DEVTO_API_TOKEN"

# API Endpoints
TWITTER_API_ENDPOINT = "https://api.twitter.com/2/users/by/username/"
GITHUB_API_ENDPOINT = "https://api.github.com/users/"
INSTAGRAM_API_ENDPOINT = "https://www.instagram.com/"
YOUTUBE_API_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"
REDDIT_API_ENDPOINT = "https://www.reddit.com/user/"
GITLAB_API_ENDPOINT = "https://gitlab.com/api/v4/users"
MEDIUM_API_ENDPOINT = "https://api.medium.com/v1/users/"
DEVTO_API_ENDPOINT = "https://dev.to/api/users/by_username"

# Platforms to search
SEARCH_PLATFORMS = [
    "twitter",
    "github", 
    "instagram",
    "youtube",
    "reddit",
    "gitlab",
    "medium",
    "dev.to"
]

# Rate limiting delay in seconds
RATE_LIMIT_DELAY = 1

# Headers for web scraping
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Error messages
ERROR_MESSAGES = {
    "API_ERROR": "Terjadi kesalahan saat mengakses API: {}",
    "RATE_LIMIT": "Rate limit tercapai untuk platform {}",
    "NO_RESULTS": "Tidak ditemukan hasil untuk username {}",
    "INVALID_TOKEN": "API token tidak valid untuk platform {}"
}

# Success messages
SUCCESS_MESSAGES = {
    "SEARCH_START": "Memulai pencarian untuk username {}...",
    "SEARCH_COMPLETE": "Pencarian selesai! Ditemukan {} hasil",
    "PLATFORM_SUCCESS": "Berhasil mendapatkan data dari {}"
}

# Maximum retries for API requests
MAX_RETRIES = 3

# Timeout for API requests (in seconds)
REQUEST_TIMEOUT = 10

# Cache settings
CACHE_ENABLED = True
CACHE_DURATION = 3600  # 1 hour in seconds

# Chrome Settings
CHROME_SETTINGS = {
    'arguments': [
        '--headless',
        '--disable-gpu',
        '--disable-software-rasterizer',
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--disable-webgl',
        '--disable-notifications',
        '--disable-popup-blocking',
        '--disable-infobars',
        '--disable-extensions',
        '--disable-logging',
        '--log-level=3',
        '--silent',
        '--blink-settings=imagesEnabled=false'
    ],
    'prefs': {
        'profile.default_content_setting_values.notifications': 2,
        'profile.default_content_setting_values.images': 2,
        'profile.default_content_setting_values.cookies': 2,
        'profile.default_content_setting_values.plugins': 2,
        'profile.default_content_setting_values.popups': 2,
        'profile.default_content_setting_values.geolocation': 2,
        'profile.default_content_setting_values.media_stream': 2,
        'profile.managed_default_content_settings.images': 2,
        'profile.managed_default_content_settings.cookies': 2,
        'download.default_directory': '/dev/null',
        'download.prompt_for_download': False,
        'download.directory_upgrade': True
    },
    'timeouts': {
        'implicit': 5,
        'pageLoad': 15,
        'script': 15
    }
}
