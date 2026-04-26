# Approved Features (DO NOT MODIFY)

This document lists features that have been implemented, tested, and **APPROVED** by the user. These features are considered "Frozen" (Production/Frozen) and should not be modified unless explicitly requested.

## 1. Core Architecture

### **V2 Isolation**

- **Description**: The agent operates from the `sms_v2_agent/` directory, isolated from legacy code.
- **Status**: APPROVED.
- **Constraint**: All new development must happen within `sms_v2_agent/`.

### **"No AI" Mode**

- **Description**: A headless, command-only mode that disables all conversational AI capabilities.
- **Functionality**:
  - Skips interactive startup wizard.
  - Skips importing heavy libraries (Torch, Ultralytics) to save RAM/Boot time.
  - Only responds to deterministic commands (`!weather`, `!radar`).
- **Status**: APPROVED.
- **Constraint**: Maintain the "No AI" option in `settings.json` and ensure it remains lightweight.

## 2. Weather & Environmental Data

### **!weather <location>**

- **Description**: Fetches current weather and 12-hour forecast from NOAA.
- **Status**: APPROVED.

### **!radar <location> <miles> [gif] [duration]**

- **Description**: Generates high-quality NEXRAD radar maps overlaid on OpenStreetMap.
- **Features**:
  - **Static Images**: High-resolution PNGs with 60% opacity and box-blur smoothing.
  - **Animated GIFs**:
    - 30-minute loop (`gif 30`) with 5-minute intervals.
    - 60-minute loop (`gif 60`) with 10-minute intervals.
- **Status**: APPROVED.
- **Constraint**: Do not alter the transparency or smoothing algorithms without permission.

### **!info**

- **Description**: Sends a concise list of available commands.
- **Status**: APPROVED.

## 4. System & Configuration

### **Settings.json**

- **Description**: Central configuration file for all backends, keys, and preferences.
- **Status**: APPROVED.
- **Constraint**: Must remain the single source of truth for configuration.
