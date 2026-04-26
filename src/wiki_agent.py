import sys
import re
import os
import time
import libzim.reader
import libzim.search
from bs4 import BeautifulSoup
import threading
import requests
from connection_utils import smart_post, smart_get

# ================= CONFIGURATION =================
# 1. PATH TO YOUR ZIM FILE
# User specified path (All Maxi)
ZIM_PATH = r"C:\wikipedia\zim_files_for_kiwix\wikipedia_en_all_maxi_2025-08.zim"

# Defaults (will be updated by auto-detection)
API_BASE = "http://localhost:8000/api/v1"
API_KEY = "lemonade" 
MODEL_NAME = "Qwen3-8b-FLM"
MAX_SEARCH_STEPS = 50
CHUNK_SIZE = 1000

CURRENT_ARTICLE_CACHE = {}
_ZIM_ARCHIVE = None

def get_zim_archive():
    """Singleton getter for the ZIM archive to prevent repeated I/O."""
    global _ZIM_ARCHIVE
    if _ZIM_ARCHIVE is not None:
        return _ZIM_ARCHIVE
        
    if "REPLACE" in ZIM_PATH:
        print("   [WikiAgent] !!! ERROR: ZIM_PATH not configured !!!")
        return None
        
    if not os.path.exists(ZIM_PATH):
        print(f"   [WikiAgent] !!! ERROR: ZIM file missing at {ZIM_PATH} !!!")
        return None

    try:
        print(f"   [WikiAgent] Opening archive: {os.path.basename(ZIM_PATH)}...")
        _ZIM_ARCHIVE = libzim.reader.Archive(ZIM_PATH)
        return _ZIM_ARCHIVE
    except Exception as e:
        print(f"   [WikiAgent] !!! ERROR opening ZIM: {e} !!!")
        return None

def detect_and_configure_backend():
    """Probe for available AI backends and configure the first one found."""
    global API_BASE, MODEL_NAME
    
    print("\n   [WikiAgent] Probing for available AI backends...")
    
    # List of (Name, URL, Path, DefaultModel)
    backends = [
        ("Lemonade (IPv6)", "http://[::1]:8000", "/api/v1", "Qwen3-8b-FLM"),
        ("Lemonade (IPv4)", "http://127.0.0.1:8000", "/api/v1", "Qwen3-8b-FLM"),
        ("Lemonade (Localhost)", "http://localhost:8000", "/api/v1", "Qwen3-8b-FLM"),
        ("LM Studio", "http://localhost:1234", "/v1", "local-model")
    ]
    
    for name, base_url, path, default_model in backends:
        try:
            # Check models endpoint for availability
            models_url = f"{base_url}{path}/models"
            resp = smart_get(models_url, timeout=2)
            if resp and resp.status_code == 200:
                print(f"   [WikiAgent] [OK] Found {name} at {base_url}{path}")
                API_BASE = f"{base_url}{path}"
                MODEL_NAME = "Qwen3-8b-FLM"
                
                print(f"   [WikiAgent] Connected to {name} (Model: {MODEL_NAME})")
                return True
        except:
            continue
            
    print("   [WikiAgent] [X] No local AI backends found (Lemonade on port 8000)")
    print("   [WikiAgent] Fallback to default configuration.")
    return False

def configure_backend(provider, url, api_key, model):
    """Reconfigure the backend for a specific provider."""
    global API_BASE, API_KEY, MODEL_NAME
    
    print(f"   [WikiAgent] Configuring backend: {provider} ({model}) at {url}")

    API_BASE = url
    API_KEY = api_key
    # Use the model passed from main.py (no auto-detection)
    MODEL_NAME = model

def normalize_path(path):
    return os.path.normpath(path)

