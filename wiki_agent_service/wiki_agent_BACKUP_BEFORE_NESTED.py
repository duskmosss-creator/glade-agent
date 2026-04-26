import sys
import re
import os
import time
import json
import libzim.reader
import libzim.search
from bs4 import BeautifulSoup
import threading
import requests
from connection_utils import smart_post, smart_get

# ================= CONFIGURATION =================
SETTINGS_PATH = "wiki_settings.json"
DEFAULT_ZIM_PATH = r"C:\wikipedia\zim_files_for_kiwix\wikipedia_en_all_maxi_2025-08.zim"

# Runtime Globals
CONFIG = {}
ZIM_ARCHIVE = None
CURRENT_ARTICLE_CACHE = {}

def load_config():
    """Load configuration from wiki_settings.json."""
    global CONFIG
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r') as f:
                CONFIG = json.load(f)
            print(f"   [Config] Loaded {SETTINGS_PATH}")
        except Exception as e:
            print(f"   [Config] Error loading settings: {e}")
            CONFIG = {}
    else:
        print(f"   [Config] No settings file found at {SETTINGS_PATH}. Using defaults.")
        CONFIG = {}

def get_zim_archive():
    """Singleton getter for the ZIM archive to prevent repeated I/O."""
    global ZIM_ARCHIVE
    if ZIM_ARCHIVE is not None:
        return ZIM_ARCHIVE
    
    zim_path = CONFIG.get("zim_path", DEFAULT_ZIM_PATH)
    
    if not os.path.exists(zim_path):
        print(f"   [WikiAgent] !!! ERROR: ZIM file missing at {zim_path} !!!")
        return None

    try:
        print(f"   [WikiAgent] Opening archive: {os.path.basename(zim_path)}...")
        ZIM_ARCHIVE = libzim.reader.Archive(zim_path)
        return ZIM_ARCHIVE
    except Exception as e:
        print(f"   [WikiAgent] !!! ERROR opening ZIM: {e} !!!")
        return None

def detect_and_configure_backend():
    """Load settings and report status. Actual logic now handled in query loop."""
    load_config()
    mode = CONFIG.get("mode", "simple")
    print(f"   [WikiAgent] Mode: {mode.upper()}")
    
    if mode == "hybrid":
        fast = CONFIG.get("hybrid", {}).get("fast_model", {})
        smart = CONFIG.get("hybrid", {}).get("smart_model", {})
        print(f"   [WikiAgent] Fast Model: {fast.get('model')} at {fast.get('api_base')}")
        print(f"   [WikiAgent] Smart Model: {smart.get('model')} at {smart.get('api_base')}")
    else:
        simple = CONFIG.get("simple", {})
        print(f"   [WikiAgent] Simple Model: {simple.get('model')} at {simple.get('api_base')}")

