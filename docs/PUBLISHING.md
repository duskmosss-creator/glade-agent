# Publishing Guide for Glade Agent

This guide outlines the steps to package and publish your local Glade Agent instance for public use or redistribution.

## 📦 Packaging for Distribution

When sharing the Glade Agent, you should provide a clean copy that doesn't contain your personal credentials or conversation logs.

### 1. Clean the Project
Remove temporary folders that contain sensitive or unnecessary data:
- `logs/` (Contains conversation transcripts)
- `attachments/` (Local copies of images/audio received)
- `weather/` (Generated radar maps and icons)
- `__pycache__/` (Python cache files)
- `processed_uids.json` (Internal tracking of processed SMS)

### 2. Sanitize Configuration
1. Open `config/settings.json`.
2. Remove your **Gmail address** and **App Password**.
3. Remove any custom local paths (e.g., ZIM file paths for Wikipedia) that won't work on another machine.
4. Update `settings.json.example` to reflect the latest configuration structure.

### 3. Create the Release Bundle
1. Create a new folder (e.g., `Glade-Agent-Release`).
2. Copy the Following:
   - `src/` folder
   - `config/` folder (with sanitized JSONs)
   - `agents/` folder (containing the `.bat` launchers)
   - `docs/` folder
   - `tools/` folder
   - `requirements.txt`
   - `README.md`
3. Zip the entire folder for distribution.

---

## 🚀 GitHub Upload Instructions

If you are uploading to a public GitHub repository:

1. **Check .gitignore**: Ensure the `.gitignore` file includes `config/settings.json`, `logs/`, `attachments/`, and `weather/`.
2. **Commit Source**: Commit only the `src/`, `config/*.example`, `agents/`, `docs/`, and `tools/` directories.
3. **Draft Release**: On GitHub, go to the **Releases** tab and upload your `.zip` bundle as a binary asset.

## 📡 Deployment Check
Before publishing, always run the `!check` command on a fresh instance to ensure all essential dependencies and folder structures are detected correctly.