def search_zim_tool(query):
    """
    SEARCH TOOL: Locates article in ZIM file (Exact or Fuzzy) and extracts text.
    """
    query = query.strip().strip("'\"")
    print(f"   [TOOL] Searching ZIM for: '{query}'...")
    
    zim = get_zim_archive()
    if not zim:
        return "SYSTEM ERROR: ZIM archive is not available. Check ZIM_PATH configuration."

    try:
        entry = None
        
        # 1. Try Exact Match (Fastest)
        # ZIM articles often start with 'A/' namespace
        potential_keys = [
            query, 
            f"A/{query}", 
            query.replace(" ", "_"), 
            f"A/{query.replace(' ', '_')}"
        ]
        
        for k in potential_keys:
            try:
                if zim.has_entry_by_path(k):
                    entry = zim.get_entry_by_path(k)
                    break
            except:
                continue

        # 2. Index / Fuzzy Search
        if not entry:
            print("   ...No exact match, trying index search...")
            try:
                # Direct instantiation for newer libzim bindings
                searcher = libzim.Searcher(zim)
            except AttributeError:
                # Fallback for older bindings if needed
                searcher = zim.get_searcher()
            q = libzim.search.Query(query)
            search = searcher.search(q)
            
            count = search.getEstimatedMatches()
            if count == 0:
                return "SYSTEM NOTICE: No articles found matching that term. Try a broader search."
            
            # Get top match
            results = list(search.getResults(0, 1))
            entry = zim.get_entry_by_path(results[0])
            print(f"   ...Found: {entry.title}")

        # 3. Read Content
        item = entry.get_item()
        content_bytes = bytes(item.content)
        
        # 4. Clean HTML -> Text
        soup = BeautifulSoup(content_bytes, "html.parser")
        
        # Remove distractions
        for tag in soup(["script", "style", "table", "footer", "nav", "div.references", "span.mw-editsection"]):
            tag.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        
        # --- PAGINATION LOGIC ---
        global CURRENT_ARTICLE_CACHE
        if len(text) > CHUNK_SIZE:
            # Cache the full text
            CURRENT_ARTICLE_CACHE = {
                'full_text': text,
                'current_index': CHUNK_SIZE,
                'title': entry.title
            }
            return (f"ARTICLE TITLE: {entry.title} (Page 1)\n"
                    f"CONTENT:\n{text[:CHUNK_SIZE]}\n"
                    f"\n[SYSTEM NOTICE: Article is long. Output truncated. "
                    f"To read the next section, issue command: CONTINUE]")
        else:
            # Clear cache if new short article found
            CURRENT_ARTICLE_CACHE = {}
            return f"ARTICLE TITLE: {entry.title}\nCONTENT:\n{text}"
        
    except Exception as e:
        return f"SYSTEM ERROR: Exception reading ZIM - {e}"

def continue_reading_tool():
    """Returns the next chunk of the active article."""
    global CURRENT_ARTICLE_CACHE
    if not CURRENT_ARTICLE_CACHE:
        return "SYSTEM NOTICE: No active article to continue. Use SEARCH first."
    
    full_text = CURRENT_ARTICLE_CACHE['full_text']
    idx = CURRENT_ARTICLE_CACHE['current_index']
    
    if idx >= len(full_text):
        return "SYSTEM NOTICE: End of article reached."
    
    # Get next chunk
    next_idx = idx + CHUNK_SIZE
    chunk = full_text[idx:next_idx]
    CURRENT_ARTICLE_CACHE['current_index'] = next_idx
    
    remaining = len(full_text) - next_idx
    footer = ""
    if remaining > 0:
        footer = "\n[SYSTEM NOTICE: Valid info. Still more text remaining. Use CONTINUE for next part.]"
    else:
        footer = "\n[SYSTEM NOTICE: End of article.]"
        
    return (f"ARTICLE: {CURRENT_ARTICLE_CACHE['title']} (Continuation)\n"
            f"CONTENT:\n{chunk}{footer}")



