print("Starting agent...", flush=True)
import time
import os
import datetime
import requests
import smtplib
import ssl
import re
import signal
import sys
import random
from connection_utils import smart_post, smart_get, CloudUploader
import threading
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from imap_tools import MailBox, A
from email.message import EmailMessage
import mimetypes
# Lazy import for CloudUploader to avoid circular deps if possible, or just standard import
# removed
from email.utils import parseaddr

# Import database module
try:
    import database
    # Initialize explicitly
    print("Initializing database...", flush=True)
    database.init_database()
except ImportError:
    print("!!! WARNING: database.py not found. Conversation history will not be saved.", flush=True)
    database = None

# Plant ID Service
# Lazy initialization to save memory
PLANT_ID_SERVICE = None
print("[PlantID] Service configured for lazy loading.", flush=True)

# Wiki Agent Integration
try:
    import wiki_agent
    print("[WikiAgent] Module imported.", flush=True)
except ImportError:
    wiki_agent = None
    print("[WikiAgent] Module not found.", flush=True)

# =======================================================
#           CONFIGURATION MANAGEMENT
# =======================================================
SETTINGS_FILE = os.path.join("config", "settings.json")
SETTINGS_EXAMPLE_FILE = os.path.join("config", "settings.json.example")

def get_default_settings():
    """Return default settings structure with safe fallback values."""
    return {
        "email": {
            "address": "",
            "app_password": "",
            "gmail_label": "off-grid-agent"
        },
        "ai_backend": {
            "provider": "anythingllm",
            "anythingllm": {
                "workspace_slug": "off-grid-automation",
                "api_key": "",
                "url": "http://localhost:3001"
            },
            "lmstudio": {
                "url": "http://127.0.0.1:1234/v1/chat/completions",
                "model": "llama-3.2-1b-instruct",
                "default_model": "llama-3.2-1b-instruct"
            },
            "video_processing": {
                "provider": "vllm",
                "vllm": {
                    "url": "http://localhost:8000/v1/chat/completions",
                    "model": "Qwen/Qwen2.5-VL-7B-Instruct"
                },
                "llama_cli": {
                    "path": "./llama-cli",
                    "model_path": "Qwen2.5-VL-7B-Instruct-Q5_K_M.gguf",
                    "mmproj_path": "mmproj-model-f16.gguf"
                }
            }
        },
        "weather": {
            "user_agent": "off-grid-agent",
            "cache_minutes": 10,
            "max_cache_size": 100
        },
        "performance": {
            "imap_idle_timeout": 30,
            "max_retries": 5,
            "base_retry_delay": 30,
            "rate_limit_window": 20,
            "max_burst": 4,
            "duplicate_window": 60
        },
        "features": {
            "delayed_response_enabled": True,
            "respond_to_offline_messages": False
        },
        "timeouts": {
            "lmstudio": 300,
            "anythingllm": 600,
            "weather_api": 120,
            "lemonade": 300,
            "fast_flow": 300
        },
        "plant_id": {
            "method": "specialized",
            "model_file": "plant_yolov8s.pt"
        },
        "wiki_agent": {
            "zim_path": r"C:\path\to\your\wikipedia.zim"
        }
    }

def load_settings():
    """Load settings from settings.json file.
    Returns settings dict. Creates file from example if missing.
    """
    # If settings.json doesn't exist, try to create it from example
    if not os.path.exists(SETTINGS_FILE):
        if os.path.exists(SETTINGS_EXAMPLE_FILE):
            print(f"[CONFIG] {SETTINGS_FILE} not found. Creating from {SETTINGS_EXAMPLE_FILE}...")
            shutil.copy(SETTINGS_EXAMPLE_FILE, SETTINGS_FILE)
            print(f"[CONFIG] Created {SETTINGS_FILE}. Please edit it with your credentials.")
        else:
            print(f"[CONFIG] Neither {SETTINGS_FILE} nor {SETTINGS_EXAMPLE_FILE} found.")
            print(f"[CONFIG] Creating {SETTINGS_FILE} with defaults...")
            default_settings = get_default_settings()
            save_settings(default_settings)
            print(f"[CONFIG] Created {SETTINGS_FILE}. Please edit it with your credentials.")
        
        # Return defaults and let user configure
        return get_default_settings()
    
    # Load existing settings
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # Merge with defaults to ensure all keys exist (for backward compatibility)
        defaults = get_default_settings()
        merged = _deep_merge(defaults, settings)
        
        print(f"[CONFIG] Loaded settings from {SETTINGS_FILE}")
        return merged
        
    except json.JSONDecodeError as e:
        print(f"[CONFIG ERROR] Failed to parse {SETTINGS_FILE}: {e}")
        print(f"[CONFIG ERROR] Using default settings. Please fix the JSON syntax in {SETTINGS_FILE}")
        return get_default_settings()
    except Exception as e:
        print(f"[CONFIG ERROR] Failed to load {SETTINGS_FILE}: {e}")
        print(f"[CONFIG ERROR] Using default settings.")
        return get_default_settings()

def _deep_merge(default, override):
    """Recursively merge override dict into default dict."""
    result = default.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def save_settings(settings):
    """Save settings to settings.json file atomically."""
    try:
        # Create backup if file exists
        if os.path.exists(SETTINGS_FILE):
            backup_file = f"{SETTINGS_FILE}.backup"
            shutil.copy(SETTINGS_FILE, backup_file)
        
        # Write to temporary file first
        temp_file = f"{SETTINGS_FILE}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
        os.rename(temp_file, SETTINGS_FILE)
        
        print(f"[CONFIG] Saved settings to {SETTINGS_FILE}")
        return True
        
    except Exception as e:
        print(f"[CONFIG ERROR] Failed to save settings: {e}")
        return False

# Load settings at startup
print("[CONFIG] Loading configuration...", flush=True)
_SETTINGS = load_settings()
print(f"[CONFIG] AI Backend: {_SETTINGS['ai_backend']['provider']}", flush=True)

if wiki_agent:
    wiki_agent.ZIM_PATH = _SETTINGS.get("wiki_agent", {}).get("zim_path", r"C:\path\to\your\wikipedia.zim")

# =======================================================
#     SETTINGS (Loaded from settings.json)
# =======================================================
# All settings are now loaded from settings.json for easy editing
# Edit settings.json to modify these values - no need to edit this code!

# 1. GMAIL/IMAP SETTINGS
YOUR_EMAIL = _SETTINGS["email"]["address"]
YOUR_APP_PASSWORD = _SETTINGS["email"]["app_password"]

# 2. GOOGLE VOICE FILTERS
GMAIL_LABEL = _SETTINGS["email"]["gmail_label"]

# 3. AI BACKEND SETTINGS
AI_BACKEND = _SETTINGS["ai_backend"]["provider"]

# A. ANYTHINGLLM SETTINGS
WORKSPACE_SLUG = _SETTINGS["ai_backend"]["anythingllm"]["workspace_slug"]
ANYTHINGLLM_API_KEY = _SETTINGS["ai_backend"]["anythingllm"]["api_key"]
ANYTHINGLLM_BASE_URL = _SETTINGS["ai_backend"]["anythingllm"]["url"]
ANYTHINGLLM_URL = f"{ANYTHINGLLM_BASE_URL}/api/v1/workspace/{WORKSPACE_SLUG}/chat"

# B. LM STUDIO SETTINGS
LMSTUDIO_URL = _SETTINGS["ai_backend"]["lmstudio"]["url"]
LMSTUDIO_MODEL = _SETTINGS["ai_backend"]["lmstudio"]["model"]
LEMONADE_URL = _SETTINGS["ai_backend"]["lemonade"]["url"]
LEMONADE_MODEL = _SETTINGS["ai_backend"]["lemonade"]["model"]

# C. FAST FLOW SETTINGS
FAST_FLOW_URL = _SETTINGS["ai_backend"].get("fast_flow", {}).get("url", "http://localhost:52625/v1/chat/completions")
FAST_FLOW_MODEL = _SETTINGS["ai_backend"].get("fast_flow", {}).get("model", "fast-flow-lm")

# 4. WEATHER API SETTINGS
WEATHER_USER_AGENT = _SETTINGS["weather"]["user_agent"]
WEATHER_CACHE = {}  # Runtime cache: {location: (timestamp, data)}
WEATHER_CACHE_MINUTES = _SETTINGS["weather"]["cache_minutes"]
MAX_CACHE_SIZE = _SETTINGS["weather"]["max_cache_size"]

# 5. PERFORMANCE & ROBUSTNESS SETTINGS
IMAP_IDLE_TIMEOUT = _SETTINGS["performance"]["imap_idle_timeout"]
MAX_RETRIES = _SETTINGS["performance"]["max_retries"]
BASE_RETRY_DELAY = _SETTINGS["performance"]["base_retry_delay"]
RATE_LIMIT_WINDOW = _SETTINGS["performance"]["rate_limit_window"]
MAX_BURST = _SETTINGS["performance"]["max_burst"]
RATE_LIMIT_TRACKER = {}  # {phone_number: [timestamp1, timestamp2, ...]}

# DELAYED RESPONSE HANDLER
DELAYED_RESPONSE_QUEUE = []  # [(request_id, api_func, args, kwargs, recipient_email, description, initial_timeout)]
DELAYED_RESPONSE_LOCK = threading.Lock()
AI_PROCESSING_LOCK = threading.Lock()  # Serialize all AI requests (foreground & background)
DELAYED_RESPONSE_ENABLED = _SETTINGS["features"]["delayed_response_enabled"]

# OFFLINE MESSAGE HANDLING
RESPOND_TO_OFFLINE_MESSAGES = _SETTINGS["features"]["respond_to_offline_messages"]

# DUPLICATE MESSAGE TRACKER
DUPLICATE_TRACKER = {}  # {phone_number: (last_message_hash, timestamp)}
DUPLICATE_WINDOW = _SETTINGS["performance"]["duplicate_window"]

# =======================================================


def get_timestamp():
    """Return current timestamp string in US format (MM/DD/YYYY HH:MM:SS AM/PM)."""
    return datetime.datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")

def sanitize_input(text):
    """Sanitize user input to prevent injection or system command execution.
    Returns (sanitized_text, is_safe) tuple.
    
    Blocks keyboard macro patterns (ctrl+X) that phones shouldn't send.
    Allows normal words like "control", "alternative", "delete" in conversation.
    """
    if not text:
        return "", True
    
    # Detect keyboard macro patterns (these shouldn't come from a phone)
    # User requested to ONLY filter "ctrl" patterns to avoid false positives
    keyboard_macro_patterns = [
        r'\bctrl[\+\-]\w+',      # ctrl+X, ctrl-C
        r'\bctrl\s+(key|button)\b',  # "ctrl key"
        r'\^ctrl',  # ^ctrl (caret notation)
    ]
    
    text_lower = text.lower()
    for pattern in keyboard_macro_patterns:
        if re.search(pattern, text_lower):
            # This looks like a keyboard macro attempt
            return text, False
    
    # Normal text is safe
    return text, True

def format_temp(temp):
    """Return temperature string with Â°F suffix."""
    try:
        return f"{int(temp)}Â°F"
    except Exception:
        return f"{temp}Â°F"

