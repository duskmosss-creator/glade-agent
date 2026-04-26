import time
import os
import json
import statistics
import sys
import argparse
import re
import requests
from datetime import datetime

# Inject parent directory for wiki_agent import (ONLY for ZIM tools)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import wiki_agent

SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'wiki_settings.json'))
TEST_QUERY = "List cryptids in and around Cincinnati to West Virginia"
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"

def direct_llm_call(model_name, messages, max_tokens=200):
    """Bypass wiki_agent completely and hit the API directly."""
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "stream": False
    }
    
    print(f"   [API] POST to {LM_STUDIO_URL} (Model: {model_name})...")
    try:
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"   [API ERROR] Status: {response.status_code}, Response: {response.text}")
            return ""
    except Exception as e:
        print(f"   [CONNECTION ERROR] Is LM Studio running? {e}")
        return ""

def update_wiki_settings(model_name):
    """Still update settings file for record keeping, but we don't rely on it for the call."""
    if not os.path.exists(SETTINGS_PATH): return False
    with open(SETTINGS_PATH, 'r') as f:
        data = json.load(f)
    
    data["mode"] = "hybrid"
    if "hybrid" not in data: data["hybrid"] = {}
    data["hybrid"]["fast_model"] = {
        "api_base": "http://127.0.0.1:1234/v1",
        "model": model_name,
        "timeout": 60
    }
    with open(SETTINGS_PATH, 'w') as f:
        json.dump(data, f, indent=4)
    return True

def run_research_only_loop(question, model_name, max_searches=25, forced_cycles=3):
    print("   [Bench] PHASE 1: Initial Planning...")
    
    planner_prompt = (
        "You are a research planner. Given a user question, create a list of Wikipedia article titles to search.\n\n"
        f"User Question: {question}\n\n"
        "Instructions:\n"
        "- Output 4-6 specific Wikipedia article titles, ONE per line\n"
        "- Use proper nouns and specific terms (e.g., 'Mothman', not 'cryptids')\n\n"
        "Output:"
    )
    
    # DIRECT CALL
    raw_plan = direct_llm_call(model_name, [{"role": "user", "content": planner_prompt}], max_tokens=300)
    
    keywords = []
    for line in raw_plan.replace(',', '\n').split('\n'):
        clean = line.strip().strip('"').strip("'").strip('- ').strip('* ').strip(':')
        if clean and len(clean) > 2 and len(clean) < 50:
             keywords.append(clean.title())
    
    if not keywords: 
        print("   [Bench] WARNING: No keywords generated. Using fallback.")
        keywords = ["Cryptids", "Ohio"]
        
    print(f"   [Bench] Plan: {keywords}")

    # ===== PHASE 2: FORCED DEPTH LOOPS =====
    verified_dossier = []
    searched_terms = set()
    research_queue = list(keywords)
    
    total_searches = 0
    MAX_SEARCHES = max_searches
    FORCED_CYCLES = forced_cycles
    current_cycle = 0
    
    while current_cycle < FORCED_CYCLES and total_searches < MAX_SEARCHES:
        current_cycle += 1
        print(f"\n   [Bench] --- CYCLE {current_cycle} (Queue: {len(research_queue)}) ---")
        
        cycle_searches = 0
        while research_queue and cycle_searches < 10:
            term = research_queue.pop(0)
            if term.lower() in searched_terms: continue
            searched_terms.add(term.lower())
            
            total_searches += 1
            cycle_searches += 1
            
            # ZIM Search (Using existing tool)
            # We assume wiki_agent module handles ZIM correctly as that is local file IO, not LLM
            try:
                if wiki_agent.ZIM_ARCHIVE is None: wiki_agent.get_zim_archive()
                obs = wiki_agent.search_zim_tool(term)
            except Exception as e:
                print(f"   [ZIM ERROR] {e}")
                obs = ""
                
            snippet = obs[:2000] if len(obs) > 150 else "[NO RESULTS]"
            
            eval_prompt = (
                f"Query: {question}\n"
                f"Search: '{term}'\n"
                f"Result: {snippet}\n"
                f"Dossier Size: {len(verified_dossier)} sources\n\n"
                "INSTRUCTIONS:\n"
                "1. DECISION: Is this relevant? [KEEP/DISCARD]\n"
                "2. NEXT_SEARCH: Suggest ONE new related article title.\n"
                "3. Do NOT say 'DONE'.\n\n"
                "DECISION: [KEEP/DISCARD]\n"
                "NEXT_SEARCH: [Article Title]"
            )
            
            # DIRECT CALL
            response = direct_llm_call(model_name, [{"role": "user", "content": eval_prompt}], max_tokens=80)
            
            if "KEEP" in response.upper():
                verified_dossier.append(term)
                print(f"   [Bench] [{total_searches}] {term}: KEPT")
            else:
                print(f"   [Bench] [{total_searches}] {term}: Discarded")
                
            next_match = re.search(r"NEXT_SEARCH:\s*(.+)", response, re.IGNORECASE)
            if next_match:
                new_t = next_match.group(1).strip().strip('"').strip("'").strip('[]')
                if len(new_t) > 2 and '[' not in new_t and new_t.lower() not in searched_terms:
                    research_queue.append(new_t)
                    print(f"   [Bench]    -> Immediate Lead: {new_t}")

        if current_cycle < FORCED_CYCLES:
            print(f"   [Bench] End of Cycle {current_cycle}. Forcing expansion...")
            expand_prompt = (
                f"We are researching: {question}\n"
                f"We have found: {verified_dossier}\n"
                f"We have searched: {list(searched_terms)}\n\n"
                "Generate 3 NEW, SPECIFIC Wikipedia article titles to dig deeper. Focus on obscure or related topics missed so far.\n"
                "Output ONLY the 3 titles, one per line."
            )
            # DIRECT CALL
            expansion = direct_llm_call(model_name, [{"role": "user", "content": expand_prompt}], max_tokens=150)
            
            new_leads = []
            for line in expansion.replace(',', '\n').split('\n'):
                clean = line.strip().strip('"').strip("'").strip('- ').strip('* ').strip(':')
                if clean and len(clean) > 2 and clean.lower() not in searched_terms:
                    new_leads.append(clean.title())
            
            print(f"   [Bench] Expansion Leads: {new_leads}")
            research_queue.extend(new_leads)

    return {
        "sources": len(verified_dossier), 
        "searches": total_searches,
        "cycles": current_cycle,
        "dossier_titles": verified_dossier
    }

