import logging
import json
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

def search_web(query, max_results=5):
    """
    Performs a DuckDuckGo search and returns a list of results.
    Each result has 'title', 'href', 'body'.
    """
    logger.info(f"Searching web for: {query}")
    try:
        results = []
        with DDGS() as ddgs:
            # text() returns generator
            ddg_results = ddgs.text(query, max_results=max_results)
            for r in ddg_results:
                results.append(r)
        
        return results
    except Exception as e:
        logger.error(f"DuckDuckGo Search failed: {e}")
        return []

def get_page_content(url, max_length=2000):
    """
    Fetches and summarizes the content of a specific URL.
    """
    logger.info(f"Fetching page content: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        text = soup.get_text()
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:max_length]
    except Exception as e:
        logger.error(f"Failed to fetch page content: {e}")
        return f"Error fetching content: {e}"

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    res = search_web("current time in Tokyo")
    print(json.dumps(res, indent=2))
    
    if res:
        content = get_page_content(res[0]['href'])
        print("\nContent Sample:\n", content[:500])