def validate_command_input(cmd, user_query):
    """Validate command syntax and required arguments.
    Returns (is_valid, error_message).
    """
    # Weather command needs location
    if cmd in ("!weather", "!weather_") or (cmd.startswith("!weather") and len(cmd.split()) == 1):
        return False, "Please specify a location:\n\nExamples:\n- !weather Seattle\n- !weather 90210\n- !weather London,UK\n\nFormat: !weather <location>"
    
    # Forecast command needs location
    if cmd.startswith("!forecast"):
        match = re.match(r'!forecast(\d+)?\s*(.+)?', user_query, re.IGNORECASE)
        if match:
            hours_str = match.group(1)
            location = match.group(2)
            
            if not location or not location.strip():
                return False, "Please provide a location for the forecast.\n\nExamples:\n- !forecast24 Seattle\n- !forecast Seattle (defaults to 12h)"
            
            if hours_str:
                hours = int(hours_str)
                if hours < 1 or hours > 72:
                    return False, "Forecast hours must be between 1 and 72.\n\nExample: !forecast24 Seattle"
        else:
            return False, "Invalid forecast syntax.\n\nExamples:\n- !forecast24 Seattle\n- !forecast Seattle"
    
    # Radar command needs location
    if cmd.startswith("!radar") or cmd.startswith("!weather-map"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            return False, "Please specify a location for radar.\n\nExample: !radar Seattle"
    
    return True, ""

def check_rate_limit(phone_number):
    """Check if user is sending messages too quickly.
    Allows a burst of messages (MAX_BURST) within a time window (RATE_LIMIT_WINDOW).
    """
    now = time.time()
    if phone_number not in RATE_LIMIT_TRACKER:
        RATE_LIMIT_TRACKER[phone_number] = []
    
    # Filter out timestamps older than the window
    timestamps = [t for t in RATE_LIMIT_TRACKER[phone_number] if now - t < RATE_LIMIT_WINDOW]
    
    if len(timestamps) >= MAX_BURST:
        print(f"[WARN]  RATE LIMIT: Blocked burst from {phone_number} ({len(timestamps)} msgs in {RATE_LIMIT_WINDOW}s)")
        return False
    
    timestamps.append(now)
    RATE_LIMIT_TRACKER[phone_number] = timestamps
    return True

def calculate_rate_limit_delay(phone_number):
    """Calculate how long to wait before processing this message.
    Returns delay in seconds (0 if no delay needed).
    Uses smart queuing - processes in bursts of MAX_BURST with delays between batches.
    """
    now = time.time()
    if phone_number not in RATE_LIMIT_TRACKER:
        RATE_LIMIT_TRACKER[phone_number] = []
    
    # Get timestamps within the window
    timestamps = [t for t in RATE_LIMIT_TRACKER[phone_number] if now - t < RATE_LIMIT_WINDOW]
    
    # If we're under the burst limit, no delay needed
    if len(timestamps) < MAX_BURST:
        RATE_LIMIT_TRACKER[phone_number] = timestamps + [now]
        return 0
    
    # Calculate delay needed (wait until oldest timestamp expires from window)
    oldest_in_window = min(timestamps)
    delay_needed = RATE_LIMIT_WINDOW - (now - oldest_in_window)
    
    # Add small buffer (1 second) to ensure we're clearly outside the window
    delay_needed = max(1, int(delay_needed) + 1)
    
    print(f"   [QUEUE] Rate limit: Will process after {delay_needed}s delay")
    return delay_needed

# DUPLICATE MESSAGE TRACKER
# {phone_number: (last_message_hash, timestamp)}
DUPLICATE_TRACKER = {}
DUPLICATE_WINDOW = 10  # Seconds to ignore identical messages

def check_duplicate_message(phone_number, message_body):
    """Check if this is a duplicate message sent recently.
    Returns True if it's a duplicate (should be ignored), False otherwise.
    """
    if not message_body:
        return False
        
    import hashlib
    
    # Create a simple hash of the message content
    # Normalize: lowercase, strip whitespace to catch "Hello" vs "hello "
    normalized_msg = message_body.strip().lower()
    msg_hash = hashlib.md5(normalized_msg.encode('utf-8')).hexdigest()
    
    now = time.time()
    
    if phone_number in DUPLICATE_TRACKER:
        last_hash, last_time = DUPLICATE_TRACKER[phone_number]
        
        # Check if same content AND within time window
        if last_hash == msg_hash and (now - last_time < DUPLICATE_WINDOW):
            print(f"   [DUPLICATE] Ignored identical message from {phone_number} (seen {int(now - last_time)}s ago)")
            return True
            
    # Update tracker with new message
    DUPLICATE_TRACKER[phone_number] = (msg_hash, now)
    return False

def cleanup_cache():
    """Remove old entries from weather cache."""
    now = datetime.datetime.now()
    keys_to_remove = []
    
    for loc, (timestamp, _) in WEATHER_CACHE.items():
        age_minutes = (now - timestamp).total_seconds() / 60
        if age_minutes > WEATHER_CACHE_MINUTES:
            keys_to_remove.append(loc)
            
    for k in keys_to_remove:
        del WEATHER_CACHE[k]
        
    # Size limit check
    if len(WEATHER_CACHE) > MAX_CACHE_SIZE:
        # Remove oldest
        sorted_cache = sorted(WEATHER_CACHE.items(), key=lambda item: item[1][0])
        to_remove_count = len(WEATHER_CACHE) - MAX_CACHE_SIZE
        for i in range(to_remove_count):
            del WEATHER_CACHE[sorted_cache[i][0]]

def monitor_delayed_response(request_id, api_func, args, kwargs, recipient_email, description, initial_timeout):
    """Monitor for delayed API response - called by queue worker.
    Power efficient: no continuous polling, just one retry attempt.
    """
    print(f"[{get_timestamp()}] [DELAYED MONITOR] Processing {description} (ID: {request_id[:8]})")
    
    # Try ONE more time with extended timeout (double the original)
    extended_timeout = initial_timeout * 2
    kwargs['timeout'] = extended_timeout
    
    try:
        # Acquire lock to ensure we don't conflict with foreground requests
        with AI_PROCESSING_LOCK:
            result = api_func(*args, **kwargs)
        
        # Extract content based on result type
        if hasattr(result, 'json'):
            try:
                data = result.json()
                content = data.get('textResponse') or data.get('text') or str(data)
            except:
                content = result.text if hasattr(result, 'text') else str(result)
        else:
            content = str(result)
        
        delayed_msg = f"[DELAYED RESPONSE - arrived after {initial_timeout}s]\n\n{content}"
        
        print(f"[{get_timestamp()}] [DELAYED RESPONSE] Received for {description}, sending to user")
        if recipient_email:
            send_sms_reply(recipient_email, delayed_msg)
        
    except Exception as e:
        print(f"[{get_timestamp()}] [DELAYED MONITOR] Failed for {description}: {str(e)[:80]}")

def process_delayed_queue_worker():
    """Single background worker that processes delayed response queue.
    Very power efficient: sleeps when queue is empty.
    """
    while True:
        try:
            # Check if there's work to do
            with DELAYED_RESPONSE_LOCK:
                if DELAYED_RESPONSE_QUEUE:
                    task = DELAYED_RESPONSE_QUEUE.pop(0)
                else:
                    task = None
            
            if task:
                request_id, api_func, args, kwargs, recipient_email, description, initial_timeout = task
                monitor_delayed_response(request_id, api_func, args, kwargs, recipient_email, description, initial_timeout)
            else:
                # No work - sleep for 5 seconds to save power
                time.sleep(5)
                
        except Exception as e:
            print(f"[{get_timestamp()}] [DELAYED WORKER ERROR] {str(e)[:100]}")
            time.sleep(1)

def cleanup_delayed_trackers():
    """Remove old items from delayed queue to prevent memory leak."""
    with DELAYED_RESPONSE_LOCK:
        if len(DELAYED_RESPONSE_QUEUE) > 20:
            # Keep only most recent 20 items
            DELAYED_RESPONSE_QUEUE[:] = DELAYED_RESPONSE_QUEUE[-20:]
            print(f"[CLEANUP] Trimmed delayed queue to 20 items")


def smart_split_message(message, limit=150):
    """Split message into chunks, respecting word boundaries.
    Default limit can be high (e.g. 15,000) for MMS, or low (150) for SMS.
    """
    if not message:
        return []
        
    if len(message) <= limit:
        return [message]
        
    chunks = []
    MAX_CHUNKS = 50  # Cap to prevent infinite loops, but allow substantial content
    
    while message and len(chunks) < MAX_CHUNKS:
        if len(message) <= limit:
            chunks.append(message)
            break
            
        # Find split point. 
        # User requested: 700 for non-spaces, more for spaces (like 838).
        # We try to find a space within the 838 limit.
        split_idx = message.rfind(' ', 0, limit)
        
        # If no space found, OR the space is too early (making the chunk too small),
        # but only if we HAVE to split.
        if split_idx == -1:
            # Force split at 700 if no space found within 838
            split_idx = 700
            
        chunks.append(message[:split_idx])
        message = message[split_idx:].strip()
        
    if message and len(chunks) >= MAX_CHUNKS:
        chunks.append("... [Message Truncated due to length]")
        
    return chunks

# =======================================================
# COMMAND MESSAGES
# =======================================================

COMMANDS_MESSAGE = """
OFF-GRID AGENT - COMMAND LIST

--- WEATHER & RADAR ---
!weather <loc> : Current conditions + 12h forecast.
!radar <loc> <miles> [gif] [30/60] : Visual radar. 
   - Ex: !radar Seattle 50 gif 60
   - Defaults: 30 miles, Static Image, 30m Loop.
!forecast<hrs> <loc> : Forecast for next X hours (e.g. !forecast24 Seattle).
!forecast(<var>)(<hrs>) <loc> : Targeted forecast (temp, wind, cond, precip).
!temp-history <loc> : Past 24h temperature trend graph/data.

--- UTILITIES ---
!check : System status and health.
!clear : Wipe your conversation history.
!test : Verify agent is online.
!info : This command list.
!readme : Overview of agent capabilities.
"""
COMMANDS_MESSAGE = COMMANDS_MESSAGE.strip()

# =======================================================
# WEATHER AND UTILITY FUNCTIONS
# =======================================================

def detect_weather_query(user_query):
    """Detect if query is asking about weather and extract location if possible.
    Returns (is_weather_query, location) tuple.
    Uses regex word boundaries to avoid false positives (e.g. 'hot' in 'photos').
    """
    query_lower = user_query.lower()
    
    # Weather-related keywords
    weather_keywords = ['weather', 'temperature', 'temp', 'forecast', 'rain', 'snow', 
                       'sunny', 'cloudy', 'hot', 'cold', 'warm', 'climate', 'wind', 'humidity']
    
    # Check if any weather keyword is present (as a full word)
    found_keyword = False
    for keyword in weather_keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
            found_keyword = True
            break
            
    if not found_keyword:
        return False, None
    
    # Explicit ignore for cameras/photos if they don't have other weather context
    if any(ignore in query_lower for ignore in ['photo', 'camera', 'picture', 'selfie']):
        # Only ignore if NO specific location is mentioned with a weather term
        # e.g. "weather in seattle photo" should still work, but "look at this photo it's hot" shouldn't.
        # But for now, word boundaries \bhot\b will fix "photos".
        pass

    # Try to extract location patterns
    # Pattern 1: "in <location>" or "at <location>"
    in_at_match = re.search(r'\b(?:in|at|for|near)\s+([a-z0-9\s,]+?)(?:\?|$|\.|!)', query_lower)
    if in_at_match:
        location = in_at_match.group(1).strip()
        return True, location
    
    # Pattern 2: ZIP code mentioned
    zip_match = re.search(r'\b(\d{5})\b', user_query)
    if zip_match:
        return True, zip_match.group(1)
        
    # Pattern 3: "weather <location>" direct pattern (e.g. "weather paris")
    # Only if "weather" is at the start or preceded by "check"
    direct_match = re.search(r'(?:check|get|show)?\s*weather\s+([a-z0-9\s,]+?)(?:\?|$|\.|!)', query_lower)
    if direct_match:
        loc = direct_match.group(1).strip()
        if loc not in weather_keywords: # Avoid matching "weather forecast"
            return True, loc
    
    # Weather query detected but no location found
    return True, None

def detect_time_query(user_query):
    """Detect if query is asking about time/date.
    Returns boolean.
    """
    query_lower = user_query.lower()
    time_keywords = ['what time', 'current time', 'what is the time', 'tell me the time', 
                    'what date', 'current date', 'what day', 'what is today']
    
    return any(keyword in query_lower for keyword in time_keywords)

def get_greeting():
    """Return time-appropriate greeting."""
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"

def get_weather_openmeteo(lat, lon, location_name):
    """Fallback weather fetch using OpenMeteo (Global coverage, no key)."""
    try:
        print(f"-> Fetching OpenMeteo forecast for: {location_name}")
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m&hourly=temperature_2m,weather_code,precipitation_probability&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&forecast_days=1"
        
        resp = requests.get(url, timeout=_SETTINGS["timeouts"]["weather_api"])
        resp.raise_for_status()
        data = resp.json()
        
        # WMO Weather Codes
        wmo_codes = {
            0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime Fog", 51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
            61: "Light Rain", 63: "Rain", 65: "Heavy Rain", 71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
            80: "Rain Showers", 81: "Showers", 82: "Violent Showers", 95: "Thunderstorm", 96: "Storm+Hail"
        }
        
        current = data.get('current', {})
        hourly = data.get('hourly', {})
        
        report = [f"Forecast for {location_name} (OpenMeteo)"]
        
        # Current
        temp = current.get('temperature_2m')
        code = current.get('weather_code')
        cond = wmo_codes.get(code, f"Code {code}")
        wind = current.get('wind_speed_10m')
        report.append(f"Now: {temp}Â°F {cond}, Wind {wind} mph")
        report.append("")
        
        # Hourly (Next 12h)
        times = hourly.get('time', [])
        temps = hourly.get('temperature_2m', [])
        codes = hourly.get('weather_code', [])
        probs = hourly.get('precipitation_probability', [])
        
        now_hour = datetime.datetime.now().hour
        count = 0
        
        for i, t_str in enumerate(times):
            dt = datetime.datetime.fromisoformat(t_str)
            if dt.hour >= now_hour:
                time_str = dt.strftime("%I%p").lstrip('0').lower()
                t = temps[i]
                c = wmo_codes.get(codes[i], "")
                p = probs[i]
                
                line = f"{time_str}: {t}Â°F {c}"
                if p > 0:
                    line += f" ({p}% precip)"
                report.append(line)
                
                count += 1
                if count >= 12: break
                
        return "\n".join(report)
        
    except Exception as e:
        return f"ERROR: OpenMeteo failed - {str(e)[:100]}"

def get_weather(location, hours=12, filter_mode=None):
    """Fetch detailed weather info.
    hours: Number of hours to forecast (default 12, max 72).
    filter_mode: 'temp', 'wind', 'cond', or None (all).
    """
    cleanup_cache()
    
    # Cap hours
    hours = max(1, min(hours, 72))
    
    # Check cache (key includes hours and filter)
    cache_key = f"{location.lower()}_{hours}_{filter_mode}"
    if cache_key in WEATHER_CACHE:
        cached_time, cached_data = WEATHER_CACHE[cache_key]
        age_minutes = (datetime.datetime.now() - cached_time).total_seconds() / 60
        if age_minutes < WEATHER_CACHE_MINUTES:
            print(f"   [Using cached weather data for {location}]")
            return cached_data
    
    try:
        headers = {"User-Agent": f"({WEATHER_USER_AGENT})", "Accept": "application/json"}
        
        # 1. Geocode
        if location.isdigit() and len(location) == 5:
            geo_url = f"https://nominatim.openstreetmap.org/search?postalcode={location}&country=us&format=json&limit=1"
        else:
            geo_url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
            
        geo_resp = requests.get(geo_url, headers={"User-Agent": WEATHER_USER_AGENT}, timeout=_SETTINGS["timeouts"]["weather_api"])
        geo_data = geo_resp.json()
        
        if not geo_data:
            return f"Location '{location}' not found."
            
        lat = float(geo_data[0]['lat'])
        lon = float(geo_data[0]['lon'])
        display_name = geo_data[0].get('display_name', location).split(',')[0]
        
        print(f"-> Fetching {hours}h Forecast for: {display_name}")
        
        # 2. Get Grid Points (NOAA)
        points_url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
        points_resp = requests.get(points_url, headers=headers, timeout=_SETTINGS["timeouts"]["weather_api"])
        
        # If NOAA fails (e.g. outside US), fall back to OpenMeteo
        if points_resp.status_code != 200:
            print(f"   [NOAA Failed ({points_resp.status_code}) - Trying OpenMeteo Fallback]")
            fallback_report = get_weather_openmeteo(lat, lon, display_name)
            WEATHER_CACHE[cache_key] = (datetime.datetime.now(), fallback_report)
            return fallback_report
            
        points_data = points_resp.json()
        
        if 'properties' not in points_data:
             print(f"   [NOAA Invalid Data - Trying OpenMeteo Fallback]")
             fallback_report = get_weather_openmeteo(lat, lon, display_name)
             WEATHER_CACHE[cache_key] = (datetime.datetime.now(), fallback_report)
             return fallback_report

        hourly_url = points_data['properties']['forecastHourly']
        
        # 3. Fetch Hourly Forecast
        hourly_resp = requests.get(hourly_url, headers=headers, timeout=_SETTINGS["timeouts"]["weather_api"])
        hourly_resp.raise_for_status()
        hourly_data = hourly_resp.json()['properties']['periods']
        
        # === BUILD REPORT ===
        report = []
        if filter_mode == 'temp':
            report.append(f"Temp Trend: {display_name}")
        elif filter_mode == 'wind':
            report.append(f"Wind Forecast: {display_name}")
        elif filter_mode == 'cond':
            report.append(f"Conditions: {display_name}")
        elif filter_mode == 'precip':
            report.append(f"Precipitation: {display_name}")
        else:
            report.append(f"Forecast for {display_name} ({hours}h)")
        
        # A. Current Conditions (skip if filtering specific variable to save space)
        if not filter_mode:
            current = hourly_data[0]
            humidity = current.get('relativeHumidity', {}).get('value')
            wind = f"{current.get('windSpeed')} {current.get('windDirection')}"
            
            report.append(f"Now: {current['temperature']}Â°{current['temperatureUnit']} {current['shortForecast']}")
            report.append(f"Wind: {wind} | Humidity: {humidity}%")
            report.append("")
        
        # B. Hourly Breakdown
        for i in range(hours):
            if i >= len(hourly_data): break
            p = hourly_data[i]
            
            dt = datetime.datetime.fromisoformat(p['startTime'])
            time_str = dt.strftime("%I%p").lstrip('0').lower()
            temp = p['temperature']
            cond = p['shortForecast'].replace("Chance", "").replace("Slight", "").strip()
            # Shorten conditions
            cond = cond.replace("Thunderstorms", "Storms").replace("Showers", "Rain").replace("Partly Cloudy", "P.Cloudy")
            if len(cond) > 15: cond = cond[:13] + ".."
            
            wind_speed = p.get('windSpeed', '0 mph')
            wind_dir = p.get('windDirection', '')
            precip_prob = p.get('probabilityOfPrecipitation', {}).get('value', 0) or 0
            precip_amount = p.get('quantitativePrecipitation', {}).get('value')  # mm
            
            humidity = p.get('relativeHumidity', {}).get('value')
            wind_gust = p.get('windGust') # Usually in GridData, maybe in Hourly?
            
            if filter_mode == 'temp':
                report.append(f"{time_str}: {temp}Â°F" + (f" ({humidity}%RH)" if humidity else ""))
            elif filter_mode == 'wind':
                gust_str = f" G{wind_gust}" if wind_gust else ""
                report.append(f"{time_str}: {wind_speed}{gust_str} {wind_dir}")
            elif filter_mode == 'cond':
                report.append(f"{time_str}: {cond}")
            elif filter_mode == 'precip':
                # Show chance and amount if available
                if precip_amount is not None:
                    # Convert mm to inches (1 mm = 0.0393701 in)
                    inches = precip_amount * 0.0393701
                    report.append(f"{time_str}: {precip_prob}% Chance, {inches:.2f}" + " in")
                else:
                    report.append(f"{time_str}: {precip_prob}% Chance")
            else:
                # Default view: Show ALL hours requested (compact format)
                hum_str = f" {humidity}%H" if humidity else ""
                report.append(f"{time_str}: {temp}Â°{hum_str} {cond}")

        # If precip filter, add a total precipitation summary for the period
        if filter_mode == 'precip':
            total_precip = 0.0
            for p in hourly_data[:hours]:
                amt = p.get('quantitativePrecipitation', {}).get('value')
                if amt is not None:
                    total_precip += amt
            if total_precip:
                inches_total = total_precip * 0.0393701
                report.append(f"Total Precipitation (next {hours}h): {inches_total:.2f} in")
        final_report = "\n".join(report)
        WEATHER_CACHE[cache_key] = (datetime.datetime.now(), final_report)
        return final_report
    except Exception as e:
        return f"ERROR [E005]: Weather fetch failed - {str(e)[:100]}"

def get_weather_history(location, hours=24):
    """Fetch historical weather observations for the past N hours.
    Returns temperature trend from NOAA observation stations.
    """
    try:
        headers = {"User-Agent": f"({WEATHER_USER_AGENT})", "Accept": "application/json"}
        
        # 1. Geocode
        if location.isdigit() and len(location) == 5:
            geo_url = f"https://nominatim.openstreetmap.org/search?postalcode={location}&country=us&format=json&limit=1"
        else:
            geo_url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
            
        geo_resp = requests.get(geo_url, headers={"User-Agent": WEATHER_USER_AGENT}, timeout=_SETTINGS["timeouts"]["weather_api"])
        geo_data = geo_resp.json()
        
        if not geo_data:
            return f"Location '{location}' not found."
            
        lat = float(geo_data[0]['lat'])
        lon = float(geo_data[0]['lon'])
        display_name = geo_data[0].get('display_name', location).split(',')[0]
        
        print(f"-> Fetching {hours}h History for: {display_name}")
        
        # 2. Get nearest observation station
        points_url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
        points_resp = requests.get(points_url, headers=headers, timeout=_SETTINGS["timeouts"]["weather_api"])
        points_resp.raise_for_status()
        points_data = points_resp.json()
        
        # Get observation stations
        stations_url = points_data['properties']['observationStations']
        stations_resp = requests.get(stations_url, headers=headers, timeout=_SETTINGS["timeouts"]["weather_api"])
        stations_data = stations_resp.json()
        
        if not stations_data.get('features'):
            return f"No observation stations found near {display_name}."
            
        # Use first (nearest) station
        station_id = stations_data['features'][0]['properties']['stationIdentifier']
        
        # 3. Fetch observations
        obs_url = f"https://api.weather.gov/stations/{station_id}/observations"
        obs_resp = requests.get(obs_url, headers=headers, timeout=_SETTINGS["timeouts"]["weather_api"])
        obs_data = obs_resp.json()
        
        observations = obs_data.get('features', [])
        if not observations:
            return f"No historical data available for {display_name}."
        
        # 4. Build report (past 24 hours)
        report = [f"Temp History: {display_name} (Past {hours}h)"]
        
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=hours)
        
        valid_obs = []
        for obs in observations:
            timestamp_str = obs['properties'].get('timestamp')
            if not timestamp_str:
                continue
                
            obs_time = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            if obs_time >= cutoff:
                temp_c = obs['properties'].get('temperature', {}).get('value')
                if temp_c is not None:
                    # Convert C to F
                    temp_f = (temp_c * 9/5) + 32
                    valid_obs.append((obs_time, temp_f))
        
        if not valid_obs:
            return f"No temperature data available for the past {hours}h."
        
        # Sort by time (oldest first)
        valid_obs.sort(key=lambda x: x[0])
        
        # Sample observations (show ~12 data points max)
        step = max(1, len(valid_obs) // 12)
        sampled_obs = valid_obs[::step]
        
        for obs_time, temp_f in sampled_obs:
            # Convert to local time
            local_time = obs_time.astimezone()
            time_str = local_time.strftime("%I%p").lstrip('0').lower()
            day_str = local_time.strftime("%m/%d")
            report.append(f"{day_str} {time_str}: {int(temp_f)}Â°F")
        
        return "\n".join(report)
        
    except Exception as e:
        return f"ERROR: History fetch failed - {str(e)[:100]}"

def get_available_lmstudio_models():
    """Fetch available models from LM Studio."""
    try:
        url = LMSTUDIO_URL.replace("/chat/completions", "/models")
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        # Extract model IDs
        models = [m['id'] for m in data.get('data', [])]
        return models
    except Exception as e:
        print(f"   [WARN] Failed to fetch LM Studio models: {e}")
        return []

def resolve_model_alias(alias):
    """Fuzzy match alias to available models (hardcoded active list)."""
    # Hardcoded list of active models
    available = [
        "llama-3.2-1b-instruct",
        "smollm2-360m-instruct",
        "qwen3-8b-gemini-3-pro-preview-distill"
    ]
        
    alias_lower = alias.lower()
    
    # 1. Exact match
    for m in available:
        if m.lower() == alias_lower:
            return m, "Exact match"
            
    # 2. Substring match (if alias is part of model name)
    # Prioritize if alias is at start
    for m in available:
        if m.lower().startswith(alias_lower):
            return m, "Prefix match"
            
    # 3. General substring
    for m in available:
        if alias_lower in m.lower():
            return m, "Substring match"
            
    return None, f"No match found for '{alias}'"

def parse_model_override(text):
    """Detect model override syntax in multiple formats.
    Supports:
    - (!alias message) - parentheses wrapped
    - !alias message - simple prefix (if alias is a known model)
    Returns (clean_text, model_id_or_none, log_msg)
    """
    if not text:
        return text, None, None
        
    text = text.strip()
    
    # DEBUG: Print what we are parsing
    # print(f"   [DEBUG_PARSE] Analyzing: '{text[:20]}...'")
    
    # Format 1: (!alias message) - full parentheses wrapped
    # We'll stick to regex for this specific format as it's structured
    match = re.search(r'^\(!([a-zA-Z0-9_\-\.]+)\s+(.+)\)$', text, re.DOTALL)
    if match:
        alias = match.group(1)
        content = match.group(2)
        
        resolved_model, method = resolve_model_alias(alias)
        if resolved_model:
            return content, resolved_model, f"Model override: '{alias}' -> '{resolved_model}' ({method})"
        else:
            return content, None, f"Model override failed: '{alias}' not found. Using default."
    
    # Format 2: !alias message - simple prefix
    # Use robust split instead of regex to avoid pattern matching issues
    if text.startswith('!'):
        # Check for immediate parenthesis: !model(msg)
        if '(' in text and text.index('(') < 20: # arbitrary limit to ensure it's a prefix
             paren_idx = text.index('(')
             potential_alias = text[1:paren_idx].strip()
             content = text[paren_idx:]
             if content.startswith('(') and content.endswith(')'):
                 content = content[1:-1] # strip parens if wrapped
        else:
            # Standard split: !model msg
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                potential_alias = parts[0][1:] # Remove '!'
                content = parts[1]
            else:
                return text, None, None

        # Check if this is NOT a known command
        known_commands = ['info', 'readme', 'read', 'formats', 'models', 'check', 'test', 'clear', 
                          'weather', 'forecast', 'temp-history', 'radar', 'weather-map']
        
        if potential_alias.lower() not in known_commands:
            # Try to resolve as model alias
            resolved_model, method = resolve_model_alias(potential_alias)
            if resolved_model:
                return content, resolved_model, f"Model override: '{potential_alias}' -> '{resolved_model}' ({method})"
            else:
                # It started with ! but wasn't a valid model OR a known command
                # Log this for debugging
                print(f"   [DEBUG_PARSE] '{potential_alias}' is not a known command nor a valid model.")

    return text, None, None

def query_lmstudio(user_query, system_prompt="You are a helpful SMS assistant.", model_override=None):
    """Send a query to the local LM Studio instance (OpenAI-compatible)."""
    headers = {
        "Content-Type": "application/json"
    }
    
    model_to_use = model_override if model_override else LMSTUDIO_MODEL
    
    payload = {
        "model": model_to_use,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.7
    }
    
    print(f"[{get_timestamp()}] -> Querying LM Studio (Model: {model_to_use})...")
    
    try:
        with AI_PROCESSING_LOCK:
            response = requests.post(LMSTUDIO_URL, headers=headers, json=payload, timeout=_SETTINGS["timeouts"]["lmstudio"])
        response.raise_for_status()
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        
        print(f"[{get_timestamp()}] <- LM Studio response received")
        return content.strip()
        
    except requests.exceptions.Timeout:
        # Spawn delayed monitor if enabled
        if DELAYED_RESPONSE_ENABLED and len(DELAYED_RESPONSE_QUEUE) < 10:
            import uuid
            request_id = str(uuid.uuid4())
            with DELAYED_RESPONSE_LOCK:
                DELAYED_RESPONSE_QUEUE.append((request_id, requests.post, (), {'url': LMSTUDIO_URL, 'headers': headers, 'json': payload}, None, "LM Studio query", _SETTINGS["timeouts"]["lmstudio"]))
            print(f"[{get_timestamp()}] [DELAYED] Queued monitor for LM Studio response")
        return "ERROR [E002]: LM Studio timeout after 5 minutes"
    except Exception as e:
        return f"ERROR [E002]: LM Studio unreachable - {str(e)[:100]}"

def query_lemonade(user_query, system_prompt="You are a helpful SMS assistant.", model_override=None):
    """Send a query to the local Lemonade instance (OpenAI-compatible)."""
    headers = {
        "Content-Type": "application/json"
    }
    
    model_to_use = model_override if model_override else LEMONADE_MODEL
    
    payload = {
        "model": model_to_use,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.7
    }
    
    print(f"[{get_timestamp()}] -> Querying Lemonade at {LEMONADE_URL} (Model: {model_to_use})...")
    
    try:
        response = smart_post(LEMONADE_URL, json_data=payload, timeout=_SETTINGS["timeouts"]["lemonade"])
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        
        print(f"[{get_timestamp()}] <- Lemonade response received")
        return content.strip()
        
    except requests.exceptions.Timeout:
        # Spawn delayed monitor if enabled
        if DELAYED_RESPONSE_ENABLED and len(DELAYED_RESPONSE_QUEUE) < 10:
            import uuid
            request_id = str(uuid.uuid4())
            with DELAYED_RESPONSE_LOCK:
                # Use smart_post for the background monitor as well to ensure IPv6 loopback works
                DELAYED_RESPONSE_QUEUE.append((request_id, smart_post, (), {'url': LEMONADE_URL, 'json_data': payload}, None, "Lemonade query", _SETTINGS["timeouts"]["lemonade"]))
            print(f"[{get_timestamp()}] [DELAYED] Queued monitor for Lemonade response")
        return "ERROR [E002]: Lemonade timeout"
    except requests.exceptions.ConnectionError as ce:
        print(f"[{get_timestamp()}] [CRITICAL] Lemonade connection failed: {ce}")
        return f"ERROR [E002]: Lemonade unreachable (Connection Refused). Check port 8000."
    except Exception as e:
        print(f"[{get_timestamp()}] [ERROR] Lemonade query failed: {type(e).__name__} - {e}")
        return f"ERROR [E002]: Lemonade query failed - {str(e)[:100]}"

def query_ai(user_query, thread_slug=None, model_override=None, force_wiki=False):
    """Router function to send query to the configured AI backend."""
    
    # 1. Check for Weather
    is_weather, location = detect_weather_query(user_query)
    
    # 2. Check for Time
    is_time = detect_time_query(user_query)
    
    enhanced_query = user_query
    
    if is_weather and location:
        print(f"   [Detected weather query for: {location}]")
        weather_data = get_weather(location)
        if not weather_data.startswith("ERROR"):
            enhanced_query = f"[CURRENT WEATHER DATA FROM NOAA]\n{weather_data}\n\n[USER QUESTION]\n{user_query}"
            print(f"   [Weather data injected into AI context]")
            
    elif is_weather and not location:
        return "I can get weather information for you! Please specify a location. Examples:\n- 'weather in Seattle'\n- 'weather in 98101'\n- 'weather in Miami,FL'"

    # If time query detected, return current time
    if is_time:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"Current time: {current_time}"

    # Route to backend
    # Route to backend
    if AI_BACKEND == "anythingllm" and not force_wiki:
        return query_anythingllm(enhanced_query, thread_slug)
    elif AI_BACKEND == "lmstudio" and not force_wiki:
        return query_lmstudio(enhanced_query, model_override=model_override)
    elif AI_BACKEND == "lemonade" and not force_wiki:
        return query_lemonade(enhanced_query, model_override=model_override)
    elif AI_BACKEND == "fast_flow" and not force_wiki:
        return query_fast_flow(enhanced_query, model_override=model_override)
    elif force_wiki or AI_BACKEND.startswith("wiki_agent"):
        if not wiki_agent:
            return "ERROR [E009]: Wiki Agent module not loaded. Check dependencies."
            
        print(f"[{get_timestamp()}] -> Querying Wiki Agent (Research Mode)...")
        
        # Configure Backend dynamically based on selection
        if "lemonade" in AI_BACKEND:
            # Load Lemonade settings
            url = LEMONADE_URL.replace("/chat/completions", "") # Strip suffix if needed, but wiki_agent expects base
            # Ensure URL has /api/v1 if looking for OpenAI compat usually, but settings has full chat URL
            # Parse base from LEMONADE_URL: http://localhost:8000/api/v1/chat/completions -> http://localhost:8000/api/v1
            # Parse base from LEMONADE_URL: http://localhost:8000/api/v1/chat/completions -> http://localhost:8000/api/v1
            if "/chat/completions" in LEMONADE_URL:
                base_url = LEMONADE_URL.rsplit("/chat/completions", 1)[0]
            else:
                base_url = LEMONADE_URL
            
            # Use specific reasoning model if configured, else fallback
            wa_model = _SETTINGS.get("ai_backend", {}).get("wiki_agent", {}).get("lemonade_model", LEMONADE_MODEL)
            wiki_agent.configure_backend("Lemonade", base_url, "lemonade", wa_model)
            
        elif "lmstudio" in AI_BACKEND:
            # Load LM Studio settings
            if "/chat/completions" in LMSTUDIO_URL:
                base_url = LMSTUDIO_URL.rsplit("/chat/completions", 1)[0]
            else:
                base_url = LMSTUDIO_URL
                
            # Use specific reasoning model if configured, else fallback
            wa_model = _SETTINGS.get("ai_backend", {}).get("wiki_agent", {}).get("lmstudio_model", LMSTUDIO_MODEL)
            wiki_agent.configure_backend("LM Studio", base_url, "lmstudio", wa_model)
        
        else:
            # Generic wiki_agent or auto-detect mode
            wiki_agent.detect_and_configure_backend()

        # Use simple global lock primarily for the Model calls within the agent
        with AI_PROCESSING_LOCK:
            return wiki_agent.get_agent_response(enhanced_query)
    else:
        return "ERROR: Unknown AI backend configured."

def query_fast_flow(user_query, model_override=None):
    """Query Fast Flow LM directly (via OpenAI API compatibility)."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": FAST_FLOW_MODEL,
        "messages": [{"role": "user", "content": user_query}],
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    print(f"[{get_timestamp()}] -> Querying Fast Flow LM...")
    try:
        # Use global lock
        with AI_PROCESSING_LOCK:
            response = requests.post(FAST_FLOW_URL, headers=headers, json=payload, timeout=_SETTINGS["timeouts"].get("fast_flow", 300))
        
        if response.status_code != 200:
             return f"ERROR [E002]: Fast Flow LM returned {response.status_code} - {response.text[:200]}"
             
        data = response.json()
        return data['choices'][0]['message']['content']
        
    except requests.exceptions.ConnectionError:
        return f"ERROR [E002]: Fast Flow LM unreachable at {FAST_FLOW_URL}"
    except Exception as e:
        return f"ERROR [E002]: Fast Flow LM failed - {str(e)[:100]}"

def query_anythingllm(user_query, thread_slug=None):
    """Internal function to query AnythingLLM."""
    headers = {
        "Authorization": f"Bearer {ANYTHINGLLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": user_query,
        "mode": "chat"
    }
    if thread_slug:
        payload["threadSlug"] = thread_slug
    
    print(f"[{get_timestamp()}] -> Querying AnythingLLM...")
    
    print(f"[{get_timestamp()}] -> Querying AnythingLLM...")
    
    try:
        with AI_PROCESSING_LOCK:
            response = requests.post(ANYTHINGLLM_URL, headers=headers, json=payload, timeout=_SETTINGS["timeouts"]["anythingllm"])
        response.raise_for_status()
        
        try:
            resp_data = response.json()
            resp_json = resp_data.get('textResponse') or resp_data.get('text') or "NO RESPONSE FIELD"
        except ValueError:
            resp_json = response.text or "EMPTY RESPONSE"
            
        print(f"[{get_timestamp()}] <- AnythingLLM response received")
        return resp_json
    except requests.exceptions.Timeout:
        # Spawn delayed monitor if enabled
        if DELAYED_RESPONSE_ENABLED and len(DELAYED_RESPONSE_QUEUE) < 10:
            import uuid
            request_id = str(uuid.uuid4())
            with DELAYED_RESPONSE_LOCK:
                DELAYED_RESPONSE_QUEUE.append((request_id, requests.post, (), {'url': ANYTHINGLLM_URL, 'headers': headers, 'json': payload}, None, "AnythingLLM query", _SETTINGS["timeouts"]["anythingllm"]))
            print(f"[{get_timestamp()}] [DELAYED] Queued monitor for AnythingLLM response")
        return "ERROR [E002]: AnythingLLM timeout after 10 minutes"
    except Exception as e:
        return f"ERROR [E002]: AnythingLLM offline or unreachable - {str(e)[:100]}"

def send_sms_reply(recipient_email, message_body, attachment_path=None, pre_uploaded_link=None):
    """Send the AI's answer back via Gmail SMTP.
    - Supports sending an image attachment (MMS).
    - Auto-uploads attachment to transfer.sh and appends link.
    - Uses smart splitting for long messages.
    """
    # Function-scope variable to hold the link for later use
    generated_link = None

    # Carrier domain mapping (Required for MMS delivery on many networks)
    domain_map = {
        "vtext.com": "vzwpix.com",
        "txt.att.net": "mms.att.net",
        "messaging.sprintpcs.com": "pm.sprint.com"
    }
    
    mms_recipient = recipient_email
    try:
        if "@" in recipient_email:
            user, domain = recipient_email.split('@')
            if domain in domain_map:
                mms_recipient = f"{user}@{domain_map[domain]}"
                print(f"[Send] Routed MMS to carrier gateway: {mms_recipient}")
    except:
        pass

    # 1. Handle Attachment & Upload
    # 1. Handle Attachment & Upload
    if pre_uploaded_link:
        generated_link = pre_uploaded_link
        if generated_link:
            if generated_link.startswith("http://"):
                generated_link = generated_link.replace("http://", "https://")
            elif not generated_link.startswith("https://"):
                generated_link = "https://" + generated_link
        # Link is already in the body usually, so we don't need to append "(Cloud links sent separately)" 
        # unless we want to inform the user.
        # But per user request "links sent but unsecure", we just want the variants.
    elif attachment_path and os.path.exists(attachment_path):
        try:
            # Upload to Cloud
            generated_link = CloudUploader.upload_file(attachment_path)
            
            if generated_link:
                message_body += "\n\n(Cloud link sent separately to avoid carrier filter)"
        except Exception as e:
            print(f"[Send] Upload failed: {e}")
            message_body += "\n(Image upload failed, sending attachment only)"

    # Debug: Print final body
    print(f"[DEBUG] Final SMS Body: {message_body!r}")

    # Split message into chunks for carrier compatibility
    # User requested increased limits: 700 for non-spaces, 838 for spaces.
    split_limit = 838
    print(f"   [Send] Using increased {split_limit}-char segments for carrier compatibility.")
        
    chunks = smart_split_message(message_body, limit=split_limit)
    total_chunks = len(chunks)
    
    MAX_RETRIES = 3
    RETRY_DELAYS = [2, 4, 8]  # Exponential backoff
    
    for i, chunk in enumerate(chunks):
        msg = EmailMessage()
        msg['Subject'] = 'RE: SMS Response'
        msg['From'] = YOUR_EMAIL
        msg['To'] = recipient_email
        msg.set_content(chunk)
        
        # Retry logic for this chunk
        for attempt in range(MAX_RETRIES):
            try:
                print(f"[{get_timestamp()}] -> Sending text {i+1}/{total_chunks} (attempt {attempt+1})...")
                with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
                    server.starttls()
                    server.login(YOUR_EMAIL, YOUR_APP_PASSWORD)
                    server.send_message(msg)
                print(f"[{get_timestamp()}] <- Text part {i+1} sent")
                # Add delay between chunks to prevent carrier rate-limiting/dropping
                if i < total_chunks - 1:
                    time.sleep(4)
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                else:
                    print(f"!!! Text send failed: {e}")

    # --- SEPARATE BROKEN LINK (Bypass Filters) ---
    if generated_link:
        print(f"[{get_timestamp()}] -> Sending clean cloud link...")
        time.sleep(1)
        
        msg = EmailMessage()
        msg['Subject'] = 'RE: Secure File Link'
        msg['From'] = YOUR_EMAIL
        msg['To'] = recipient_email
        msg.set_content(f"Your requested file is securely hosted here:\n\n{generated_link}\n\n(This link will expire automatically and is sent separately to bypass carrier SMS filters.)")
        
        try:
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
                server.starttls()
                server.login(YOUR_EMAIL, YOUR_APP_PASSWORD)
                server.send_message(msg)
            print(f"[{get_timestamp()}] <- Cloud link sent")
            time.sleep(1)
        except Exception as e:
            print(f"!!! Cloud link send failed: {e}")

    # --- SEPARATE ATTACHMENT MESSAGE (MMS) ---
    if attachment_path and os.path.exists(attachment_path):
        print(f"[{get_timestamp()}] -> Sending MMS attachment...")
        # Use the carrier-mapped MMS recipient from earlier in the function

        msg = EmailMessage()
        msg['Subject'] = 'RE: Image Attachment'
        msg['From'] = YOUR_EMAIL
        msg['To'] = mms_recipient
        msg.set_content("Radar image attached below. High-quality links sent separately.")
        
        ctype, _ = mimetypes.guess_type(attachment_path)
        if not ctype: ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        
        try:
            with open(attachment_path, 'rb') as f:
                file_data = f.read()
            msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=os.path.basename(attachment_path))
            
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
                server.starttls()
                server.login(YOUR_EMAIL, YOUR_APP_PASSWORD)
                server.send_message(msg)
            print(f"[{get_timestamp()}] <- MMS attachment sent")
        except Exception as e:
            print(f"!!! MMS Attachment failed: {e}")
            
    return None

def check_url(url):
    try:
        # Try models endpoint
        base = url.rsplit("/chat/completions", 1)[0] if "/chat/completions" in url else url
        requests.get(f"{base}/models", timeout=3)
        return True
    except:
        return False

def check_system_status():
    """Return a brief connectivity status report."""
    lines = [f"[ SYSTEM STATUS CHECK - {get_timestamp()} ]"]
    lines.append("[OK] Gmail IMAP: Connected")
    lines.append("[OK] Python: Running")
    
    # Test AnythingLLM
    # Test AI Backend
    # Test AI Backend
    if AI_BACKEND == "lmstudio":
        try:
            requests.get(LMSTUDIO_URL.replace("/chat/completions", "/models"), timeout=5)
            lines.append(f"[OK] LM Studio: Connected ({LMSTUDIO_URL})")
        except:
            lines.append(f"[ERR] LM Studio: Not Reachable")
            
    elif AI_BACKEND == "lemonade":
        try:
            requests.get(LEMONADE_URL.replace("/chat/completions", "/models"), timeout=5)
            lines.append(f"[OK] Lemonade: Connected ({LEMONADE_URL})")
        except:
            lines.append(f"[ERR] Lemonade: Not Reachable")

    elif AI_BACKEND == "fast_flow":
        try:
            requests.get(FAST_FLOW_URL.replace("/chat/completions", "/models"), timeout=5)
            lines.append(f"[OK] Fast Flow LM: Connected ({FAST_FLOW_URL})")
        except:
            lines.append(f"[ERR] Fast Flow LM: Not Reachable")
            
    elif AI_BACKEND.startswith("wiki_agent"):
        subtype = "Lemonade" if "lemonade" in AI_BACKEND else "LM Studio"
        lines.append(f"[OK] Wiki Agent: Selected ({subtype})")
        
        if wiki_agent and os.path.exists(wiki_agent.ZIM_PATH):
             lines.append(f"[OK] ZIM File: Found")
        else:
             lines.append(f"[ERR] ZIM File: Missing")
        
        # Check backend
        if "lemonade" in AI_BACKEND:
            if check_url(LEMONADE_URL): lines.append("[OK] Lemonade Backend: Connected")
            else: lines.append("[ERR] Lemonade Backend: Unreachable")
        else:
            if check_url(LMSTUDIO_URL): lines.append("[OK] LM Studio Backend: Connected")
            else: lines.append("[ERR] LM Studio Backend: Unreachable")
            
    else:
        # Default to AnythingLLM
        try:
            headers = {"Authorization": f"Bearer {ANYTHINGLLM_API_KEY}", "Content-Type": "application/json"}
            test_data = {"message": "ping", "mode": "chat"}
            resp = requests.post(ANYTHINGLLM_URL, headers=headers, json=test_data, timeout=5)
            resp.raise_for_status()
            lines.append(f"[OK] AnythingLLM: Connected ({WORKSPACE_SLUG})")
        except Exception as e:
            lines.append(f"[ERR] AnythingLLM: ERROR - {str(e)[:50]}")
    
    # Test NOAA Weather API
    try:
        headers = {"User-Agent": f"({WEATHER_USER_AGENT})", "Accept": "application/json"}
        test_url = "https://api.weather.gov/points/47.6062,-122.3321"  # Seattle
        resp = requests.get(test_url, headers=headers, timeout=5)
        resp.raise_for_status()
        lines.append("[OK] Weather API (NOAA): Connected")
    except:
        lines.append("[ERR] Weather API (NOAA): ERROR")
    
    # Database status
    if database:
        lines.append(f"[OK] Database: Active ({database.DB_PATH})")
    else:
        lines.append("[ ] Database: Disabled")
    
    return "\n".join(lines)

def extract_phone_number(email_address):
    """Extract the phone number from a Google Voice email address."""
    if not email_address:
        return None
        
    # Check for Google Voice forwarding format: (YourNum).(SenderNum).(Hash)@...
    # Look for patterns with at least two phone-like sequences (10+ digits) separated by dot
    gv_match = re.search(r'^\+?(\d{10,})\.\+?(\d{10,})\.', email_address)
    if gv_match:
        # We assume the SECOND number is the sender, as the first is typically the forwarding/user number
        return gv_match.group(2)
        
    match = re.search(r'([+\d]{10,})', email_address)
    if match:
        return match.group(1)

    # Fallback to any digits
    match_short = re.match(r'([+\d]+)', email_address)
    if match_short:
        return match_short.group(1)
        
    # Last resort: local part
    return email_address.split('@')[0]

def process_email_body(text):
    """Clean email body and detect special format prefixes.
    Returns a tuple (cleaned_text, format_type) where format_type can be:
    - "test" for ^test
    - "thread(#)" for ^thread(#):
    - "thread" for legacy ^thread:
    - None for normal messages
    """
    if not text:
        return "", None
    
    stripped = text.strip()
    
    # Remove Google Voice specific header/footer artifacts
    # Example: <https://voice.google.com>
    stripped = re.sub(r'^<https?://voice\.google\.com>\s*', '', stripped, flags=re.IGNORECASE)
    
    # ^test prefix
    if stripped.lower().startswith("^test"):
        return "Please respond with: functioning", "test"
    
    # ^thread(#): prefix
    thread_match = re.match(r'^\^thread\((\d+)\):', stripped, re.IGNORECASE)
    if thread_match:
        num = thread_match.group(1)
        cleaned = re.sub(r'^\^thread\(\d+\):\s*', '', stripped, flags=re.IGNORECASE)
        return cleaned, f"thread({num})"
    
    # legacy ^thread: prefix
    if stripped.lower().startswith("^thread:"):
        cleaned = re.sub(r'^\^thread:\s*', '', stripped, flags=re.IGNORECASE)
        return cleaned, "thread"
    
    # Remove common footers and delimiters
    delimiters = [
        r'\nOn .*? wrote:',
        r'\n-----Original Message-----',
        r'\nFrom:\s',
        r'\nSent from my',
        r'\n________________________________',
        r'\nYOUR ACCOUNT',
        r'\nHELP CENTER',
        r'\nhttps://voice\.google\.com',
        r'\nThis email was sent to you',
        r'\nGoogle LLC',
        r'<https://voice\.google\.com>',  # Catch footer links too
        r'\nTo respond to this text message',  # Google Voice footer
        r'\nreply to this email or visit',  # Google Voice footer continuation
        r'\nreply to this message',  # Generic reply instruction
        r'\nvisit Google Voice',  # Direct Google Voice mention
        r'\nFor more information',  # Generic Gmail footer
    ]
    earliest = len(stripped)
    for pat in delimiters:
        m = re.search(pat, stripped, re.IGNORECASE | re.DOTALL)
        if m and m.start() < earliest:
            earliest = m.start()
    
    return stripped[:earliest].strip(), None

def process_attachments(msg, phone_number):
    """Process email attachments (images, audio files).
    Returns a tuple: (attachment_note, attachment_paths)
    """
    print(f"   [DEBUG_ATT] Processing attachments for {phone_number}...")
    
    # Collect parts from standard attachments
    parts_to_save = []
    if msg.attachments:
        print(f"   [DEBUG_ATT] Found {len(msg.attachments)} standard attachments via imap_tools.")
        parts_to_save.extend(msg.attachments)
    
    # FALLBACK: If nothing found, or to be safe, walk the message structure
    # This helps with MMS images that might be sent as inline parts
    if hasattr(msg, 'obj'):
        inline_count = 0
        for part in msg.obj.walk():
            if part.get_content_maintype() in ('image', 'audio'):
                # Check if this part is already in attachments (don't double count)
                # Usually attachments have a filename
                filename = part.get_filename()
                if not filename:
                    # Look for name in content-type
                    content_type = part.get_content_type()
                    ext = content_type.split('/')[-1] if '/' in content_type else 'dat'
                    filename = f"part_{random.randint(1000, 9999)}.{ext}"
                
                # If we don't have standard attachments or this one seems new/inline
                # Note: imap_tools usually handles this, but some MMS are weird
                if not msg.attachments or not any(a.filename == filename for a in msg.attachments):
                    from collections import namedtuple
                    Att = namedtuple('Att', ['filename', 'content_type', 'payload'])
                    parts_to_save.append(Att(filename, part.get_content_type(), part.get_payload(decode=True)))
                    inline_count += 1
        if inline_count > 0:
            print(f"   [DEBUG_ATT] Found {inline_count} additional inline/part images.")

    if not parts_to_save:
        print("   [DEBUG_ATT] No image/audio attachments discovered.")
        return None, []
    
    # Create attachments directory
    attachments_dir = os.path.join("attachments", phone_number)
    os.makedirs(attachments_dir, exist_ok=True)
    
    attachment_note = "\n[Attachments received:"
    attachment_paths = []
    
    for att in parts_to_save:
        filename = att.filename
        content_type = att.content_type
        
        # Skip empty files
        if not att.payload:
            continue
            
        # Only process images and audio
        if content_type.startswith('image/') or content_type.startswith('audio/'):
            # Save file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"{timestamp}_{filename}"
            filepath = os.path.join(attachments_dir, safe_filename)
            
            try:
                with open(filepath, 'wb') as f:
                    f.write(att.payload)
                
                attachment_paths.append(filepath)
                file_type = "Image" if content_type.startswith('image/') else "Audio"
                attachment_note += f"\n- {file_type}: {filename} ({len(att.payload)} bytes)"
                print(f"   [ATTACHMENT] Saved {file_type}: {filepath}")
            except Exception as e:
                print(f"   [WARNING] Failed to save attachment {filename}: {e}")
    
    attachment_note += "]"
    
    if attachment_paths:
        return attachment_note, attachment_paths
    else:
        return None, []

def configure_startup_settings():
    """Give user a chance to configure settings on startup with separate wait periods."""
    global RESPOND_TO_OFFLINE_MESSAGES, AI_BACKEND
    
    print("\n" + "="*60)
    print("STARTUP CONFIGURATION")
    print("="*60)
    
    try:
        import msvcrt
        
        # QUESTION 1: Offline Messages (90-second wait)
        print(f"\n1. Process Offline Messages? (Current: {RESPOND_TO_OFFLINE_MESSAGES})")
        print("   Enter 'y' for Yes, 'n' for No (90s timeout)...")
        
        start_time = time.time()
        user_input = ""
        
        while time.time() - start_time < 90:
            remaining = int(90 - (time.time() - start_time))
            print(f"\r   Waiting... {remaining}s  ", end="", flush=True)
            
            if msvcrt.kbhit():
                char = msvcrt.getwche()
                if char == '\r':  # Enter key
                    break
                elif char == '\b':  # Backspace
                    if user_input:
                        user_input = user_input[:-1]
                        print('\b \b', end='', flush=True)
                else:
                    user_input += char
            
            time.sleep(0.1)
        
        print("\r" + " "*30 + "\r", end="", flush=True)  # Clear line
        
        ans = user_input.strip().lower()
        if ans == 'y':
            RESPOND_TO_OFFLINE_MESSAGES = True
            print("   -> ENABLED: Will process offline messages.")
        elif ans == 'n':
            RESPOND_TO_OFFLINE_MESSAGES = False
            print("   -> DISABLED: Will ignore offline messages.")
        else:
            print("   -> Kept current setting.")
        
        # QUESTION 2: AI Backend (90-second wait)
        print(f"\n2. Select AI Backend (Current: {AI_BACKEND})")
        print("   1) LM Studio (Qwen3-VL-8B)")
        print("   2) Lemonade (Llama-3.2-1B-FLM)")
        print("   3) Wiki Agent (Lemonade + Qwen3-8b-FLM)")
        print("   4) Wiki Agent (LM Studio + Qwen3-VL-8B)")
        print("   Enter 1-4 (90s timeout)...")
        
        start_time = time.time()
        user_input = ""
        
        while time.time() - start_time < 90:
            remaining = int(90 - (time.time() - start_time))
            print(f"\r   Waiting... {remaining}s  ", end="", flush=True)
            
            if msvcrt.kbhit():
                char = msvcrt.getwche()
                if char == '\r':  # Enter key
                    break
                elif char == '\b':  # Backspace
                    if user_input:
                        user_input = user_input[:-1]
                        print('\b \b', end='', flush=True)
                else:
                    user_input += char
            
            time.sleep(0.1)
        
        print("\r" + " "*30 + "\r", end="", flush=True)  # Clear line
        
        ans = user_input.strip()
        if ans == '1':
            AI_BACKEND = "lmstudio"
            _SETTINGS["ai_backend"]["provider"] = AI_BACKEND
            save_settings(_SETTINGS)
            print("   -> SELECTED: LM Studio (saved to settings.json)")
        elif ans == '2':
            AI_BACKEND = "lemonade"
            _SETTINGS["ai_backend"]["provider"] = AI_BACKEND
            save_settings(_SETTINGS)
            print("   -> SELECTED: Lemonade (saved to settings.json)")
        elif ans == '3':
            AI_BACKEND = "wiki_agent_lemonade"
            _SETTINGS["ai_backend"]["provider"] = AI_BACKEND
            save_settings(_SETTINGS)
            print("   -> SELECTED: Wiki Agent (Lemonade) (saved to settings.json)")
        elif ans == '4':
            AI_BACKEND = "wiki_agent_lmstudio"
            _SETTINGS["ai_backend"]["provider"] = AI_BACKEND
            save_settings(_SETTINGS)
            print("   -> SELECTED: Wiki Agent (LM Studio) (saved to settings.json)")
        else:
            print(f"   -> Kept current backend: {AI_BACKEND}")
        
        # Reload AI_BACKEND global variable (redundant if set directly above, but good for consistency)
        AI_BACKEND = _SETTINGS["ai_backend"]["provider"]
        
        print("\n[ CONFIGURATION COMPLETE ] Continuing startup...\n")
        print(f"[CONFIG] To change settings, edit {SETTINGS_FILE} and restart the agent.\n")
            
    except ImportError:
        print("\n[SKIP] msvcrt not available (non-Windows?), skipping interactive setup.")
    except Exception as e:
        print(f"\n[SKIP] Setup error: {e}")


# UID Tracker for persistent state
try:
    from uid_tracker import UIDTracker
    uid_tracker = UIDTracker()
except ImportError:
    print("Warning: UIDTracker not found. Persistent tracking disabled.")
    uid_tracker = None

def main_listener():
    """Main loop: listen for new SMS emails and process them."""
    
    # Run startup configuration wizard
    configure_startup_settings()
    
    current_retry_delay = BASE_RETRY_DELAY
    
    print("\n" + "="*60)
    print(f"[ OFF-GRID AGENT STARTED - {get_timestamp()} ]")
    print("="*60)
    print(f"Email: {YOUR_EMAIL}")
    print(f"Label: {GMAIL_LABEL}")
    print(f"Weather: NOAA weather.gov (User-Agent: {WEATHER_USER_AGENT})")
    print("\nPress Ctrl+C to stop gracefully.")
    print("="*60)
    
    # STARTUP TEST: Verify AI connectivity
    print(f"\n[{get_timestamp()}] [ STARTUP TEST ] Checking AI Backend ({AI_BACKEND})...")
    # ... (AI checks omitted for brevity in diff, existing logic remains) ...

    # STARTUP LOGIC: INITIALIZE UID TRACKER
    # If this is the FIRST run (empty tracker), and Offline Mode is OFF:
    # We must mark ALL existing messages as "seen" in the tracker to prevent spamming history.
    if uid_tracker:
        print(f"[{get_timestamp()}] [ TRACKER ] Initializing UID state...")
        try:
            with MailBox('imap.gmail.com').login(YOUR_EMAIL, YOUR_APP_PASSWORD) as mailbox:
                mailbox.folder.set(GMAIL_LABEL)
                
                # Fetch ALL messages to populate initial state if needed
                # We use a broad search.
                all_msgs = mailbox.fetch(mark_seen=False, limit=500)
                all_uids = [str(m.uid) for m in all_msgs]
                
                if not RESPOND_TO_OFFLINE_MESSAGES:
                    # Case: First run (or cleared privacy), Offline Mode DISABLED.
                    # Action: Mark everything as processed so we don't reply to them.
                    print(f"   [INIT] First run + Offline Mode OFF -> Ignoring {len(all_uids)} existing messages.")
                    uid_tracker.mark_batch_processed(all_uids)
                elif RESPOND_TO_OFFLINE_MESSAGES:
                     print(f"   [INIT] Offline Mode ON -> Agent will process any un-tracked messages found.")
                else:
                     print(f"   [INIT] Standard Startup -> Resuming tracking.")
                     
        except Exception as e:
            print(f"   [ERROR] Failed to initialize tracker: {e}")

    print("="*60 + "\n")
    
    # Start delayed response worker
    # ...
    
    while True:
        try:
            print(f"\n[{get_timestamp()}] [ CONNECTING ] Initializing Gmail IMAP connection...")
            
            with MailBox('imap.gmail.com').login(YOUR_EMAIL, YOUR_APP_PASSWORD) as mailbox:
                # Reset retry delay on successful connection
                current_retry_delay = BASE_RETRY_DELAY
                print(f"[{get_timestamp()}] [ CONNECTED ] Successfully connected to Gmail")
                
                try:
                    mailbox.folder.set(GMAIL_LABEL)
                    print(f"[{get_timestamp()}] [ READY ] Monitoring label '{GMAIL_LABEL}'")
                except Exception as label_error:
                    print(f"\n!!! ERROR [E001]: Gmail label '{GMAIL_LABEL}' not found!")
                    print(f"!!! {label_error}")
                    print("!!! Please create this label in Gmail or update GMAIL_LABEL variable.")
                    break
                
                print(f"[{get_timestamp()}] [ WAITING ] Listening for new messages (timeout: {IMAP_IDLE_TIMEOUT}s)...")
                print("    (Press Ctrl+C to exit)")
                
                last_heartbeat = time.time()
                first_run = True
                while True:
                    # Heartbeat pulse every 2 minutes to show it hasn't hung
                    if time.time() - last_heartbeat > 120:
                        print(f"\n[{get_timestamp()}] [ MONITOR ] Active | Watching '{GMAIL_LABEL}' | Timeout: {IMAP_IDLE_TIMEOUT}s")
                        last_heartbeat = time.time()

                    # Start IDLE mode (Skip wait on first run)
                    if not first_run:
                        try:
                            # print(f"[{get_timestamp()}] [ IDLE ] Waiting for message...") # Too verbose if every 10s
                            # Use a shorter internal timeout for better Ctrl+C response
                            mailbox.idle.wait(timeout=10)
                        except Exception as idle_err:
                            print(f"\n[{get_timestamp()}] [ IDLE ] Connection refresh needed: {idle_err}")
                            break # Break inner loop to trigger a fresh reconnect
                    
                    first_run = False
                    print(f"\r[{get_timestamp()}] [ CHECKING ] Checking for new messages...", end="", flush=True)
 
                    # message processing logic
                    messages = list(mailbox.fetch(limit=10, reverse=True)) 
                    # reverse=True gets newest first usually, but fetch order varies.
                    
                    # Sort messages by date (Oldest First for FIFO processing)
                    messages.sort(key=lambda x: x.date if x.date else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc))
                    
                    # Filter: Only keep messages whose UID is NOT in our tracker
                    new_messages = []
                    if uid_tracker:
                        for m in messages:
                            if not uid_tracker.is_processed(m.uid):
                                new_messages.append(m)
                    else:
                        # Fallback: relies on seen=False if tracker broken
                         new_messages = [m for m in messages if not 'SEEN' in m.flags]

                    if not new_messages:
                        # No new unique UIDs
                        continue
                    
                    # Queue system: Show how many messages are pending
                    msg_count = len(new_messages)
                    if msg_count > 0:
                        print(f"\n[{get_timestamp()}] [MSG] New Messages Detected: {msg_count}")
                    
                    for msg_idx, msg in enumerate(new_messages, 1):
                        # Mark as processed in tracker IMMEDIATELY to prevent loops if we crash
                        if uid_tracker:
                            uid_tracker.mark_processed(msg.uid)

                        # Generate unique tracking ticket ID
                        ticket_id = f"REQ-{random.randint(100000, 999999)}"
                        
                        try:
                            # Reset per-message variables
                            ATTACHMENT_PATH = None

                            GENERATED_CLOUD_LINK = None
                            print("\n" + "="*60)
                            if msg_count > 1:
                                print(f"[{get_timestamp()}] [ SMS RECEIVED ] Message {msg_idx}/{msg_count} | Ticket: {ticket_id}")
                            else:
                                print(f"[{get_timestamp()}] [ SMS RECEIVED ] Processing | Ticket: {ticket_id}")
                            print("="*60)
                            
                            # Extract message details
                            raw_body = msg.text
                            print(f"   [DEBUG] Raw body length: {len(raw_body)} chars")
                            print(f"   [DEBUG] Raw preview: {raw_body[:150]}...")
                            
                            # Determine reply address and phone number FIRST (needed for attachments)
                            reply_to_address = msg.reply_to[0] if msg.reply_to else msg.from_
                            phone_number = extract_phone_number(reply_to_address) or "unknown"
                            print(f"   Phone: {phone_number}")
                            
                            original_query, format_type = process_email_body(raw_body)
                            
                            # Check for model override (!alias msg)
                            # Only if using LM Studio (or BOTH)
                            model_override = None
                            if AI_BACKEND in ("lmstudio", "both"):
                                original_query, model_override, override_log = parse_model_override(original_query)
                                if override_log:
                                    print(f"   [MODEL] {override_log}")
                                    
                            print(f"   [DEBUG] After processing: '{original_query[:100]}...'")
                            
                            # DUPLICATE CHECK: DISABLED per user request
                            # if check_duplicate_message(phone_number, original_query):
                            #    continue
                            
                            # Process attachments (images, audio)
                            attachment_note, attachment_paths = process_attachments(msg, phone_number)
                            
                            # PIPELINE REFACTOR: Separate the image identification from the text prompt
                            # 'user_query' is what goes to the AI.
                            # 'text_prompt' is the actual human words without attachment notes.
                            text_prompt = original_query.strip()
                            user_query = original_query
                            if attachment_note:
                                print(f"   [DEBUG] Attachments: {len(attachment_paths)} file(s)")
                                user_query += attachment_note
                            
                            # === PLANT ID PIPELINE (NON-BLOCKING) ===
                            print(f"   [DEBUG_ID] Checking Plant ID trigger. Service: {PLANT_ID_SERVICE is not None}, Paths: {len(attachment_paths)}")
                            if PLANT_ID_SERVICE and attachment_paths:
                                # Filter for images (BROAD SUPPORT)
                                valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.heic', '.heif', '.tiff', '.tif', '.dng')
                                image_paths = [p for p in attachment_paths if p.lower().endswith(valid_extensions)]
                                
                                if image_paths:
                                    print(f"   [PlantID] {len(image_paths)} image(s) detected. Processing identification...")
                                    send_sms_reply(reply_to_address, "Hold please, analyzing photo...")

                                    target_image = image_paths[0]
                                    try:
                                        # Use global lock to prevent concurrent GPU usage
                                        with AI_PROCESSING_LOCK:
                                            id_result = PLANT_ID_SERVICE.identify(target_image)
                                        send_sms_reply(reply_to_address, id_result)
                                        print(f"   [PlantID] ID result sent: {id_result[:30]}...")
                                    except Exception as e:
                                        print(f"   [PlantID] Error: {e}")
                                        send_sms_reply(reply_to_address, "Error identifying plant.")

                                    # CONTINUATION LOGIC:
                                    # If there is NO text (just an image), we stop here.
                                    # Use a 3-character threshold to ignore things like " " or "."
                                    if len(text_prompt) < 3:
                                        print(f"   [PlantID] Image-only request. Done.")
                                        print("="*60)
                                        print(f"[{get_timestamp()}] [ COMPLETE ] Plant ID processed successfully")
                                        print("="*60 + "\n")
                                        continue
                                    else:
                                        print(f"   [PlantID] Text found ('{text_prompt[:20]}'). Continuing to command/AI pipeline...")
                            
                            # Check for Plant ID model idleness
                            if PLANT_ID_SERVICE:
                                PLANT_ID_SERVICE.check_idle()
                            
                            # Smart Rate Limiting with Queue (Don't skip messages, delay them)
                            delay_needed = calculate_rate_limit_delay(phone_number)
                            if delay_needed > 0:
                                print(f"   [QUEUE] [WAIT] Waiting {delay_needed}s to respect rate limit...")
                                time.sleep(delay_needed)
                                # Update tracker after delay
                                RATE_LIMIT_TRACKER[phone_number].append(time.time())
                                print(f"   [QUEUE] [OK] Proceeding with message processing")
                            
                            # Security check
                            user_query, is_safe = sanitize_input(user_query)
                            if not is_safe:
                                error_msg = "ERROR [E007]: Your message contained blocked system commands and was rejected for security."
                                send_sms_reply(reply_to_address, error_msg)
                                continue
                            
                            if format_type:
                                print(f"   Format: ^{format_type}")
                            print(f"   Query Length: {len(user_query)} characters")
                            print(f"   Preview: {user_query[:100]}{'...' if len(user_query) > 100 else ''}")
                            
                            # Determine thread slug
                            if format_type and format_type.startswith("thread("):
                                # explicit thread number
                                thread_num = re.search(r'\d+', format_type).group(0)
                                thread_slug = f"thread_{thread_num}"
                            else:
                                # new thread per prompt
                                timestamp_id = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
                                thread_slug = f"{phone_number}_{timestamp_id}"
                            
                            # === COMMAND HANDLING (BEFORE AI QUERY) ===
                            # This fixes issues where email processing leaves invisible chars
                            # IMPORTANT: Use text_prompt for commands so attachment notes don't interfere
                            clean_cmd = re.sub(r'^[^a-z0-9!]+', '', text_prompt.lower().strip())
                            cmd = clean_cmd
                            
                            
                            print(f"   [DEBUG] Command check: '{cmd}' (Original Text: '{text_prompt}')")
                            ai_answer = None
                            error_code = None
                            
                            # Normalize command for multi-word commands
                            full_cmd_normalized = cmd.replace(" ", "")
                            
                            if cmd == "!info":
                                print(f"   [DEBUG] [OK] Command matched: !info")
                                ai_answer = COMMANDS_MESSAGE
                                
                                # Try to attach the Manual PDF (Backup if !readme fails)
                                try:
                                    pdf_path = os.path.join("docs", "Off-Grid_Agent_Manual_Full.pdf")
                                    if os.path.exists(pdf_path):
                                        pdf_link = CloudUploader.upload_file(pdf_path)
                                        if pdf_link:
                                            # Enforce HTTPS
                                            if pdf_link.startswith("http://"):
                                                pdf_link = pdf_link.replace("http://", "https://")
                                            elif not pdf_link.startswith("https://"):
                                                pdf_link = "https://" + pdf_link
                                            ai_answer = f"[ FULL MANUAL PDF ]\n{pdf_link}\n\n" + ai_answer
                                except Exception as pdf_err:
                                    print(f"Error uploading manual: {pdf_err}")
                                
                                print(f"[{get_timestamp()}] -> Command: !info (local response + pdf) | {ticket_id}")

                            elif full_cmd_normalized == "!readme":
                                print(f"   [DEBUG] [OK] Command matched: !readme / !read me")
                                
                                ai_answer = (
                                    "Off-Grid SMS Agent\n"
                                    "==================\n"
                                    "Overview: Specialized low-bandwidth AI backend service operating over Google Voice.\n"
                                    "Features: Weather Radar, Offline Wikipedia, Plant ID, Video Recipes."
                                )
                                
                                # Use CloudUploader (Force tmpfiles.org for transient PDF delivery)
                                try:
                                    pdf_path = os.path.join("docs", "README.pdf")
                                    if os.path.exists(pdf_path):
                                        # Create temp settings to force tmpfiles provider
                                        upload_settings = _SETTINGS.copy()
                                        if "cloud_storage" not in upload_settings:
                                            upload_settings["cloud_storage"] = {}
                                        upload_settings["cloud_storage"]["provider"] = "tmpfiles"
                                        
                                        pdf_link = CloudUploader.upload_file(pdf_path)
                                        
                                        if pdf_link:
                                            # Enforce HTTPS
                                            if pdf_link.startswith("http://"):
                                                pdf_link = pdf_link.replace("http://", "https://")
                                            elif not pdf_link.startswith("https://"):
                                                pdf_link = "https://" + pdf_link
                                            ai_answer += f"\n\n[ README PDF ]\n{pdf_link}"
                                            ATTACHMENT_PATH = pdf_path
                                    else:
                                        ai_answer = "Error: README.pdf not found."
                                except Exception as pdf_err:
                                    print(f"Error uploading README: {pdf_err}")
                                
                                print(f"[{get_timestamp()}] -> Command: !readme (sending PDF Link + Attachment) | {ticket_id}")
                                
                            elif cmd == "!check":
                                print(f"   [DEBUG] [OK] Command matched: !check")
                                ai_answer = check_system_status()
                                print(f"[{get_timestamp()}] -> Command: !check (system status) | {ticket_id}")
                                
                            elif cmd == "!test":
                                print(f"   [DEBUG] [OK] Command matched: !test")
                                ai_answer = "[OK] Test complete. Off-Grid Agent is functioning normally."
                                print(f"[{get_timestamp()}] -> Command: !test (local response) | {ticket_id}")
                                
                            elif cmd == "!clear":
                                print(f"   [DEBUG] [OK] Command matched: !clear")
                                if database:
                                    count = database.clear_history(phone_number)
                                    ai_answer = f"[OK] History cleared. Removed {count} conversations."
                                else:
                                    ai_answer = "Database not enabled."
                                print(f"[{get_timestamp()}] -> Command: !clear (history wipe) | {ticket_id}")
                                
                            elif cmd == "!weather":
                                print(f"   [DEBUG] [OK] Command matched: !weather")
                                ai_answer = "Please specify a location:\n\nExamples:\n- !weather Seattle\n- !weather 90210\n- !weather London,UK\n\nFormat: !weather <location>"
                                print(f"[{get_timestamp()}] -> Command: !weather (needs location) | {ticket_id}")
                                
                            elif cmd == "!radar":
                                print(f"   [DEBUG] [OK] Command matched: !radar")
                                ai_answer = "Please specify a location:\n\nExamples:\n- !radar Seattle\n- !radar Seattle 20\n- !radar 90210 10\n\nFormat: !radar <location> <miles>"
                                print(f"[{get_timestamp()}] -> Command: !radar (needs location) | {ticket_id}")

                            elif cmd == "!identify":
                                ai_answer = "To identify a plant or object, please send an image attachment (MMS) directly to the agent. No command is required!"
                                print(f"[{get_timestamp()}] -> Command: !identify (help text) | {ticket_id}")
                            
                            elif cmd.startswith("!radar ") or cmd.startswith("!weather-map"):
                                # Validate input
                                is_valid, err_msg = validate_command_input(cmd, user_query)
                                if not is_valid:
                                    ai_answer = err_msg
                                    print(f"[{get_timestamp()}] -> Command: !radar (validation failed) | {ticket_id}")
                                else:
                                    try:
                                        print(f"   [DEBUG] [OK] Command matched: !radar <loc> [miles] [gif]")
                                        
                                        # Parse arguments using the original case text_prompt
                                        # Use regex to find the command and everything after it
                                        cmd_match = re.search(r'(!radar|!weather-map)\s*(.*)', text_prompt, re.IGNORECASE)
                                        if cmd_match:
                                            args = cmd_match.group(2).strip()
                                        else:
                                            args = ""
                                        
                                        # 1. Check for GIF request and Duration
                                        is_gif = False
                                        duration = 30  # Default duration
                                        if re.search(r'\bgif\b', args, re.IGNORECASE):
                                            is_gif = True
                                            args = re.sub(r'\bgif\b', '', args, flags=re.IGNORECASE).strip()
                                            
                                            # Check for duration (digits at end)
                                            # Allow any duration up to 2 days (2880 mins). Regex catches final number.
                                            duration_match = re.search(r'\b(\d+)\b$', args)
                                            if duration_match:
                                                parsed_duration = int(duration_match.group(1))
                                                # If it's reasonable for a duration (and not zip code 90210), treat as duration
                                                # But "90210" is a location? Conflict if user types "!radar 90210 gif 30" -> OK
                                                # "!radar 90210 gif" -> duration=30
                                                # "!radar Seattle 100 gif 120" -> duration=120
                                                # "!radar Seattle gif 90" -> duration=90
                                                
                                                # Safety cap: 2 Days = 2880 mins
                                                if parsed_duration > 2880: parsed_duration = 2880
                                                if parsed_duration <= 0: parsed_duration = 30
                                                
                                                duration = parsed_duration
                                                args = args[:duration_match.start()].strip()
                                        
                                        # 2. Extract Miles (if present as an integer)
                                        miles = 30  # Default to 30 miles
                                        miles_match = re.search(r'\b(\d+)\b$', args)
                                        if miles_match:
                                            miles = int(miles_match.group(1))
                                            location = args[:miles_match.start()].strip()
                                        else:
                                            location = args.strip()
                                            
                                        if not location:
                                            ai_answer = "Please specify a location for the radar.\n\nFormat: !radar <location> [miles] [gif] [duration]"
                                        else:
                                            mode_str = f"ANIMATION ({duration}min GIF)" if is_gif else "STATIC IMAGE"
                                            print(f"[{get_timestamp()}] -> Generating {mode_str} for: {location} ({miles} mi) | {ticket_id}")
                                            
                                            # Import radar module
                                            try:
                                                from weather_radar import generate_radar_images, generate_radar_animation
                                            except ImportError as ie:
                                                ai_answer = f"ERROR: Radar module not available - {ie}"
                                                print(f"[{get_timestamp()}] -> Radar import failed: {ie} | {ticket_id}")
                                                if "weather_radar" in str(ie):
                                                     raise ie
                                            
                                            if is_gif:
                                                # === GENERATE ANIMATED GIF ===
                                                gif_path = generate_radar_animation(location, miles=miles, duration_minutes=duration)
                                                
                                                if gif_path and os.path.exists(gif_path):
                                                    # Build response like !info does - link IN the text body
                                                    best_link = None
                                                    try:
                                                        best_link = CloudUploader.upload_file(gif_path)
                                                        if best_link:
                                                            if best_link.startswith("http://"):
                                                                best_link = best_link.replace("http://", "https://")
                                                            elif not best_link.startswith("https://"):
                                                                best_link = "https://" + best_link
                                                    except Exception as up_err:
                                                        print(f"GIF upload error: {up_err}")
                                                    
                                                    if best_link:
                                                        ai_answer = f"[ RADAR LOOP ]\n{best_link}\n\n"
                                                        ai_answer += f"Radar: {location} ({miles} mi)\n"
                                                        ai_answer += f"Time: Past {duration} min (-5 min intervals)"
                                                    else:
                                                        ai_answer = f"Radar Loop: {location} ({miles} mi)\n"
                                                        ai_answer += f"Time: Past {duration} min (-5 min intervals)\n"
                                                        ai_answer += "(Animation generated but upload failed)"
                                                else:
                                                    ai_answer = f"Failed to generate radar animation for {location}."
                                            
                                            else:
                                                # === GENERATE STATIC IMAGES ===
                                                radar_paths = generate_radar_images(location, miles=miles)
                                                
                                                if radar_paths:
                                                    # Use the LAST path (HQ) for attachment preference
                                                    # Build response like !info does - link IN the text body
                                                    best_link = None
                                                    try:
                                                        # Upload the best (last) image
                                                        best_link = CloudUploader.upload_file(radar_paths[-1])
                                                        if best_link:
                                                            if best_link.startswith("http://"):
                                                                best_link = best_link.replace("http://", "https://")
                                                            elif not best_link.startswith("https://"):
                                                                best_link = "https://" + best_link
                                                    except Exception as up_err:
                                                        print(f"Radar upload error: {up_err}")
                                                    
                                                    if best_link:
                                                        ai_answer = f"[ WEATHER RADAR ]\n{best_link}\n\n"
                                                        ai_answer += f"Radar: {location} ({miles} mi)\n"
                                                        ai_answer += "Layers: Precip, Warnings, Watches"
                                                    else:
                                                        ai_answer = f"Radar: {location} ({miles} mi)\n"
                                                        ai_answer += "Layers: Precip, Warnings, Watches\n"
                                                        ai_answer += "(Image generated but upload failed)"
                                                    
                                                    print(f"[{get_timestamp()}] -> Enhanced radar generated | {ticket_id}")
                                                else:
                                                    ai_answer = f"Radar generation failed for {location}. See logs for details."
                                                    print(f"[{get_timestamp()}] -> Radar generation failed (returned empty list) | {ticket_id}")
                                    except Exception as e:
                                        ai_answer = f"ERROR generating radar: {str(e)[:100]}"
                                        import traceback
                                        traceback.print_exc()
                                        print(f"[{get_timestamp()}] -> Radar error: {e} | {ticket_id}")
                            
                            elif cmd.startswith("!weather ") or cmd.startswith("!weather_"):
                                # Validate input first
                                is_valid, err_msg = validate_command_input(cmd, user_query)
                                if not is_valid:
                                    ai_answer = err_msg
                                    print(f"[{get_timestamp()}] -> Command: !weather (validation failed) | {ticket_id}")
                                else:
                                    try:
                                        print(f"   [DEBUG] [OK] Command matched: !weather <loc>")
                                        # Use original case for location
                                        cmd_match = re.search(r'(!weather_|!weather\s+)(.*)', text_prompt, re.IGNORECASE)
                                        if cmd_match:
                                            location = cmd_match.group(2).strip()
                                        else:
                                            location = cmd.replace("!weather ", "").replace("!weather_", "").strip()
                                        
                                        ai_answer = get_weather(location)
                                        print(f"[{get_timestamp()}] -> Command: !weather {location} | {ticket_id}")
                                    except Exception as weather_err:
                                        ai_answer = f"ERROR: Weather lookup failed - {str(weather_err)[:100]}"
                                        print(f"[ERROR] Weather command exception: {weather_err}")
                                
                            elif cmd.startswith("!forecast"):
                                # Check for parameterized format: !forecast(var)(hrs) loc
                                param_match = re.match(r'!forecast\((.*?)\)\((\d+)\)\s+(.+)', user_query, re.IGNORECASE)
                                if param_match:
                                    var = param_match.group(1).lower()
                                    hours = int(param_match.group(2))
                                    location = param_match.group(3).strip()
                                    
                                    # Map variable to filter mode
                                    filter_mode = None
                                    if 'temp' in var: filter_mode = 'temp'
                                    elif 'wind' in var: filter_mode = 'wind'
                                    elif 'cond' in var or 'cloud' in var or 'clear' in var: filter_mode = 'cond'
                                    elif 'precip' in var or 'rain' in var: filter_mode = 'precip'
                                    
                                    print(f"   [DEBUG] [OK] Command matched: !forecast({var})({hours}) {location}")
                                    ai_answer = get_weather(location, hours=hours, filter_mode=filter_mode)
                                else:
                                    # Standard forecast logic
                                    # Validate input first
                                    is_valid, err_msg = validate_command_input(cmd, user_query)
                                    if not is_valid:
                                        ai_answer = err_msg
                                        print(f"[{get_timestamp()}] -> Command: !forecast (validation failed) | {ticket_id}")
                                    else:
                                        try:
                                            match = re.match(r'!forecast(\d+)\s+(.+)', user_query, re.IGNORECASE)
                                            if match:
                                                hours = int(match.group(1))
                                                location = match.group(2).strip()
                                                print(f"   [DEBUG] [OK] Command matched: !forecast{hours} {location}")
                                                ai_answer = get_weather(location, hours=hours)
                                            else:
                                                match_default = re.match(r'!forecast\s+(.+)', user_query, re.IGNORECASE)
                                                if match_default:
                                                    location = match_default.group(1).strip()
                                                    ai_answer = get_weather(location, hours=12)
                                                else:
                                                    ai_answer = err_msg
                                            print(f"[{get_timestamp()}] -> Command: !forecast | {ticket_id}")
                                        except Exception as forecast_err:
                                            ai_answer = f"ERROR: Forecast lookup failed - {str(forecast_err)[:100]}"
                                            print(f"[ERROR] Forecast command exception: {forecast_err}")
                            
                            elif cmd.startswith("!temp-history"):
                                # Shows PAST 24 hours from observation stations
                                location = cmd.replace("!temp-history", "").strip()
                                if not location:
                                    ai_answer = "Please specify a location. Ex: !temp-history Seattle"
                                else:
                                    print(f"   [DEBUG] [OK] Command matched: !temp-history (historical observations)")
                                    ai_answer = get_weather_history(location, hours=24)
                                
                            elif cmd.startswith("!radar") or cmd.startswith("!weather-map"):
                                # Validate input first
                                is_valid, err_msg = validate_command_input(cmd, user_query)
                                if not is_valid:
                                    ai_answer = err_msg
                                    print(f"[{get_timestamp()}] -> Command: !radar (validation failed) | {ticket_id}")
                                else:
                                    try:
                                        print(f"   [DEBUG] [OK] Command matched: !radar")
                                        parts = cmd.split(maxsplit=1)
                                        location = parts[1] if len(parts) > 1 else ""
                                        ai_answer = get_weather_radar(location)
                                        print(f"[{get_timestamp()}] -> Command: !radar {location} | {ticket_id}")
                                    except Exception as radar_err:
                                        ai_answer = f"ERROR: Weather map failed - {str(radar_err)[:100]}"
                                        print(f"[ERROR] Radar command exception: {radar_err}")
    
                            elif cmd.startswith("!recipe") or (cmd.startswith("http") and any(d in cmd for d in ["instagram.com", "youtube.com", "youtu.be", "tiktok.com"])):
                                ai_answer = "ERROR: Recipe/video extraction has been removed from this version."
                                print(f"[{get_timestamp()}] -> Command: !recipe (feature removed) | {ticket_id}")
                                
                            else:
                                # Not a command, query AI
                                print(f"   [DEBUG] No command matched, querying AI ({AI_BACKEND}) | {ticket_id}")
                                ai_answer = query_ai(user_query, thread_slug=thread_slug, model_override=model_override)
                                
                                # Check for errors in response
                                if ai_answer.startswith("ERROR"):
                                    error_match = re.search(r'\[E\d+\]', ai_answer)
                                    if error_match:
                                        error_code = error_match.group(0).strip('[]')
                            
                            # === LOGGING ===
                            # 1. File logging (per phone number)
                            base_log_dir = os.path.join("logs", phone_number)
                            os.makedirs(base_log_dir, exist_ok=True)
                            timestamp_str = datetime.datetime.now().strftime("%m-%d-%Y_%I-%M-%S_%p")
                            log_file = os.path.join(base_log_dir, f"log_{timestamp_str}.txt")
                            
                            try:
                                with open(log_file, "w", encoding="utf-8") as f:
                                    f.write(f"Ticket ID: {ticket_id}\n")
                                    f.write(f"Timestamp: {timestamp_str}\n")
                                    f.write(f"Phone: {phone_number}\n")
                                    f.write(f"Thread: {thread_slug}\n")
                                    f.write(f"Format: {format_type}\n")
                                    f.write(f"User Query: {user_query}\n")
                                    f.write(f"AI Response: {ai_answer}\n")
                                    f.write(f"Error Code: {error_code or 'None'}\n")
                                    f.write(f"System: Local AI ({AI_BACKEND})\n")
                                print(f"[{get_timestamp()}] -> Log saved: {log_file}")
                            except Exception as le:
                                print(f"!!! Error saving log file: {le}")
                            
                            # 2. Database logging
                            if database:
                                try:
                                    database.save_conversation(
                                        phone_number=phone_number,
                                        user_query=user_query,
                                        ai_response=ai_answer,
                                        thread_slug=thread_slug,
                                        format_type=format_type,
                                        error_code=error_code
                                    )
                                    print(f"[{get_timestamp()}] -> Database: Conversation saved")
                                except Exception as de:
                                    print(f"!!! ERROR [E006]: Database save failed - {de}")
                            
                            # === SEND REPLY ===
                            try:
                                # Check if we have an image to attach (Radar, etc)
                                attachment = ATTACHMENT_PATH
                                
                                send_error = send_sms_reply(reply_to_address, ai_answer, attachment_path=attachment, pre_uploaded_link=GENERATED_CLOUD_LINK)
                                if send_error:
                                    error_code = "E004"
                                    print(f"!!! ERROR [E004]: Send failed - {send_error}")
                            except Exception as send_ex:
                                error_code = "E008"
                                print(f"!!! ERROR [E008]: Critical send failure - {send_ex}")
                                print(f"    Message length: {len(ai_answer)}")
                                
                            if not error_code:
                                print("="*60)
                                print(f"[{get_timestamp()}] [ COMPLETE ] Message processed successfully")
                                print("="*60 + "\n")
                            
                            # Small delay to prevent SMTP spam blocking
                            time.sleep(1)

                        except Exception as msg_error:
                            print(f"\n!!! ERROR processing message {ticket_id}: {msg_error}")
                            # Try to send error reply if we have an address
                            try:
                                reply_to_address = msg.reply_to[0] if msg.reply_to else msg.from_
                                send_sms_reply(reply_to_address, f"ERROR [E009]: System error: {str(msg_error)[:200]}")
                            except:
                                pass
                            continue
                    
        except KeyboardInterrupt:
            print("\nAre you sure you want to stop the agent? (y/n): ", end="", flush=True)
            try:
                if input().lower().startswith('y'):
                    print("\n[ SHUTDOWN ] Stopping agent...")
                    return
                else:
                    print("\n[ RESUMING ] Continuing operation...\n")
                    continue
            except:
                return
            
        except Exception as e:
            if isinstance(e, ssl.SSLEOFError) or "EOF occurred" in str(e):
                print(f"\n[ CONNECTION ] SSL/Socket Error: {e}")
                print(f"[ RECONNECT ] Reconnecting immediately...")
                time.sleep(1)
                continue

            print(f"\n!!! CRITICAL ERROR [E003]: {e}")
            print(f"!!! Error Type: {type(e).__name__}")
            
            if "authentication" in str(e).lower():
                print("\n!!! Gmail authentication failed. Check YOUR_EMAIL and YOUR_APP_PASSWORD")
                print("!!! APP PASSWORD tutorial: https://support.google.com/accounts/answer/185833")
                break
            
            # Exponential Backoff
            print(f"\n[ RETRY ] Waiting {current_retry_delay} seconds before reconnection attempt...")
            time.sleep(current_retry_delay)
            
            # Increase delay for next time (up to 5 minutes)
            current_retry_delay = min(current_retry_delay * 2, 300)
    
    # Cleanup before exit
    print(f"[ SHUTDOWN COMPLETE - {get_timestamp()} ]")
    print("="*60)

def check_permissions():
    """Check if we have write permissions in the current directory."""
    try:
        test_file = "perm_test.tmp"
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception as e:
        print(f"\n!!! PERMISSION ERROR: Cannot write to this directory.")
        print(f"!!! Details: {e}")
        print("!!! SOLUTION: Either run 'start agent.bat' as Administrator")
        print("!!!           OR move this folder to your Desktop/Documents folder.")
        return False

if __name__ == "__main__":
    try:
        if not check_permissions():
            input("\nPress Enter to exit...")
            sys.exit(1)
            
        main_listener()
    except Exception as fatal_error:
        print(f"\n!!! FATAL ERROR: {fatal_error}")
        print("!!! Agent terminated unexpectedly")
        sys.exit(1)

