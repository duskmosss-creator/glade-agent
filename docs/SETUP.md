# AnythingLLM Setup Guide for SMS Agent

## Overview
This guide will help you configure AnythingLLM to work optimally with your SMS agent, including internet search capabilities, proper prompting, and workspace configuration.

## Prerequisites
- AnythingLLM installed and running on http://localhost:3001
- Workspace created (default: "glade_automation")
- API key generated

## Step 1: Create/Configure Workspace

### 1.1 Access AnythingLLM
1. Open browser to `http://localhost:3001`
2. Navigate to **Workspaces** in the sidebar
3. Create new workspace or select existing "glade_automation"

### 1.2 Get API Key
1. Click your profile icon (top right)
2. Go to **API Keys**
3. Click **Generate New API Key**
4. Copy the key and update `settings.json`:
   ```json
   "anythingllm": {
     "api_key": "YOUR-API-KEY-HERE",
     "workspace_slug": "glade_automation"
   }
   ```

## Step 2: Configure System Prompt

### 2.1 Navigate to Workspace Settings
1. Select your workspace
2. Click **Settings** (gear icon)
3. Scroll to **System Prompt**

### 2.2 Recommended System Prompt
```
You are a helpful SMS assistant that provides concise, accurate information.

IMPORTANT INSTRUCTIONS:
- Keep responses SHORT (under 300 words) - SMS format
- Be direct and to the point
- Use web search when you need current information
- For weather queries, the user's system provides real-time data
- Format responses clearly with bullet points when helpful
- If you don't know something, say so and offer to search

RESPONSE FORMAT:
- Start with a direct answer
- Provide 2-3 key points maximum
- Avoid lengthy explanations unless asked
- Use plain text (no markdown formatting)

CAPABILITIES:
- You can search the internet for current information
- You can answer questions about any topic
- You receive weather data from NOAA when relevant
- You maintain conversation context across messages
```

## Step 3: Enable Internet Search (CRITICAL)

### 3.1 Configure Web Scraping Agent
1. In workspace settings, scroll to **Agent Configuration**
2. Enable **Web Scraping** agent
3. This allows AnythingLLM to search the web for answers

### 3.2 Configure Search Provider (Optional)
1. Go to **Settings** > **Tools & Agents**
2. Select search provider (Google, DuckDuckGo, etc.)
3. Add API keys if required

## Step 4: Configure Agent Flows (IMPORTANT - Missing Step!)

### 4.1 What Are Agent Flows?
Agent Flows are visual workflows in AnythingLLM that let you:
- Chain multiple API calls together
- Add conditional logic
- Transform data between steps
- Create complex automation workflows

**For your SMS agent**, Agent Flows can enhance responses by calling external APIs.

### 4.2 Create an Agent Flow

1. **Navigate to Agent Flows**
   - In AnythingLLM, click **Agent Flows** in the sidebar
   - Click **Create New Flow**
   - Name it: "SMS Agent Flow"

2. **Add Start Block**
   - Every flow starts with a **Start** block
   - This receives the user's message
   - Variables available: `${message}`, `${user}`, `${workspace}`

3. **Add API Call Block** (Example: Weather Enhancement)
   ```
   Block Type: API Call
   Name: "Fetch Weather Details"
   Method: GET
   URL: https://api.weather.gov/points/${latitude},${longitude}
   Headers:
     User-Agent: your-agent-name
   ```

4. **Configure POST Body Usage**
   For POST requests, use `${variableName}` syntax:
   ```json
   {
     "query": "${message}",
     "context": "${conversationHistory}",
     "options": {
       "temperature": 0.7,
       "maxTokens": 500
     }
   }
   ```

### 4.3 Agent Flow for SMS Agent

**Recommended Flow Structure:**

```
[Start] → [Check Message Type] → [Branch]
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              [Weather API]   [Web Search]    [Direct LLM]
                    ↓               ↓               ↓
                    └───────────────┼───────────────┘
                                    ↓
                              [Format Response]
                                    ↓
                                  [End]
```

