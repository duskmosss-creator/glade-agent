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
DEFAULT_ZIM_PATH = r"C:\path\to\your\wikipedia.zim"

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
    NESTED LOOP ARCHITECTURE:
    1. Qwen: Create initial keywords
    2. OUTER LOOP (Qwen oversight):
        - LLAMA SUB-LOOP: Autonomous research until Llama says "DONE"
        - QWEN REVIEW: Check if sufficient, request more if needed
    3. Qwen: Synthesize final answer
    """
    if check_cancellation: check_cancellation()
    
    ctx = ContextManager(history)
    recent_history_text = ctx.get_recent_history_text()
    
    # ===== PHASE 1: QWEN INITIAL PLANNING =====
    print("   [WikiAgent] PHASE 1: Qwen creates initial keywords...")
    if check_cancellation: check_cancellation()
    
    planner_prompt = (
        "You are a research planner. Given a user question, create a list of Wikipedia article titles to search.\n\n"
        f"User Question: {user_question}\n\n"
        "Instructions:\n"
        "- Output 4-6 specific Wikipedia article titles, ONE per line\n"
        "- Use proper nouns and specific terms (e.g., 'Mothman', not 'cryptids')\n"
        "- Think: What Wikipedia articles would contain this information?\n\n"
        "Example 1:\n"
        "Question: 'What is the Eiffel Tower?'\n"
        "Output:\n"
        "Eiffel Tower\n"
        "Paris\n"
        "Gustave Eiffel\n"
        "Iron architecture\n\n"
        "Example 2:\n"
        "Question: 'List cryptids in Ohio'\n"
        "Output:\n"
        "Mothman\n"
        "Loveland Frog\n"
        "Ohio\n"
        "Cryptid\n"
        "West Virginia\n\n"
        "Now create your search plan (article titles only, one per line):\n"
    )
    
    raw_plan = call_llm([{"role": "user", "content": planner_prompt}], role="fast", max_tokens=300)
    
    # Handle empty response (less likely with Llama, but keep as safety)
    if not raw_plan or len(raw_plan.strip()) == 0:
        print("   [WikiAgent] WARNING: Qwen returned empty! Using keyword extraction...")
        import re
        words = user_question.split()
        raw_plan = "\n".join([w for w in words if len(w) > 3 and w[0].isupper()])
        if not raw_plan:
            stopwords = {'what', 'where', 'when', 'who', 'how', 'list', 'all', 'the', 'and', 'in', 'to', 'around'}
            raw_plan = "\n".join([w for w in words if w.lower() not in stopwords and len(w) > 2])
    
    print(f"   [WikiAgent] Raw plan:\n{raw_plan[:200]}")
    
    # Parse keywords
    stopwords = {'what', 'where', 'when', 'who', 'how', 'list', 'all', 'the', 'and', 'in', 'to', 'around'}
    qwen_keywords = []
    
    # Split by common delimiters and clean
    split_chars = ['\n', ',', ';']
    lines = [raw_plan]
    for char in split_chars:
        new_lines = []
        for l in lines:
            new_lines.extend(l.split(char))
        lines = new_lines

    for line in lines:
        clean = line.strip().strip('"').strip("'").strip('- ').strip('* ').strip(':')
        
        # Remove common prefixes from fallbacks
        prefixes = ["NEED_MORE:", "NEXT_SEARCH:", "SEARCH:", "KEYWORDS:", "SUGGESTION:"]
        for p in prefixes:
            if clean.upper().startswith(p):
                clean = clean[len(p):].strip()

        # Final quality checks
        if clean and len(clean) > 2 and len(clean) < 50 and clean.lower() not in stopwords:
            # Capitalize each word for Wikipedia compatibility
            qwen_keywords.append(clean.title())
    
    if not qwen_keywords:
        qwen_keywords = ["Cryptid", "Ohio", "West Virginia"]  # Emergency fallback
    
    print(f"   [WikiAgent] Initial keywords: {qwen_keywords}\n")
    
    # ===== PHASE 2: NESTED RESEARCH LOOPS =====
    verified_dossier = []
    searched_terms = set()
    qwen_satisfied = False
    qwen_cycle = 0
    MAX_QWEN_CYCLES = 3
    
    while not qwen_satisfied and qwen_cycle < MAX_QWEN_CYCLES:
        if check_cancellation: check_cancellation()
        qwen_cycle += 1
        
        print(f"\n{'='*60}")
        print(f"   QWEN-LLAMA RESEARCH CYCLE #{qwen_cycle}")
        print(f"{'='*60}")
        print(f"   Qwen → Llama: Keywords = {qwen_keywords}")
        
        # ----- LLAMA SUB-LOOP (Self-contained research session) -----
        print(f"\n   [Llama Sub-Loop] Starting autonomous research...")
        
        research_queue = list(qwen_keywords)
        llama_done = False
        llama_iter = 0
        MAX_LLAMA_ITER = 15
        
        while not llama_done and llama_iter < MAX_LLAMA_ITER and research_queue:
            if check_cancellation: check_cancellation()
            llama_iter += 1
            
            term = research_queue.pop(0)
            if term.lower() in searched_terms:
                continue
            searched_terms.add(term.lower())
            
            print(f"   [Llama] [{llama_iter}] Searching: '{term}'")
            obs = search_zim_tool(term)
            print(f"   [Llama] Result: {len(obs)} chars")
            
            is_empty = "No results found" in obs or len(obs.strip()) < 150
            snippet = obs[:1500] if not is_empty else "[NO RESULTS FOUND]"
            
            # Llama assessment - GREEDY LOGIC (No 'DONE' escape hatch inside sub-loop)
            llama_prompt = (
                f"Query: {user_question}\n"
                f"Search: '{term}'\n"
                f"Result: {snippet}\n"
                f"Dossier Size: {len(verified_dossier)} sources\n\n"
                "INSTRUCTIONS:\n"
                "1. If this article is about the LOCATION or TOPIC, DECISION: KEEP.\n"
                "2. Suggest exactly ONE specific Wikipedia article title for NEXT_SEARCH.\n"
                "3. Do NOT say 'DONE' here. Suggest a new lead to explore.\n\n"
                "DECISION: [KEEP/DISCARD]\n"
                "NEXT_SEARCH: [Article Title]"
            )
            
            llama_response = call_llm([{"role": "user", "content": llama_prompt}], role="fast", max_tokens=80)
            
            # Parse decision
            is_keep = "KEEP" in llama_response.upper() and not is_empty
            if is_keep:
                verified_dossier.append(f"=== SOURCE: {term} ===\n{obs}\n")
                print(f"   [Llama] ✓ KEPT")
            else:
                print(f"   [Llama] ✗ Discarded")
            
            # Check next action
            import re
            next_match = re.search(r"NEXT_SEARCH:\s*(.+)", llama_response, re.IGNORECASE)
            if next_match:
                next_term = next_match.group(1).strip().strip('"').strip("'").strip('[]')
                if len(next_term) > 60:
                    next_term = " ".join(next_term.split()[:4])
                
                if next_term and len(next_term) > 2 and '[' not in next_term:
                    if next_term.lower() not in searched_terms:
                        print(f"   [Llama] → Adding: '{next_term}'")
                        research_queue.append(next_term)
        
        print(f"\n   [Llama Sub-Loop] Complete: {llama_iter} searches, {len(verified_dossier)} total sources\n")
        
        # ----- QWEN REVIEW (Check if dossier is sufficient) -----
        print(f"   [Qwen Review] Evaluating dossier...")
        if check_cancellation: check_cancellation()
        
        # Increase preview size for evaluation (10k chars is safer for 16k context window)
        dossier_preview = "\n".join(verified_dossier)[:10000]
        
        qwen_review_prompt = (
            "SYSTEM: You are a Research Quality Reviewer. Output ONLY robotic responses.\n\n"
            f"User Question: {user_question}\n\n"
            f"Research Dossier Preview:\n{dossier_preview}\n\n"
            f"Total Sources Collected: {len(verified_dossier)}\n\n"
            "INSTRUCTIONS:\n"
            "1. Can you answer the user's question COMPLETELY with this information?\n"
            "2. Output SUFFICIENT if yes.\n"
            "3. Output NEED_MORE followed by 2-3 Wikipedia titles if no.\n"
            "4. NO INTRO. NO TABLE. NO COMMENTARY.\n\n"
            "Example 1:\n"
            "Question: 'What is the Eiffel Tower?'\n"
            "Response: SUFFICIENT\n\n"
            "Example 2:\n"
            "Question: 'List cryptids in Ohio'\n"
            "Response: NEED_MORE: Mothman, Loveland Frog\n\n"
            "Final Evaluation:"
        )
        
        qwen_review = call_llm([{"role": "user", "content": qwen_review_prompt}], role="fast", max_tokens=200)
        
        # Fallback if Qwen returns empty
        if len(qwen_review.strip()) == 0:
            print("   [Qwen Review] WARNING: Empty response! Using Llama fallback...")
            fallback = f"Query: '{user_question}'\n\nSuggest 2-3 specific names/topics to search:\n"
            llama_suggestions = call_llm([{"role": "user", "content": fallback}], role="fast", max_tokens=50)
            if llama_suggestions:
                qwen_review = f"NEED_MORE: {llama_suggestions}"
        
        print(f"   [Qwen Review] {qwen_review[:150]}")
        
        # Decision
        if "SUFFICIENT" in qwen_review.upper():
            print("   [Qwen Review] ✓ SUFFICIENT → Proceeding to synthesis\n")
            qwen_satisfied = True
        elif "NEED_MORE" in qwen_review.upper() or len(verified_dossier) == 0:
            import re
            # Clean possible bracketed placeholders Llama might echo
            clean_review = qwen_review.replace("[", "").replace("]", "")
            need_match = re.search(r"NEED_MORE:\s*(.+)", clean_review, re.IGNORECASE)
            if need_match:
                raw_list = []
                # Split by commas, semicolons, or newlines
                raw_content = need_match.group(1)
                for delimiter in [',', ';', '\n']:
                    raw_content = raw_content.replace(delimiter, '|')
                raw_list = [x.strip() for x in raw_content.split('|') if x.strip()]
                
                print(f"   [WikiAgent] → Reviewer requested: {raw_list}")
                
                qwen_keywords = []
                for t in raw_list:
                    clean = t.strip().strip('"').strip("'").strip('- ').strip('* ').strip(':')
                    # Discard if it looks like a sentence (too long), is a prefix, or contains brackets
                    if clean and 2 < len(clean) < 60 and '[' not in clean:
                        # Avoid adding generic phrases Llama might spit out
                        if "list 2-3" not in clean.lower() and "wikipedia" not in clean.lower():
                            qwen_keywords.append(clean.title())
                
                qwen_keywords = qwen_keywords[:3]  # Limit to 3 fresh leads per cycle
                if qwen_keywords:
                    print(f"   [Reviewer] Requested more info on: {qwen_keywords}")
                else:
                    # If parsing failed but NEED_MORE was said, use a broad lead
                    qwen_keywords = [user_question.split()[0].title()]
                print(f"   [Qwen Review] ✗ INSUFFICIENT → Requesting: {qwen_keywords}\n")
                # Outer loop continues with new keywords
            else:
                print("   [Qwen Review] Ambiguous response, assuming sufficient\n")
                qwen_satisfied = True
        else:
            print("   [Qwen Review] Ambiguous response, assuming sufficient\n")
            qwen_satisfied = True
    
    print(f"{'='*60}")
    print(f"   RESEARCH COMPLETE: {len(verified_dossier)} sources after {qwen_cycle} cycle(s)")
    print(f"{'='*60}\n")
    
    # ===== PHASE 3: QWEN SYNTHESIS =====
    if check_cancellation: check_cancellation()
    print("   [WikiAgent] PHASE 3: Qwen synthesizing final answer...")
    
    if not verified_dossier:
        final_context = "No relevant information found in the archive."
        print("   [WikiAgent] WARNING: No verified data.")
    else:
        final_context = "\n".join(verified_dossier)
        print(f"   [WikiAgent] Dossier: {len(final_context)} characters")
    
    synthesizer_prompt = (
        f"User Question: {user_question}\n\n"
        f"===== RESEARCH DOSSIER =====\n{final_context}\n\n"
        "INSTRUCTIONS:\n"
        "1. Answer using ONLY the Research Dossier above.\n"
        "2. Organize clearly and list all relevant items.\n"
        "3. Cite sources (e.g., 'According to the Cryptid article...').\n\n"
        "**DO NOT ASSUME**:\n"
        "- If the dossier lacks specific information, state what's missing.\n"
        "- Do NOT add facts from training data. Only use the dossier.\n"
        "- If incomplete, say so.\n\n"
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
