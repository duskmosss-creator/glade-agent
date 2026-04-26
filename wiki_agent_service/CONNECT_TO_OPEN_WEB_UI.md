# How to Connect Wiki Agent to Open Web UI

You can connect your offline Wiki Agent to Open Web UI (formerly Ollama Web UI) to chat with it continuously.

## Prerequisites
1. Ensure `serve_wiki_agent.bat` is running (Port 8002).
2. Ensure your backend LLM (Lemonade or LM Studio) is running.

## Connection Steps

1. Open **Open Web UI**.
2. Click on your profile icon (bottom left) and go to **Settings**.
3. Select **Connections** (or **Admin Settings > Connections** if you are simple user).
4. Find the **OpenAI API** section.
5. Add a new connection:
   - **URL**: `http://localhost:8002/v1`
     *(Note: If Open Web UI is running in Docker, use `http://host.docker.internal:8002/v1` instead)*
   - **Key**: `any-key-you-want` (Authentication is disabled)
6. Click **Save** or the verify checkmark.

## Using the Agent
1. Go to the **New Chat** screen.
2. In the model selector drop-down, look for **wiki-agent-offline**.
   *(If you don't see it, try refreshing the page)*.
3. Select it and start chatting!

## Troubleshooting
- **"Connection Failed"**: Check if the console window for `serve_wiki_agent.bat` shows any request attempts.
- **Docker Users**: If `localhost` doesn't work, ensure you added `--add-host=host.docker.internal:host-gateway` to your Docker run command, or use your PC's specific LAN IP address (e.g., `http://192.168.1.50:8002/v1`).
