# Glade Agent: Complete Setup Guide

This guide covers everything you need to get your low-bandwidth SMS/MMS agent up and running, from installing dependencies to managing large offline Wikipedia databases.

---

## 💻 System Requirements

*   **OS**: Windows 10/11 (Scripts are optimized for PowerShell/CMD).
*   **RAM**: 
    *   Minimum: 8GB (for agent + small model).
    *   Recommended: 16GB+ (for smooth radar generation and larger LLMs).
*   **Storage**: 
    *   Agent Core: < 100MB.
    *   AI Models: 2GB - 15GB (depending on the model chosen).
    *   Wikipedia (ZIM): 1GB - 120GB (see Storage section below).

---

## 🐍 1. Python Environment & Dependencies

It is **strongly recommended** to use [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) to manage your environment, as it simplifies the installation of heavy libraries like `libzim` and `onnxruntime`.

### Step 1: Create Environment
```powershell
conda create -n glade python=3.10
conda activate glade
```

### Step 2: Install Core Dependencies
Run this in the root folder:
```powershell
pip install -r requirements.txt
```

### Step 3: Special Dependency Notes
*   **imap-tools**: Handles the Gmail/SMS bridging. If you get a `ModuleNotFoundError`, run `pip install imap-tools`.
*   **libzim**: Required for offline Wikipedia. If the standard pip install fails on Windows, you may need to download a pre-built wheel for your Python version.
*   **ultralytics**: Used for the Plant Identification Vision system.

---

## 📚 2. Wikipedia (ZIM) Storage Estimates

The Glade Agent uses `.zim` files to provide offline knowledge. You can download these from [Kiwix](https://library.kiwix.org/).

| Wikipedia Version | Approx. Size | Description |
| :--- | :--- | :--- |
| **Top 100k (Mini)** | ~5 GB | The most popular 100,000 articles with images. Great for small drives. |
| **Simple English** | ~1 GB | Simple versions of articles. Very low storage footprint. |
| **Full (No Images)** | ~55 GB | Every single English article, text-only. Ideal for pure information. |
| **Full (With Images)**| ~119 GB | The complete English Wikipedia. Requires significant disk space. |

> [!TIP]
> Place your `.zim` file in a dedicated folder (e.g., `C:\Knowledge\wikipedia.zim`) and update the `zim_path` in your `settings.json`.

---

## ✉️ 3. Gmail & SMS Configuration

The agent communicates by "reading" your Gmail inbox and "replying" via SMTP.

1.  **Enable 2FA**: Your Google account must have 2-Factor Authentication enabled.
2.  **Create App Password**: 
    *   Go to Google Account Settings → Security.
    *   Search for "App Passwords".
    *   Create one named "Glade Agent" and copy the 16-character code.
3.  **Gmail Labels**: 
    *   Open Gmail.
    *   Create a label named `off-grid-agent`.
    *   When you receive a text, apply this label to the thread to let the agent take control.

---

## 🧠 4. AI Backend Options & Model Selection

The Glade Agent is a "brain-optional" system—it needs a local API to talk to. Here are the supported backends and recommended models for various hardware.

### A. Backend Providers & Startup Options

When you start the Glade Agent, you will be prompted to select one of four backend modes:

| Mode | Backend Focus | Best For... |
| :--- | :--- | :--- |
| **1. LM Studio** | Pure LM Studio | Visual model browsing, easy GUI setup, and fast chat. |
| **2. Lemonade** | Pure Lemonade | Ultra-lightweight headless server, best for low-resource hardware. |
| **3. Wiki Agent (Lemonade)** | Hybrid | Uses Lemonade for chat and Wikipedia integration. |
| **4. Wiki Agent (LM Studio)**| Hybrid | Uses LM Studio for chat and Wikipedia integration. |

### B. Required Models

To match the built-in startup options, you will need the following models downloaded in your respective backends:

*   **Qwen3-VL-8B**: The primary model used when running via **LM Studio** (Options 1 and 4). It handles both high-intelligence text chat and vision tasks (for the `!identify` command).
*   **Llama-3.2-1B-FLM**: An ultra-lightweight model used when running the pure **Lemonade** backend (Option 2). Ideal for very low-resource hardware.
*   **Qwen3-8b-FLM**: The primary model used when running the **Wiki Agent** via Lemonade (Option 3), providing the intelligence needed to parse offline Wikipedia data.

---

## ⚙️ 5. Configuration (settings.json)

Rename `config/settings.json.example` to `settings.json` and update these keys:

```json
{
  "email": {
    "address": "yourname@gmail.com",
    "app_password": "xxxx xxxx xxxx xxxx",
    "gmail_label": "off-grid-agent"
  },
  "ai_backend": {
    "provider": "lmstudio", 
    "zim_path": "C:\\Data\\wikipedia.zim",
    "model_name": "llama-3.2-3b-instruct" 
  }
}
```

> [!NOTE]
> If using **LM Studio**, ensure the "Local Server" tab is active and the port (usually `1234`) matches your config. If using **Ollama**, the default port is `11434`.


---

## 🚀 6. Launching the Agent

Navigate to the `agents/` folder:
1.  **Double-click `run_glade_agent.bat`**.
2.  The console will show a "Startup Configuration" menu.
3.  You have **90 seconds** to choose if you want to process offline messages or change your AI backend.
4.  Once the "Initialization complete" message appears, you are live!

---

## ❓ Troubleshooting

*   **"No module named imap_tools"**: Run the `.bat` file as an Administrator or ensure your Python PATH is set correctly.
*   **Radar images not appearing**: Check the `weather/` folder. If images are there but not on your phone, your carrier might be blocking links. The agent will automatically try to use carrier-specific MMS gateways to bypass this.
*   **404 Error for AI Backend**: Ensure LM Studio server is actually started and the port matches your `settings.json`.
