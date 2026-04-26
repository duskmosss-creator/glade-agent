# Wiki Agent Configuration Summary

## SMS Agent Integration (main.py)

The Wiki Agent is **fully integrated** into the SMS agent. When you select option 5 or 6 during startup:

### Option 5: Wiki Agent + Lemonade
- **Backend**: Lemonade server on `http://localhost:8000/v1`
- **Model**: `qwen3-8b-flm`
- **URL**: `http://localhost:8000/v1/chat/completions`
- **No auto-detection** - model name is passed from settings.json

### Option 6: Wiki Agent + LM Studio
- **Backend**: LM Studio on `http://127.0.0.1:1234/v1`
- **Model**: `qwen/qwen3-8b`
- **URL**: `http://127.0.0.1:1234/v1/chat/completions`
- **No auto-detection** - model name is passed from settings.json

## Standalone Wiki Agent (wiki_agent.py)

Can be run independently via `run_wiki_agent.bat`. It will auto-detect available backends OR you can configure it programmatically before calling `get_agent_response()`.

## Current Configuration

```json
{
  "ai_backend": {
    "provider": "wiki_agent_lemonade",  // Default startup mode
    "lmstudio": {
      "url": "http://127.0.0.1:1234/v1/chat/completions",
      "model": "qwen/qwen3-8b"
    },
    "lemonade": {
      "url": "http://localhost:8000/v1/chat/completions",
      "model": "llama-3.2-1b-flm"  // For non-wiki-agent queries
    },
    "wiki_agent": {
      "lemonade_model": "qwen3-8b-flm",  // For wiki_agent + lemonade
      "lmstudio_model": "qwen/qwen3-8b"   // For wiki_agent + lmstudio
    }
  }
}
```

## How It Works

1. When SMS agent starts, you select backend option 5 or 6
2. `main.py` reads the corresponding model from `settings.json`
3. `main.py` calls `wiki_agent.configure_backend(provider, base_url, api_key, model)`
4. `wiki_agent.py` accepts the model parameter WITHOUT any auto-detection
5. All queries use the specified model

## Testing

- ✅ LM Studio connection verified: `qwen/qwen3-8b` responds on port 1234
- ✅ Lemonade connection verified: responds on port 8000/v1
- ✅ Model names are hardcoded in settings - no auto-detection