def run_single_model_test(model_name, iterations=5, max_searches=25, forced_cycles=3, query=None):
    if query is None: query = TEST_QUERY
    
    print(f"\n=== BENCHMARK: FAST MODEL ONLY (DEEP MODE) ===\n")
    print(f"Model: {model_name}")
    print(f"Target API: {LM_STUDIO_URL}")
    print(f"Config: {iterations} Iterations | {max_searches} Max Searches | {forced_cycles} Forced Cycles")
    print(f"Query: {query[:50]}...")
    update_wiki_settings(model_name) # Just for file sync

    # Ensure Archive is Open
    wiki_agent.get_zim_archive()
    
    safe_name = model_name.replace("/", "_").replace(".", "_")
    log_name = f"bench_fast_deep_{safe_name}.log"
    json_name = f"bench_fast_deep_{safe_name}.json"
    results = []

    with open(log_name, "w", encoding="utf-8") as f:
        f.write(f"Deep Benchmark: {model_name}\n")
        f.write(f"Config: {iterations} Iterations | {max_searches} Max Searches | {forced_cycles} Forced Cycles\n\n")

    for i in range(iterations):
        print(f"  [Run {i+1}/{iterations}] ...", end="", flush=True)
        start = time.time()
        
        # Capture stdout for log
        import io
        from contextlib import redirect_stdout
        capture = io.StringIO()
        
        try:
            with redirect_stdout(capture):
                # Pass model name and query explicitly
                data = run_research_only_loop(query, model_name, max_searches, forced_cycles)
            
            elapsed = time.time() - start
            data["time"] = elapsed
            results.append(data)
            
            with open(log_name, "a", encoding="utf-8") as f:
                f.write(f"--- ITERATION {i+1} ---\n")
                f.write(capture.getvalue())
                f.write(f"\nRESULT: {data['sources']} sources in {elapsed:.1f}s ({data['cycles']} cycles)\n\n")
            
            print(f" Done ({data['sources']} sources, {elapsed:.1f}s)")
            
        except Exception as e:
            print(f" Error: {e}")
        
        if i < iterations - 1:
            time.sleep(10)

    avg_src = statistics.mean([r['sources'] for r in results]) if results else 0
    avg_time = statistics.mean([r['time'] for r in results]) if results else 0
    print(f"\n   [Result] Avg Sources: {avg_src:.1f} | Avg Time: {avg_time:.1f}s")
    
    graph_data = {
        "model": model_name,
        "mode": "deep_fast_only",
        "context_window": 55555,
        "config": {
            "max_searches": max_searches,
            "forced_cycles": forced_cycles
        },
        "timestamp": datetime.now().isoformat(),
        "iterations": results,
        "summary": {
            "avg_sources": avg_src,
            "avg_time": avg_time,
            "total_iterations": iterations
        }
    }
    with open(json_name, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=4)
    print(f"   [Data] Saved graph data to {json_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--searches", type=int, default=25)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--query", type=str, default=TEST_QUERY)
    args = parser.parse_args()
    
    run_single_model_test(args.model, args.count, args.searches, args.cycles, args.query)