def get_agent_response(user_question, include_thoughts=False):
    """
    Public API for main.py to get a response string from the agent.
    Returns the final answer text.
    Args:
        include_thoughts (bool): If True, returns raw response including <think> tags.
                                 If False (default), strips <think> tags for clean SMS.
    """
    # Create a fresh message history for each query
    # Adjust system prompt based on output mode
    base_prompt = (
        "You are an autonomous Research Agent with access to a massive offline Wikipedia Archive. "
        "Your goal is to answer the user's question accurately using facts from the archive.\n\n"
        "TOOLS AVAILABLE:\n"
        "- SEARCH: [term]\n"
        "- CONTINUE\n"
        "  (Use CONTINUE to read the next part of a long article if truncated.)\n\n"
        "PROTOCOL:\n"
        "0. START by using SEARCH to find a relevant article.\n"
        "1. ANALYZE the user's request.\n"
        "2. SEARCH for relevant topics.\n"
        "3. If an article says [Truncated], and you need more info from it, use CONTINUE.\n"
        "4. NEVER use CONTINUE if you haven't SEARCHed first.\n"
        "5. When you have enough info, synthesize the Final Answer.\n"
        "6. DO NOT hallucinate facts.\n"
    )
    
    if not include_thoughts:
        base_prompt += (
            "\n\nOUTPUT FORMAT RULES (SMS MODE):\n"
            "- CRITICAL: Keep response EXTREMELY CONCISE (under 140 words).\n"
            "- Use plain text only. NO tables, NO markdown formatting.\n"
            "- Summarize key points with dashes (-) only.\n"
            "- Aim for a total length under 800 characters if possible.\n"
            "- Do NOT repeat the search term or article titles in your answer.\n"
            "- Focus only on answering the specific question asked.\n"
        )
    
    messages = [
        {"role": "system", "content": base_prompt},
        {"role": "user", "content": user_question}
    ]

    step = 0
    while step < MAX_SEARCH_STEPS:
        try:
            # 1. Think / Act using requests library (bypasses OpenAI client httpx issue)
            print(f"   ...Thinking (Step {step+1}/{MAX_SEARCH_STEPS})...")
            
            payload = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
                "stop": ["Observation:"]
            }
            
            response = smart_post(
                f"{API_BASE}/chat/completions",
                json_data=payload,
                timeout=300
            )
            
            # Parse response
            data = response.json()
            
            # Robust response parsing
            if not data:
                raise ValueError("API returned empty response")

            # Check for error field in response
            if 'error' in data:
                error_msg = data['error'].get('message', 'Unknown API Error')
                raise IOError(f"AI Backend Error: {error_msg}")

            # Extract response text
            if 'choices' not in data or not data['choices']:
                print(f"[DEBUG] No choices. Full response: {data}")
                raise ValueError("API returned completion with no choices")
                
            response_text = data['choices'][0]['message']['content']
            
            if not response_text:
                response_text = ""
            
            response_text = response_text.strip()
            
            # 2. Check for Tool Use (Look for lines starting with SEARCH: or containing [SEARCH])
            match_search = re.search(r"^\s*SEARCH:\s*\[?([^\]\n]+)\]?", response_text, re.IGNORECASE | re.MULTILINE)
            match_continue = re.search(r"^\s*CONTINUE\s*$", response_text, re.IGNORECASE | re.MULTILINE)
            
            if match_search:
                # -- TOOL: SEARCH --
                search_term = match_search.group(1).strip()
                print(f"   [WikiAgent] ACTION: SEARCH '{search_term}'")
                observation = search_zim_tool(search_term)
                
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": f"Observation:\n{observation}"})
                step += 1
                
            elif match_continue:
                # -- TOOL: CONTINUE --
                print(f"   [WikiAgent] ACTION: CONTINUE READING...")
                observation = continue_reading_tool()
                
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": f"Observation:\n{observation}"})
                step += 1
                
            else:
                # -- FINAL ANSWER --
                # Strip <think> tags for clean output if present AND if we don't want thoughts
                # Strip <think> tags for clean output if present AND if we don't want thoughts
                if not include_thoughts:
                    # 1. Remove think blocks
                    clean_response = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
                    
                    # 2. Remove markdown headers (### Header -> Header)
                    clean_response = re.sub(r'^#+\s*', '', clean_response, flags=re.MULTILINE)
                    
                    # 3. Remove markdown bold/italic markers (* or _)
                    clean_response = re.sub(r'\*\*|__', '', clean_response)
                    
                    # 4. Remove markdown tables (lines starting with |)
                    clean_response = re.sub(r'^\s*\|.*\|.*$', '', clean_response, flags=re.MULTILINE)
                    
                    # 5. Remove any remaining table separators (e.g. ---)
                    clean_response = re.sub(r'^\s*[-:_]{3,}\s*$', '', clean_response, flags=re.MULTILINE)
                    
                    # 6. Collapse multiple newlines/spaces
                    lines = [line.strip() for line in clean_response.split('\n') if line.strip()]
                    clean_response = '\n'.join(lines)
                    
                    return clean_response if clean_response else "No content available."
                else:
                    return response_text

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Wiki Agent Error: {e}"

    return "Error: Wiki Agent reached maximum search steps without a final answer."

def run_agent_loop(user_question):
    """Interactive CLI loop wrapper."""
    print(f"\n[AGENT] Agent received: \"{user_question}\"")
    # For CLI usage, we WANT to see the thoughts
    answer = get_agent_response(user_question, include_thoughts=True)
    print("\n[AGENT] Final Answer:")
    print("=" * 50)
    print(answer)
    print("=" * 50)

if __name__ == "__main__":
    detect_and_configure_backend()
    
    # Check for command line arguments (one-off query mode)
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
        print(f"\n--- WIKI AGENT (ONE-OFF MODE) ---")
        print(f"Backend: {API_BASE} ({MODEL_NAME})")
        print(f"Query: {user_query}")
        run_agent_loop(user_query)
        sys.exit(0)

    # Standard interactive loop
    print(f"\n--- WIKI AGENT ACTIVATED ---")
    print(f"Backend: {API_BASE} ({MODEL_NAME})")
    print(f"ZIM File: {ZIM_PATH}")
    
    print("\nType 'exit' to quit.")
    
    while True:
        try:
            q = input("\nRequest: ")
            if q.lower() in ('exit', 'quit'): break
            if not q.strip(): continue
            
            run_agent_loop(q)
        except KeyboardInterrupt:
            break
