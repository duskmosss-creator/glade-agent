# Complete SMS Agent Model Setup - ALL FEATURES

## Overview of Features

Your SMS agent supports:
1. **Regular Chat** - Simple question/answer
2. **Wiki Agent** - Wikipedia research
3. **Plant ID** - Image-based plant identification
4. **Weather** - NOAA weather data (no model needed)
5. **Status** - System status (`!status` command)

---

## Complete Setup by Option

### Option 2: LM Studio Only (All Features)

**LM Studio (Port 1234):**
- Primary model: `llama-3.2-1b-instruct`

**Load in LM Studio:**
1. `llama-3.2-1b-instruct` - Keep loaded for chat

**Local (No server needed):**
- Plant ID: `plant_yolov8s.pt` (loaded automatically)

**Features Available:**
- ✅ Regular chat (llama-3.2-1b)
- ❌ Wiki Agent (needs larger model)
- ✅ Plant ID
- ✅ Weather

---

### Option 5: Wiki + Lemonade (RECOMMENDED)

**Lemonade (Port 8000):**
- Main model: `qwen3-8b-flm` (for Wiki research)
- Plant ID model: `Qwen2.5-VL-7B-Instruct` (for plant images)

**Local:**
- Plant ID: `plant_yolov8s.pt`

**Features Available:**
- ✅ Wiki Agent (qwen3-8b-flm)
- ✅ Plant ID
- ✅ Weather

---

### Option 6: Wiki + LM Studio

**LM Studio (Port 1234):**
- Main model: `qwen/qwen3-8b` (for Wiki)

**Load Strategy:**
- Keep `qwen/qwen3-8b` loaded by default

**Local:**
- Plant ID: `plant_yolov8s.pt`

**Features Available:**
- ✅ Wiki Agent (qwen/qwen3-8b)
- ✅ Plant ID
- ✅ Weather

---

## Full-Featured Setup (ALL features working)

### Recommended: Dual-Server Configuration

**Server 1: Lemonade (Port 8000)**
- Model: `qwen3-8b-flm`
- Use: Wiki Agent, Plant ID vision processing

**Server 2: LM Studio (Port 1234)**  
- Model: `llama-3.2-3b-instruct` (Optional, for faster chat)
- Use: Standard chat fallback

**Local:**
- `plant_yolov8s.pt` for fast plant detection

**Agent Mode:** Option 5 (Wiki + Lemonade)

**This gives you:**
- ✅ Wiki Agent (Lemonade qwen3-8b-flm)
- ✅ Plant ID (YOLOv8 + vision model fallback)
- ✅ Weather
- ✅ All SMS commands

---

## Quick Reference Table

| Feature | Model Required | Where | Port |
|---------|---------------|-------|------|
| Regular Chat (small) | `llama-3.2-1b-instruct` | LM Studio | 1234 |
| Regular Chat (Lemonade) | `llama-3.2-1b-flm` | Lemonade | 8000 |
| **Wiki Agent** | `qwen3-8b-flm` | **Lemonade** | **8000** |
| **Wiki Agent** (alt) | `qwen/qwen3-8b` | LM Studio | 1234 |
| Plant ID (fast) | `plant_yolov8s.pt` | Local | - |
| Plant ID (vision) | `Qwen2.5-VL-7B-Instruct` | Lemonade/LM Studio | 8000/1234 |

---

## Minimal Setup (Just get it running)

**Load ONE of these:**

1. **Lemonade (port 8000)**: `qwen3-8b-flm`  
   → Select Option 5  
   → Get: Wiki + Plant ID + Weather

2. **LM Studio (port 1234)**: `llama-3.2-1b-instruct`  
   → Select Option 2  
   → Get: Chat + Weather (no Wiki)

---

## Maximum Features Setup

**Run TWO instances:**

1. **Lemonade**: Load `qwen3-8b-flm` on port 8000
2. **LM Studio**: Load `llama-3.2-3b-instruct` on port 1234

**Select Option 5**

**You get everything: Wiki + Plant ID + Weather ✅**