def call_llm(messages, role="smart", max_tokens=2048):
    """Generic LLM caller that switches based on role (fast/smart)."""
    mode = CONFIG.get("mode", "simple")
    
    print(f"   [DEBUG] call_llm invoked with role='{role}', mode='{mode}'")
    
    if mode == "hybrid":
        config_key = f"{role}_model"
        settings = CONFIG.get("hybrid", {}).get(config_key)
        print(f"   [DEBUG] Looking for hybrid.{config_key}: {settings}")
        # Fallback to smart if fast not found
        if not settings: 
            print(f"   [DEBUG] WARNING: {config_key} not found, falling back to smart_model")
            settings = CONFIG.get("hybrid", {}).get("smart_model")
    else:
        settings = CONFIG.get("simple")
    
    if not settings:
        return "ERROR: Missing Model Configuration"

    api_base = settings.get("api_base", "http://localhost:8000/api/v1")
    model_name = settings.get("model", "Qwen3-8b-FLM")
    timeout = settings.get("timeout", 60)
    
    # EXPLICIT MODEL LOGGING
    print(f"   [DEBUG] ========================================")
    print(f"   [DEBUG] ROLE: {role}")
    print(f"   [DEBUG] API: {api_base}")
    print(f"   [DEBUG] MODEL: {model_name}")
    print(f"   [DEBUG] ========================================")
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.7 if role == "smart" else 0.1,
        "max_tokens": max_tokens
    }
    
    try:
        if role == "fast":
            print(f"   ...Thinking (LLAMA)...")
        else:
            print(f"   ...Reading/Synthesizing (QWEN)...")
            
        url = f"{api_base}/chat/completions"
        print(f"   [DEBUG] POST {url}")
        print(f"   [DEBUG] Payload model field: {payload['model']}")
        
        response = requests.post(url, json=payload, timeout=timeout)
        # print(f"   [DEBUG] Raw response: {response.text}") # Temporarily disabled for speed, but will check status
        response.raise_for_status()
        
        data = response.json()
        if 'choices' not in data or not data['choices']:
            print(f"   [DEBUG] ERROR: No choices in response! Data: {data}")
            return "Error: No response from model."
            
        result = data['choices'][0]['message'].get('content', '').strip()
        print(f"   [DEBUG] Response length: {len(result)} chars. Content snippet: {result[:50]}...")
        return result
        
    except Exception as e:
        print(f"   [LLM Error] {role} model failed: {e}")
        return f"System Error: {role} backend unavailable."

def search_zim_tool(query):
    """Tool to search ZIM archive and return top results."""
    term = query.strip()
    
    # Common typo corrections
    typo_map = {
        'cincinati': 'Cincinnati',
        'cinncinati': 'Cincinnati',
        'cincinatti': 'Cincinnati',
    }
    
    # Check for typos
    term_lower = term.lower()
    if term_lower in typo_map:
        corrected = typo_map[term_lower]
        print(f"   [WikiAgent] Typo detected: '{term}' → '{corrected}'")
        term = corrected
    
    archive = get_zim_archive()
    if not archive: return "Error: ZIM archive not loaded."
    
    # 1. Try EXACT Title Match First (Most reliable)
    found_entries = []
    
    # Try different casings for exact title
    variants = [term, term.title(), term.capitalize()]
    for v in variants:
        try:
            entry = archive.get_entry_by_title(v)
            if entry:
                found_entries.append(entry)
                print(f"   [WikiAgent] Found exact title match: {v}")
                break
        except: continue

    # 2. If no exact match, use index search
    if not found_entries:
        print(f"   [WikiAgent] Searching index for '{(term)}'...")
        searcher = libzim.search.Searcher(archive)
        query_obj = libzim.search.Query(term)
        search = searcher.search(query_obj)
        try:
            num_results = search.getEstimatedMatches()
        except AttributeError:
            num_results = 20
        
        if num_results > 0:
            count = min(num_results, 3)
            try:
                results = list(search.getResults(0, count))
                for res in results:
                    entry = archive.get_entry_by_path(res.path)
                    found_entries.append(entry)
            except Exception as e:
                print(f"   [WikiAgent] Error fetching results: {e}")
        else:
            # AUTO-BROADENING FALLBACK
            print(f"   [WikiAgent] No results for '{term}'. Trying Auto-Broadening...")
            stopwords = {'in', 'the', 'of', 'and', 'a', 'to', 'for', 'is', 'on', 'at', 'by', 'an', 
                         'all', 'list', 'around', 'near', 'about', 'or'}
            keywords = [w for w in term.replace(',', '').split() if w.lower() not in stopwords and len(w) > 2]
            
            print(f"   [WikiAgent] Keywords extracted: {keywords}")
            
            for kw in keywords:
                try:
                    # Try title match for keywords too
                    k_entry = archive.get_entry_by_title(kw.title())
                    if k_entry:
                        found_entries.append(k_entry)
                        print(f"   [WikiAgent] Found keyword title match: {kw}")
                        continue
                    
                    # Try search for keywords
                    kq = libzim.search.Query(kw)
                    ks = searcher.search(kq)
                    if ks.getEstimatedMatches() > 0:
                        res = list(ks.getResults(0, 1))[0]
                        found_entries.append(archive.get_entry_by_path(res.path))
                        print(f"   [WikiAgent] Found keyword search match: {kw}")
                except: pass

    if not found_entries:
        return f"No results found for '{term}'."

    # 3. Read Content (Follow redirects)
    results_text = []
    for idx, entry in enumerate(found_entries[:3]):
        try:
            # Handle Redirects
            if entry.is_redirect:
                target = entry.get_redirect_entry()
                print(f"   [WikiAgent] Redirecting: {entry.title} → {target.title}")
                entry = target

            item = entry.get_item()
            content_bytes = bytes(item.content)
            soup = BeautifulSoup(content_bytes, "html.parser")
            
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
                
            text = soup.get_text(separator=' ', strip=True)
            snippet = text[:2000] 
            
            results_text.append(f"--- SOURCE: {entry.title} ---\n{snippet}\n")
            
            if idx == 0:
                global CURRENT_ARTICLE_CACHE
                CURRENT_ARTICLE_CACHE = {"title": entry.title, "full_text": text, "position": 0}
        except Exception as e:
            print(f"   [WikiAgent] Error reading {entry.title}: {e}")

    combined_obs = "\n".join(results_text)
    if not combined_obs:
        return f"No readable content found for '{term}'."
        
    if len(combined_obs) > 10000:
        combined_obs = combined_obs[:10000] + "\n...(Total output truncated)..."
        
    return combined_obs