### 4.4 Example: Weather API Agent Flow

**Block 1: Start**
- Input: `${message}`

**Block 2: Condition**
- Check if message contains "weather"
- If true → Weather API
- If false → Web Search or Direct LLM

**Block 3: API Call - Weather**
```
Method: GET
URL: https://api.open-meteo.com/v1/forecast
Query Params:
  latitude: ${extractedLat}
  longitude: ${extractedLng}
  current: temperature_2m,weather_code
  temperature_unit: fahrenheit
```

**Block 4: Format Response**
```javascript
// Transform API response
const temp = ${apiResponse.current.temperature_2m};
const code = ${apiResponse.current.weather_code};
return `Current temp: ${temp}°F, Conditions: ${weatherCodes[code]}`;
```

**Block 5: End**
- Return formatted response to user

### 4.5 Variable Syntax in Agent Flows

**Input Variables** (from previous blocks):
```
${message}           // User's message
${variableName}      // Custom variable
${apiResponse}       // Previous API call result
${workspace}         // Workspace info
```

**In JSON Bodies**:
```json
{
  "userQuery": "${message}",
  "timestamp": "${timestamp}",
  "data": {
    "nested": "${nestedVariable}"
  }
}
```

**In URL/Headers**:
```
URL: https://api.example.com/search?q=${message}
Headers:
  Authorization: Bearer ${apiKey}
  X-User-ID: ${userId}
```

### 4.6 Connect Agent Flow to Workspace

1. **Save Your Flow**
   - Click **Save Flow**
   - Test with sample inputs

2. **Enable in Workspace**
   - Go to Workspace Settings
   - Scroll to **Agent Configuration**
   - Enable **Agent Flows**
   - Select your flow: "SMS Agent Flow"

3. **Set Flow Trigger**
   - **On Every Message** (always runs)
   - **On Specific Keywords** (runs when keywords detected)
   - **Manual Trigger** (you call it explicitly)

### 4.7 Testing Your Agent Flow

**In AnythingLLM UI:**
1. Open your workspace
2. Send a test message
3. Check **Flow Logs** to see execution
4. Debug any failed blocks

**Via SMS Agent:**
Your Python code automatically uses the flow when configured in the workspace.

## Step 6: Configure LLM Provider

### 4.1 Select Your LLM
1. Go to **Settings** > **LLM Preference**
2. Choose your provider:
   - **Local**: Ollama, LM Studio
   - **Cloud**: OpenAI, Anthropic, Google
3. Configure API keys/endpoints as needed

### 4.2 Recommended Settings
- **Temperature**: 0.7 (balanced creativity)
- **Max Tokens**: 500-1000 (keeps responses concise)
- **Top-P**: 0.9

## Step 6: Configure Chat Settings

### 5.1 Workspace Chat Settings
1. In workspace settings, configure:
   - **Chat History**: Enable (maintains context)
   - **Chat Mode**: **Chat** (not query mode)
   - **Response Mode**: **Streaming** (faster feedback)

### 5.2 Thread Management
Your SMS agent handles threads automatically:
- Each SMS starts a new thread by default
- Use `^thread(N):` to specify a thread
- Threads maintain conversation context

## Step 6: Enable Tools & Features

### 6.1 Recommended Tools to Enable
- ✅ **Web Search** - For current information
- ✅ **Web Scraping** - To fetch webpage content
- ✅ **Calculator** - For math queries
- ✅ **RAG** - If you upload documents to workspace

### 6.2 Optional Enhancements
- **Document Upload**: Add reference docs to workspace
- **Vector Database**: Improve retrieval accuracy
- **Custom Tools**: Add specialized functions

## Step 7: Test Your Setup

### 7.1 Test via API
Use the test script:
```bash
cd c:\wikipedia\glade-agent
python test_ai_integration.py
```

### 7.2 Test via SMS
Send a test message:
- "What's the weather in Seattle?" (tests weather integration)
- "Who won the latest NFL game?" (tests web search)
- "What is 2+2?" (tests basic query)

