# AI Backend & Model Setup Guide

This guide covers everything you need to know about setting up your local AI providers (Lemonade or LM Studio) to work flawlessly with the Off-Grid SMS Agent. It includes exact ports, recommended models, context sizes, and non-obvious settings.

---

## 🏗️ Essential Setup: Ports, Context, and Features

Before running any models, ensure your local AI server is configured correctly. The agent relies on exact ports and configurations to communicate.

### 1. Port Configuration (CRITICAL)
The agent expects specific providers to be available on specific ports:
*   **Lemonade Engine:** Must be running on `Port 8000`
*   **LM Studio:** Must be running the local server on `Port 1234`
*   *Note: If you change these ports in your server software, you must also update the `url` fields in the `settings.json` file to match.*

### 2. Context Window & Settings
For optimal performance over SMS and offline Wiki reading:
*   **Context Length:** Set to **8192 tokens**. The agent downloads large chunks of Wikipedia articles that can easily exceed default small context windows. If your context is set too low (e.g. 2048), large searches will crash the AI.
*   **System Prompt:** Leave the server's system prompt *blank*. The Off-Grid Agent dynamically sends its own highly-specialized SMS system prompts for every request.
*   **CORS (Cross-Origin Resource Sharing):** If using LM Studio, ensure CORS is **ON** in the developer settings.

### 3. ZIM File Storage (Wikipedia)
*   **Storage Speed:** The Wikipedia ZIM file is massive (~100GB+). Store it on an **NVMe or internal SSD**. Running it off a mechanical hard drive or a slow external USB stick will cause severe timeout errors during search phases.

---

## 🧠 Model Recommendations

Using the right model determines how fast the agent responds to texts and how smart it is at reading Wikipedia.

### Scenario A: The Recommended Default (Wiki + Lemonade)
Use this setup for the most robust, full-featured experience.
*   **Server:** Lemonade (Port 8000)
*   **Model:** `Qwen2.5-7B-Instruct` or `Qwen3-8b` (Quantized to Q4_K_M or Q5_K_M)
*   **Why:** The Qwen architecture is spectacularly good at tool-use. It flawlessly follows the command structures required to trigger the "SEARCH" and "CONTINUE" Wikipedia commands without hallucinating.

### Scenario B: Fast Texting & Basic Commands
If you only care about fast SMS weather reports and system checks, use a lightweight model.
*   **Server:** LM Studio (Port 1234) or Lemonade (Port 8000)
*   **Model:** `Llama-3.2-1B-Instruct` or `Llama-3.2-3B-Instruct`
*   **Why:** 1B and 3B parameter models can run on almost any computer instantly, resulting in 2-second SMS replies. However, they are *not* smart enough to navigate Wikipedia.

---

## 🚀 How to Launch the System

1. **Start the AI Server:** Open Lemonade or LM Studio, load your chosen model, and click "Start Server".
2. **Start the Agent:** Double-click `run_glade_agent.bat`.
3. **Select your Mode:**
    *   **Press Enter (Default):** Connects to Lemonade looking for Qwen to run the Wiki Agent.
    *   **Type `2`:** Connects to LM Studio for fast, standard chat (no Wikipedia).
    *   **Type `6`:** Forces LM Studio to try and run the Wiki Agent (ensure you loaded Qwen first!).

## Troubleshooting
*   **"Unreachable" Error:** Your AI server isn't running, or it's on the wrong port. Check `settings.json`.
*   **"Context Exceeded" Error:** You searched for a massive Wikipedia article and your Context Length is set too low. Increase it to at least 8192 in your AI server settings.
*   **Agent says "I cannot search the internet":** Your model isn't smart enough to realize it has offline wiki tools. Switch to a Qwen 7B/8B model.
