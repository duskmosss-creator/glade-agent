# Glade Agent: Low-Bandwidth Digital Autonomy

**Glade Agent** is an autonomous, low-bandwidth communication bridge that brings modern AI capabilities and high-fidelity data retrieval to environments with limited or no internet access. 

By utilizing standard SMS and MMS messaging, the Glade Agent allows users to interact with local AI models, fetch real-time weather radar, and access encyclopedic knowledge without ever needing a web browser or a stable data connection.

---

## 🛰️ The Low-Bandwidth Mission

In off-grid, emergency, or remote scenarios, bandwidth is a luxury. Modern web interfaces are heavy, trackers are everywhere, and simple tasks require megabytes of data. 

**Glade Agent** solves this by:
- **Minimizing Data**: A single text message (a few bytes) can trigger a complex AI query or fetch a detailed radar map.
- **MMS Optimization**: Images are processed and compressed on your local server, then delivered directly to your phone via carrier MMS gateways.
- **Digital Autonomy**: Keep your intelligence local. All AI processing happens on your hardware (using LM Studio, Lemonade, or Ollama).
- **Resilient Delivery**: Smart message splitting ensures your AI's answers arrive intact, even on restrictive carrier networks.

---

## 🚀 Core Features

### 1. Conversational AI via SMS
Connect your agent to a local LLM. Text a question, and receive a response directly in your SMS thread. Perfect for troubleshooting, medical advice, or just offline intelligence.

### 2. High-Fidelity Weather Radar
Request live radar for any location with `!radar <location>`. 
- **Static Maps**: High-contrast, easy-to-read radar images.
- **Animated GIFs**: Loops showing storm movement, delivered as MMS or secure cloud links.
- **Smart Routing**: Automatically detects your carrier (Verizon, AT&T, etc.) to ensure attachments bypass standard SMS filters.

### 3. Detailed Forecasts & Trends
Beyond simple temperatures, get granular NOAA-sourced data including wind gusts, humidity, and 24-hour historical temperature trends to track incoming fronts.

### 4. Plant Identification
Send an image of a plant to the agent; it uses Vision-Language models to provide an identification and care summary within seconds.

---

## 🛠️ Setup Guide

### 1. Prerequisites
- **Python 3.10+**
- **Gmail Account**: With an App Password enabled (acts as the SMS bridge).
- **Local AI Backend**: LM Studio or Lemonade running an OpenAI-compatible API.

### 2. Quick Start
1. Download the **[v1.0 Release ZIP](https://github.com/duskmosss-creator/glade-agent/releases)**.
2. Extract and navigate to `config/`.
3. Rename `settings.json.example` to `settings.json` and enter your Gmail and AI details.
4. Run `pip install -r requirements.txt`.
5. Start the agent: `agents/run_glade_agent.bat`.

### 3. Activating your SMS Thread
1. Send a text to your Google Voice number.
2. In Gmail, find the resulting email and label the thread as `off-grid-agent`.
3. The agent will now own that thread and respond to all future texts.

---

## 📝 Commands

| Command | Action |
| --- | --- |
| `!weather <loc>` | Current conditions + 12h forecast |
| `!radar <loc> [gif]` | Static or animated radar map |
| `!forecast <loc>` | Detailed hourly trend data |
| `!temp-history <loc>` | 24-hour temperature graph |
| `!info` | System status and help menu |
| `!check` | Diagnostic check of all backends |
| `!clear` | Reset AI conversation history |

---

## 📜 Privacy & License
Glade Agent is open-source and privacy-focused. No personal data, location data, or conversation history is ever sent to third-party servers. All links are enforced over HTTPS.