### 7.3 Expected Behavior
- **With "both" backend**: Get two responses (AnythingLLM + LM Studio)
- **With "anythingllm" backend**: Get one response with web search capability
- **With "lmstudio" backend**: Get one response (local only, no web search)

## Step 8: Optimize for SMS

### 8.1 Response Length Control
In system prompt, emphasize:
```
CRITICAL: Responses MUST be under 300 words for SMS delivery
Break long responses into key points
```

### 8.2 Message Splitting
The SMS agent automatically:
- Splits messages over 150 characters
- Caps at 10 chunks (1500 chars total)
- Preserves word boundaries

## Troubleshooting

### AnythingLLM Not Responding
1. Check AnythingLLM is running: http://localhost:3001
2. Verify API key in `settings.json`
3. Check workspace slug matches
4. Review logs in AnythingLLM admin panel

### Web Search Not Working
1. Ensure **Agent Configuration** > **Web Scraping** is enabled
2. Check search provider API keys (if required)
3. Test search directly in AnythingLLM UI first

### Responses Too Long
1. Update system prompt to emphasize brevity
2. Reduce **Max Tokens** in LLM settings
3. Add explicit length limits in prompts

### Timeout Errors
1. Increase timeout in `settings.json`:
   ```json
   "timeouts": {
     "anythingllm": 600  // Increase if needed
   }
   ```
2. Check AnythingLLM server performance
3. Consider using faster LLM model

## Advanced Configuration

### Custom Agent Tools
To add custom tools to AnythingLLM:
1. Go to **Settings** > **Agent Skills**
2. Click **Create Custom Skill**
3. Define function, parameters, and implementation
4. Enable for your workspace

### RAG (Document Upload)
To give AnythingLLM knowledge of specific documents:
1. Select workspace
2. Click **Upload Document**
3. Add PDFs, text files, or websites
4. Documents are embedded and searchable

### Multi-Workspace Setup
For different use cases:
1. Create separate workspaces (e.g., "personal", "work", "research")
2. Note each workspace's slug
3. Switch by changing `workspace_slug` in `settings.json`

## Best Practices

### System Prompt Tips
- ✅ Be explicit about response length limits
- ✅ Define the assistant's personality/tone
- ✅ Specify when to use web search
- ✅ Include format preferences (bullet points, numbered lists)
- ❌ Don't make prompts too rigid - allow flexibility

### Performance Optimization
- Use local LLMs (like LM Studio) for faster responses
- Enable streaming for better UX
- Set reasonable token limits
- Cache common queries if possible

### Security
- 🔒 Never expose API keys publicly
- 🔒 Use localhost-only binding for AnythingLLM
- 🔒 Regularly rotate API keys
- 🔒 Review conversation logs periodically

## Quick Reference

### Configuration Files
- **settings.json**: Main agent config
- **AnythingLLM UI**: http://localhost:3001
- **API endpoint**: http://localhost:3001/api/v1/workspace/{slug}/chat

### Key Settings
```json
{
  "ai_backend": {
    "provider": "both",  // or "anythingllm" or "lmstudio"
    "anythingllm": {
      "workspace_slug": "glade_automation",
      "api_key": "YOUR-KEY-HERE",
      "url": "http://localhost:3001"
    }
  },
  "timeouts": {
    "anythingllm": 600
  }
}
```

### Useful Commands
- Test config: `python test_config_persistence.py`
- Test AI: `python test_ai_integration.py`
- Check agent status: View startup logs
- Switch backends: Edit `settings.json` > restart agent

## Next Steps

1. ✅ Configure AnythingLLM workspace with system prompt above
2. ✅ Enable web scraping/search agents
3. ✅ Test with a few SMS messages
4. ✅ Adjust system prompt based on response quality
5. ✅ Fine-tune token limits and temperature
6. ✅ Add any custom documents via RAG if needed

---

**Need Help?**
- Check AnythingLLM docs: https://docs.anythingllm.com
- Review agent logs for errors
- Test in AnythingLLM UI before SMS testing
