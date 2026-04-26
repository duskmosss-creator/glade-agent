import re
import json
import time
import logging
from datetime import datetime

# Tools
import web_search, map_search
import wiki_agent # Import existing wiki agent for its tools
from research_pdf_generator import generate_research_report
# query_ai is in main.py, we use internal _query_backend


logger = logging.getLogger(__name__)

class ResearchAgent:
    def __init__(self, mode="FAST", max_steps=10):
        """
        :param mode: "FAST" (Chat) or "DEEP" (Report/Research)
        :param max_steps: Limit on research iterations.
        """
        self.mode = mode
        self.max_steps = max_steps
        self.context = []
        self.findings = [] # Structured findings for report
        self.sources = [] # Tracked sources for report
        
    def get_agent_response(self, user_query, max_steps=None):
        """
        Main entry point.
        """
        if max_steps:
            self.max_steps = max_steps
            
        logger.info(f"Research Agent started. Mode: {self.mode}, Steps: {self.max_steps}")
        
        # 1. Initialize Context
        self.context = [{"role": "user", "content": user_query}]
        
        # 2. ReAct Loop
        step = 0
        final_answer = None
        
        # Ensure Wiki Agent is configured (it uses globals, so calling this ensures paths are set)
        if not wiki_agent._ZIM_ARCHIVE:
             # Lazy loading handles this internally now
             pass

        while step < self.max_steps:
            logger.info(f"--- Step {step+1}/{self.max_steps} ---")
            
            # Construct System Prompt
            system_prompt = self._construct_system_prompt()
            
            # Query AI
            messages = [{"role": "system", "content": system_prompt}] + self.context
            
            try:
                # We use query_ai from connection_utils which handles fallback/retries
                # But query_ai returns string. We need to parse it.
                # Note: query_ai signature might need checking. 
                # Assuming query_ai(prompt, ...) -> str
                # We'll use a direct call helper to keep context history if query_ai doesn't support list.
                # Actually query_ai in main.py supports list? No, it takes `user_query` string.
                # We need a method to send messages list.
                # Let's import `smart_post` from connection_utils directly or define a helper here.
                # For V2, let's assume we can use the backend URL from settings.
                
                # Using wiki_agent's config for consistency for now
                response_text = self._query_backend(messages)
                
            except Exception as e:
                logger.error(f"AI Query failed: {e}")
                return f"Error: AI connection failed - {e}"

            # Parse Response
            # Look for: ACTION: TOOL_NAME [PARAM]
            # or FINAL ANSWER: ...
            
            action_match = re.search(r"ACTION:\s*(\w+)\s*(?:\[(.*?)\])?", response_text, re.IGNORECASE)
            final_match = re.search(r"FINAL ANSWER:\s*(.*)", response_text, re.IGNORECASE | re.DOTALL)
            
            self.context.append({"role": "assistant", "content": response_text})
            
            if final_match:
                final_answer = final_match.group(1).strip()
                logger.info("Final Answer received.")
                break
            
            if action_match:
                tool = action_match.group(1).upper()
                param = action_match.group(2).strip() if action_match.group(2) else ""
                
                logger.info(f"Tool Call: {tool} [{param}]")
                observation = self._execute_tool(tool, param)
                
                # Add observation to context
                self.context.append({"role": "user", "content": f"OBSERVATION: {observation}"})
                
                # Extract structured finding if useful
                if len(observation) > 50 and "Error" not in observation:
                    self.findings.append({"step": step, "tool": tool, "content": observation[:500] + "..."})

            else:
                # AI didn't follow format or just chattered.
                # If content is substantial, treat as answer?
                # Or prompt it to format.
                if step == self.max_steps - 1:
                     final_answer = response_text
                else:
                     self.context.append({"role": "system", "content": "Please format your response as ACTION: TOOL [PARAM] or FINAL ANSWER: [TEXT]."})
            
            step += 1
            
        if not final_answer:
            final_answer = "I reached my search limit before finding a complete answer. Here is what I found:\n" + \
                           "\n".join([f"- {f['content'][:100]}" for f in self.findings])

        # 3. Post-Processing
        if self.mode == "DEEP":
            return self._generate_deep_deliverable(user_query, final_answer)
        else:
            return final_answer

    def _construct_system_prompt(self):
        base = (
            "You are an advanced Offline/Online Research Agent. Your goal is to answer the user's question thoroughly.\n"
            "You have access to the following TOOLS:\n"
            "1. WEB_SEARCH [query]: Search real-time internet (DuckDuckGo).\n"
            "2. URL_READ [url]: Read content of a specific webpage.\n"
            "3. MAP_LOCATE [place]: Get coordinates for a place.\n"
            "4. MAP_POI [category] (lat,lon): Find specific POIs (hot_spring, swimming_hole, campsite) near coords.\n"
            "5. MAP_TRAILS (lat,lon): Find hiking trails near coords.\n"
            "6. WIKI_SEARCH [term]: Search offline Wikipedia.\n"
            "7. WIKI_CONTINUE: Read next part of wiki article.\n"
            "\n"
            "PROTOCOL:\n"
            "- Thought: Analyze what you know and what you need.\n"
            "- Action: Select a tool to get missing info.\n"
            "- Loop: Repeat until satisfied.\n"
            "- Format: Use 'ACTION: TOOL [PARAM]' to use a tool.\n"
            "- Format: Use 'FINAL ANSWER: [TEXT]' when done.\n"
            "- If the user asks for a physical feature (lake, trail), check MAP tools.\n"
            "- If the user asks for news or recent events, check WEB_SEARCH.\n"
            "- If the user asks for historical/general facts, check WIKI_SEARCH.\n"
        )
        return base

    def _execute_tool(self, tool, param):
        try:
            if tool == "WEB_SEARCH":
                results = web_search.search_web(param)
                # Parse results to string
                if not results: return "No results found."
                summary = ""
                for r in results[:3]:
                    summary += f"- {r['title']}: {r['body']} ({r['href']})\n"
                    self.sources.append({'title': r['title'], 'url': r['href']})
                return summary
                
            elif tool == "URL_READ":
                return web_search.get_page_content(param)
                
            elif tool == "MAP_LOCATE":
                loc = map_search.geo_locate(param)
                if loc:
                    return f"Location Found: {loc[2]} at ({loc[0]}, {loc[1]})"
                return "Location not found."
                
            elif tool == "MAP_POI":
                # Expect param like "hot_spring (38.0, -79.0)"
                # Regex parse
                m = re.match(r"(\w+)\s*\(([\d\.-]+),\s*([\d\.-]+)\)", param)
                if m:
                    cat, lat, lon = m.groups()
                    pois = map_search.find_poi(float(lat), float(lon), cat)
                    if not pois: return "No POIs found."
                    return json.dumps(pois[:5], indent=2) 
                return "Invalid params. Use: category (lat, lon)"
                
            elif tool == "MAP_TRAILS":
                m = re.match(r"\(([\d\.-]+),\s*([\d\.-]+)\)", param) # Allow (lat,lon) or just lat,lon
                if not m: m = re.search(r"([\d\.-]+),\s*([\d\.-]+)", param) # Fallback
                
                if m:
                    lat, lon = m.groups()
                    trails = map_search.find_trails(float(lat), float(lon))
                    if not trails: return "No trails found."
                    return json.dumps(trails[:5], indent=2)
                return "Invalid params. Use: (lat, lon)"
                
            elif tool == "WIKI_SEARCH":
                return wiki_agent.search_zim_tool(param)
                
            elif tool == "WIKI_CONTINUE":
                return wiki_agent.continue_reading_tool()
                
            return f"Unknown Tool: {tool}"
        except Exception as e:
            return f"Tool Error: {e}"

    def _query_backend(self, messages):
        # Using wiki_agent's configured backend
        import requests
        url = f"{wiki_agent.API_BASE}/chat/completions"
        payload = {
            "model": wiki_agent.MODEL_NAME,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1024,
            "stop": ["OBSERVATION:", "Observation:"]
        }
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']
        except Exception as e:
            # Fallback to local? Or re-raise
            raise e

    def _generate_deep_deliverable(self, query, final_answer):
        """
        Creates PDF and returns a message with the link.
        """
        filename = f"reports/Research_{int(time.time())}.pdf"
        
        # Format sections
        # We can try to parse the final answer into sections if it's markdown,
        # or just dump it.
        # Ideally we'd use the findings list to build a better report.
        categories = {}
        for f in self.findings:
            t = f['tool']
            if t not in categories: categories[t] = ""
            categories[t] += f['content'] + "\n\n"
            
        sections = []
        sections.append({'title': 'Analysis', 'content': final_answer})
        for t, content in categories.items():
            sections.append({'title': f'exclude_Appendix: {t} Data', 'content': content})
            
        # Summary for PDF
        summary = final_answer[:500] + "..."
        
        # Reports folder in root
        if not os.path.exists("reports"): os.makedirs("reports")
        
        real_path = generate_research_report(
            filename, 
            f"Research: {query[:30]}", 
            summary, 
            sections, 
            self.sources
        )
        
        # Upload using modern CloudUploader
        from connection_utils import CloudUploader
        
        try:
            link = CloudUploader.upload_file(real_path)
            if link:
                return f"RESEARCH COMPLETE.\nSummary: {summary[:100]}...\nFULL REPORT: {link}"
            else:
                return f"RESEARCH COMPLETE.\nSummary: {summary[:100]}...\n(PDF Generation successful but upload failed)"
        except Exception as e:
             return f"RESEARCH COMPLETE.\nSummary: {summary[:100]}...\n(PDF Upload Error: {str(e)[:50]})"