def continue_reading_tool():
    """Tool to read next chunk of current article."""
    global CURRENT_ARTICLE_CACHE
    if not CURRENT_ARTICLE_CACHE or "full_text" not in CURRENT_ARTICLE_CACHE:
        return "SYSTEM NOTICE: No active article to continue. Use SEARCH first."
        
    text = CURRENT_ARTICLE_CACHE["full_text"]
    pos = CURRENT_ARTICLE_CACHE["position"] + 2000
    
    if pos >= len(text):
        return "SYSTEM NOTICE: End of article reached."
        
    CURRENT_ARTICLE_CACHE["position"] = pos
    chunk = text[pos:pos+2000]
    
    if pos + 2000 < len(text):
        chunk += "\n...(Output truncated. Use 'CONTINUE' to read more)..."
        
    return chunk

class ContextManager:
    """Transient context helper for the current request."""
    def __init__(self, history):
        self.history = history or []

    def get_recent_history_text(self):
        """Format the last few turns for the LLM."""
        if not self.history:
            return ""
            
        recent = self.history[-3:]
        
        text = ""
        for msg in recent:
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            if role == 'SYSTEM': continue
            text += f"{role}: {content}\n"
        return text

class RequestCancelledError(Exception):
    """Raised when the client request is cancelled."""
    pass

