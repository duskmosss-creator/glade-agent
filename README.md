# Glade Agent

**Glade Agent** is a lightweight, low-bandwidth AI backend service that enables users to interact with large language models, fetch real-time weather/radar data, identify plants, and query Wikipedia entirely over SMS or local network tools instead of a heavy web interface.

Built to be resilient and accessible in off-grid or low-connectivity scenarios, Glade Agent bridges modern AI systems with simple text communication.

---

## 🚀 Features

- **Conversational AI via SMS:** Connects to powerful Local AI backends (AnythingLLM, LM Studio, Ollama, etc.) to securely answer questions.
- **Live Weather & Forecasts:** Fetch current weather conditions and granular forecasts by sending `!weather <location>`.
- **Weather Radar Generation:** Generate both static images and animated GIF loops of local weather radar using `!radar <location>`.
- **Offline Wikipedia Search:** Search an offline local Wikipedia database to retrieve encyclopedic knowledge without internet access.
- **Plant ID:** Send an image of a plant and the agent will use Vision-Language models to identify it in seconds.
- **Stateless/Offline Reliability:** If connections drop, the agent safely logs history and intelligently resumes answering accumulated messages when it comes back online.

---

## 🛠️ Plug and Play Setup

Getting the Glade Agent running is simple:

### 1. Configure the Agent
1. Clone or download the repository.
2. Go to the `config/` directory.
3. Rename `settings.json.example` to `settings.json`.
4. Open `settings.json` and plug in your details:
   - **Your Gmail Address & App Password** (Used to bridge the SMS interactions).
   - **AI Backend Details** (Select your provider and add your API Key/URL).

### 2. Install Dependencies
Ensure you have Python 3.9+ installed. Run the following command in the project directory:
```bash
pip install -r requirements.txt
```

### 3. Run the Agent
On Windows, navigate to the `agents/` folder and double-click the start script:
- **Glade Agent (SMS)**: `agents/run_glade_agent.bat`
- **Wiki Agent (Research)**: `agents/run_wiki_agent.bat`

The agent will initialize, perform a system check, connect to your local AI instance, and begin monitoring for commands.

### 4. Activate your Text Thread
Because the agent monitors a specific Gmail label, you must "hand off" your text thread to it:
1. Send a text to your associated Google Voice/SMS number.
2. Open Gmail and find the incoming email for that text.
3. Apply the label `off-grid-agent` (or whatever you set in `settings.json`) to the **entire thread**.
4. The agent will now automatically pick up and respond to all future messages in that thread!

---

## 📝 Commands Reference

You can text these commands to your agent's associated number:
- `!weather <location>`: Get current weather + high-fidelity forecast (Humidity, Wind, Gusts).
- `!forecast <location>`: Fetch a detailed hourly trend graph/data.
- `!radar <location> <miles>`: Receive a weather radar static map. Add `gif` to the end for an animated radar loop.
- `!temp-history <location>`: View the past 24-hour temperature trend from local observations.
- `!wiki <query>`: Direct lookup in the offline Wikipedia database.
- `!research <topic>`: Trigger a multi-step autonomous investigation with a PDF report.
- `!identify`: Send an image to identify a plant or object.
- `!info`: View system information and the basic help menu.
- `!check`: Run a backend diagnostic to ensure all models and services are online.
- `!clear`: Clear your conversation history with the AI.

> [!TIP]
> **Intelligent Sensing**: The weather system now uses strict word matching and an ignore list. It won't trigger randomly if you mention "photos" or "cameras" in a normal conversation!

---

## 🧠 Supported AI Backends
The Glade Agent is extremely flexible and can be hooked up to almost any text-generation backend:
- **AnythingLLM** (Default)
- **LM Studio** 
- **Ollama** 
- **OpenAI Compatible endpoints**

You can switch models immediately on startup or define them persistently in `settings.json`.

---

## ⚠️ Requirements
- Python 3.9+
- A Google Voice account tied to a Gmail inbox (for SMS bridging)
- (Optional) An active local AI service running Llama 3 or similar
- (Optional) SQLite3 for local conversation tracking

## 📜 License
This software is provided under open-source terms. Feel free to fork, modify, and improve the Glade Agent for your own low-bandwidth automation setups.
