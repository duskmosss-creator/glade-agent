# Glade Agent: Complete Command Reference

This document provides a comprehensive guide to all available commands for the Glade Agent.

---

## 1. Weather & Environmental Data

### **Current Weather**
**Syntax:** `!weather <location>`  
**Example:** `!weather Seattle`  
**Description:** Fetches current atmospheric conditions and a 12-hour forecast summary from the nearest observation station.  
**Output:** Text-based report.
> **Now:** 45°F, Overcast.  
> **Summary:** Rain expected to begin around 9 PM. Low of 40°F.

---

### **Interactive Radar (Static)**
**Syntax:** `!radar <location> <miles>`  
**Example:** `!radar Seattle 30`  
**Description:** Generates a high-quality NEXRAD radar overlay on an OpenStreetMap base. Uses **60% transparency** and **BoxBlur smoothing** for a professional look.  
**Output:** A high-quality map sent via MMS and Cloud Link.

![Static Radar Example](doc_assets/radar_static.png)

---

### **Animated Radar (30m Loop)**
**Syntax:** `!radar <location> <miles> gif`  
**Example:** `!radar Seattle 30 gif`  
**Description:** Generates a 30-minute animated loop of the past 30 minutes of weather data at 5-minute intervals.  
**Output:** An animated GIF showing precipitation movement.

![30m Radar GIF Example](doc_assets/radar_30m.gif)

---

### **Animated Radar (Full Hour Loop)**
**Syntax:** `!radar <location> <miles> gif 60`  
**Example:** `!radar Seattle 30 gif 60`  
**Description:** Generates a 60-minute animated loop showing the full past hour of data.  
**Output:** An extended animated GIF useful for tracking large storm fronts.

![60m Radar GIF Example](doc_assets/radar_60m.gif)

---

### **Hourly Forecast**
**Syntax:** `!forecast<hours> <location>`  
**Example:** `!forecast24 Seattle`  
**Description:** Provides a detailed hour-by-hour breakdown of temperature, wind speed, and weather conditions.  
**Output:** A multi-part SMS list.
> **10am:** 42°F (Rain)  
> **11am:** 43°F (Storms)  
> **12pm:** 41°F (Cloudy)

---

### **Temperature History**
**Syntax:** `!temp-history <location>`  
**Example:** `!temp-history Seattle`  
**Description:** Retrieves historical observation data from the past 24 hours to show the recent cooling or warming trend.  
**Output:** A list of hourly temperature readings.

---

---

### **System Check**
**Syntax:** `!check`  
**Example:** `!check`  
**Description:** Performs diagnostic checks on hardware (Disk/CPU), Connectivity (Gmail), and AI Model availability.  
**Output:** A status report.

---

## 3. Agent Management

### **Clear History**
**Syntax:** `!clear`  
**Example:** `!clear`  
**Description:** Wipes your personal conversation history from the host database. This resets the AI's short-term memory of you.  
**Output:** A confirmation message.

---

### **Command List**
**Syntax:** `!info`  
**Example:** `!info`  
**Description:** Displays the quick-reference command list directly in the SMS thread.  
**Output:** A short list of active commands.

---

### **Connection Test**
**Syntax:** `!test`  
**Example:** `!test`  
**Description:** Sends a simple "Ping" to the agent to confirm it is online.  
**Output:** `[OK] Test complete. Glade Agent is functioning normally.`