def get_agent_response(user_question, history=None, include_thoughts=False, check_cancellation=None):
    """
    3-PHASE ARCHITECTURE:
    1. PLANNER (Smart/Qwen): Analyzes request, outputs tailored search plan.
    2. RESEARCHER (Fast/Llama): Loops through plan, searches, verifies relevance, pivots if needed.
    3. SYNTHESIZER (Smart/Qwen): Takes verified verified dossier and writes final answer.
    """
    if check_cancellation: check_cancellation()
    
    ctx = ContextManager(history)
    recent_history_text = ctx.get_recent_history_text()
    
    # --- PHASE 1: RESEARCH PLANNER (Smart Model) ---
    print("   [WikiAgent] PHASE 1: Planning (Smart Model)...")
    if check_cancellation: check_cancellation()
    
    planner_prompt = f"Question: {user_question}\n\nList 4-6 specific Wikipedia article titles to search (one per line):\n"
    
    raw_plan = call_llm([{"role": "user", "content": planner_prompt}], role="smart", max_tokens=200)
    
    # CRITICAL: Handle empty responses from Qwen
    if not raw_plan or len(raw_plan.strip()) == 0:
        print("   [WikiAgent] WARNING: Qwen returned empty response! Using fallback extraction...")
        # Emergency fallback: extract proper nouns and keywords
        import re
        words = user_question.split()
        raw_plan = "\n".join([w for w in words if len(w) > 3 and w[0].isupper()])
        if not raw_plan:
            # Last resort: use question keywords
            stopwords = {'what', 'where', 'when', 'who', 'how', 'list', 'all', 'the', 'and', 'in', 'to', 'around'}
            raw_plan = "\n".join([w for w in words if w.lower() not in stopwords and len(w) > 2])
    
    print(f"   [WikiAgent] Raw plan from Qwen:\n{raw_plan[:200]}")
    
    # Parse Plan - Filter out common words
    stopwords = {'list', 'all', 'the', 'and', 'or', 'in', 'to', 'of', 'a', 'an', 'for', 'around', 'near', 'about'}
    search_queue = []
    for line in raw_plan.split('\n'):
        clean = line.strip().strip('"').strip("'").strip('- ').strip('* ').strip(':')
        # Filter out stopwords and very short terms
        if clean and len(clean) > 2 and clean.lower() not in stopwords:
            search_queue.append(clean)
            
    if not search_queue:
        # Emergency fallback: extract proper nouns from question
        import re
        words = user_question.split()
        for word in words:
            if word[0].isupper() and len(word) > 2:
                search_queue.append(word)
        if not search_queue:
            # Absolute last resort
            search_queue = ["Cryptid", "Cincinnati", "West Virginia"]
    
    # CRITICAL: Capitalize all search terms (Wikipedia uses Title Case)
    search_queue = [term.title() if not term[0].isupper() else term for term in search_queue]
    
    print(f"   [WikiAgent] Plan: {search_queue}")

    # --- PHASE 2: ACTIVE RESEARCH LOOP (Fast Model / Llama) ---
    print("   [WikiAgent] PHASE 2: Researching (Fast Model Loop)...")
    verified_dossier = []
    searched_terms = set()  # Track what we've searched
    
    # Start with Qwen's initial plan
    research_queue = list(search_queue)
    max_iterations = 15  # Safety limit - let Llama decide when to stop
    iteration = 0
    
    while research_queue and iteration < max_iterations:
        if check_cancellation: check_cancellation()
        iteration += 1
        
        # Get next search term
        term = research_queue.pop(0)
        
        # Skip if already searched
        if term.lower() in searched_terms:
            continue
        searched_terms.add(term.lower())
        
        print(f"   [WikiAgent] [{iteration}] Searching: '{term}'")
        obs = search_zim_tool(term)
        
        print(f"   [WikiAgent] Search returned: {len(obs)} characters")
        
        # Determine if we have actual content or a 'not found' message
        # Wikipedia stubs can be short, but empty/error messages are usually specific strings
        is_empty = "No results found" in obs or len(obs.strip()) < 150
        
        #  LLAMA DECIDES: Keep? Need more? What to search next?
        if check_cancellation: check_cancellation()
        
        snippet = obs[:1500] if not is_empty else "[SYSTEM: NO RESULTS FOUND FOR THIS TERM. THE SEARCH FAILED.]"
        
        assessment_prompt = (
            "You are a Research Assistant. Your goal is to find all information about the User Query.\n\n"
            f"User Query: {user_question}\n"
            f"Current Search Term: '{term}'\n"
            f"Search Result (Snippet): {snippet}\n\n"
            f"Items In Dossier: {len(verified_dossier)}\n"
            f"History (Already Searched): {list(searched_terms)[-5:]}\n\n"
            "INSTRUCTIONS:\n"
            "1. If Snippet is useful, output DECISION: KEEP.\n"
            "2. If Snippet is 'NO RESULTS FOUND', you MUST output DECISION: DISCARD and suggest a NEW search term.\n"
            "3. NEXT_SEARCH MUST be a short (1-3 words) Wikipedia article title. Do NOT output sentences.\n"
            "4. If you have enough info, output NEXT_SEARCH: DONE.\n\n"
            "FORMAT:\n"
            "DECISION: [KEEP or DISCARD]\n"
            "NEXT_SEARCH: [Short Article Title or DONE]\n"
        )
        
        assessment = call_llm([{"role": "user", "content": assessment_prompt}], role="fast", max_tokens=100)
        
        print(f"   [WikiAgent] Llama assessment:\n{assessment[:200]}...")
        
        # Parse decision - be strict
        first_line = assessment.split('\n')[0].upper()
        decision_keep = "KEEP" in first_line and "DISCARD" not in first_line and not is_empty
        
        if decision_keep:
            print(f"   [WikiAgent] > ✓ KEPT '{term}'")
            verified_dossier.append(f"=== SOURCE: {term} ===\n{obs}\n")
        else:
            reason = "Empty search result" if is_empty else "Irrelevant"
            print(f"   [WikiAgent] > ✗ Discarded '{term}' ({reason})")
        
        # Check if Llama wants to search more
        import re
        next_match = re.search(r"NEXT_SEARCH:\s*(.+)", assessment, re.IGNORECASE)
        if next_match:
            next_term = next_match.group(1).strip().strip('"').strip("'").strip('[]')
            # Extra safety: if Llama suggests a whole paragraph, take only the first few words
            if len(next_term) > 60:
                next_term = " ".join(next_term.split()[:4])
                
            if next_term.upper() == "DONE":
                print(f"   [WikiAgent] > Llama says DONE (satisfied with {len(verified_dossier)} sources)")
                break
            elif next_term and len(next_term) > 2:
                if next_term.lower() not in searched_terms:
                    print(f"   [WikiAgent] > Llama suggests: '{next_term}'")
                    research_queue.append(next_term)
    
    print(f"   [WikiAgent] Llama research complete: {iteration} searches, {len(verified_dossier)} sources kept")
    
    # --- PHASE 2.5: QWEN VERIFICATION (Trigger even if dossier is empty to pivot) ---
    max_qwen_requests = 2  
    qwen_iteration = 0
    
    while qwen_iteration < max_qwen_requests:
            if check_cancellation: check_cancellation()
            qwen_iteration += 1
            
            print(f"   [WikiAgent] PHASE 2.5: Qwen reviewing dossier (attempt {qwen_iteration})...")
            
            dossier_preview = "\n".join(verified_dossier)[:3000]  # First 3k chars
            
            qwen_review_prompt = (
                "You are the Research Lead. Review the research dossier collected so far.\n\n"
                f"Original Query: {user_question}\n\n"
                f"Research Dossier Preview:\n{dossier_preview}\n\n"
                f"Sources Count: {len(verified_dossier)}\n\n"
                "TASK: Can you answer the user's query COMPLETELY with this information?\n"
                "- If YES: Output 'SUFFICIENT'\n"
                "- If NO: Output 'NEED_MORE: [specific topic to search for]'\n\n"
                "RESPOND:"
            )
            
            qwen_review = call_llm([{"role": "user", "content": qwen_review_prompt}], role="smart", max_tokens=200)
            
            print(f"   [WikiAgent] Qwen review: {qwen_review[:150]}")
            
            # FALLBACK: If Qwen returns empty, use Llama to suggest specific entity names
            if len(qwen_review.strip()) == 0:
                print("   [WikiAgent] WARNING: Qwen empty review! Using Llama to suggest specifics...")
                llama_fallback_prompt = (
                    f"Query: '{user_question}'\n\n"
                    "Research found general info but not specific regional entities for this area.\n"
                    "List 3 SPECIFIC cryptid/creature NAMES that might exist in Ohio/West Virginia region.\n"
                    "Format: Name1, Name2, Name3"
                )
                llama_suggestions = call_llm([{"role": "user", "content": llama_fallback_prompt}], role="fast", max_tokens=50)
                if llama_suggestions:
                    qwen_review = f"NEED_MORE: {llama_suggestions.strip()}"
                    print(f"   [WikiAgent] Llama suggested: {llama_suggestions[:100]}")
            
            # Check if Qwen needs more research
            if "SUFFICIENT" in qwen_review.upper():
                print("   [WikiAgent] > Qwen: Dossier is sufficient")
                break
            elif "NEED_MORE" in qwen_review.upper():
                # Extract what Qwen wants
                import re
                need_match = re.search(r"NEED_MORE:\s*(.+)", qwen_review, re.IGNORECASE)
                if need_match:
                    requested_topic = need_match.group(1).strip().strip('"').strip("'")
                    print(f"   [WikiAgent] > Qwen requests: '{requested_topic}'")
                    
                    # Send Llama back to research
                    if requested_topic.lower() not in searched_terms:
                        print("   [WikiAgent] >> Sending Llama back to research...")
                        research_queue = [requested_topic]
                        
                        # Mini Llama loop for this specific request
                        mini_iterations = 3
                        for mini_iter in range(mini_iterations):
                            if not research_queue:
                                break
                            if check_cancellation: check_cancellation()
                            
                            term = research_queue.pop(0)
                            if term.lower() in searched_terms:
                                continue
                            searched_terms.add(term.lower())
                            
                            print(f"   [WikiAgent] >> Additional search: '{term}'")
                            obs = search_zim_tool(term)
                            
                            if "No results found" not in obs:
                                # Quick Llama assessment
                                quick_assess = call_llm([{
                                    "role": "user",
                                    "content": f"Is this useful for '{user_question}'?\n{obs[:800]}\nKEEP or DISCARD?"
                                }], role="fast", max_tokens=10)
                                
                                if "KEEP" in quick_assess.upper():
                                    verified_dossier.append(f"=== SOURCE: {term} ===\n{obs}\n")
                                    print(f"   [WikiAgent] >> ✓ Added '{term}'")
                    else:
                        print("   [WikiAgent] > Already searched that topic")
                        break
            else:
                # Qwen's response unclear, assume sufficient
                break
    
    # --- PHASE 3: SYNTHESIS (Smart Model) ---
    if check_cancellation: check_cancellation()
    print("   [WikiAgent] PHASE 3: Synthesizing (Smart Model)...")
    
    if not verified_dossier:
        final_context = "No relevant information found in the archive."
        print("   [WikiAgent] WARNING: No verified data found. Synthesis will be based on 'missing info' message.")
    else:
        final_context = "\n".join(verified_dossier)
        print(f"   [WikiAgent] Final Dossier Length: {len(final_context)} characters")
        
    synthesizer_prompt = (
        f"User Question: {user_question}\n\n"
        f"===== RESEARCH DOSSIER =====\n{final_context}\n\n"
        "INSTRUCTIONS:\n"
        "1. Answer the user's question using ONLY the information from the Research Dossier above.\n"
        "2. Organize the information clearly and list all relevant items found.\n"
        "3. Cite sources from the dossier (e.g., 'According to the Cryptid article...').\n\n"
        "**DO NOT ASSUME**:\n"
        "- If the dossier lacks specific information, explicitly state what's missing.\n"
        "- Do NOT add facts from your training data. Only use the dossier.\n"
        "- If you cannot answer completely, say so.\n\n"
        "Your Answer:"
    )
    
    final_answer = call_llm([{"role": "user", "content": synthesizer_prompt}], role="smart", max_tokens=1500)
    
    return final_answer

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
        print(f"Query: {user_query}")
        run_agent_loop(user_query)
        sys.exit(0)

    # Standard interactive loop
    print(f"\n--- WIKI AGENT ACTIVATED ---")
    print(f"ZIM File: {CONFIG.get('zim_path', DEFAULT_ZIM_PATH)}")
    
    print("\nType 'exit' to quit.")
    
    while True:
        try:
            q = input("\nRequest: ")
            if q.lower() in ('exit', 'quit'): break
            if not q.strip(): continue
            
            run_agent_loop(q)
        except KeyboardInterrupt:
            break
