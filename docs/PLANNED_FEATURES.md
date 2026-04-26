# Planned Features (Roadmap)

This document outlines features that are planned, actively being developed, or require enhancements.

## 1. Research Agent Refinements

### **Deep Research Loop Stability**

- **Goal**: Ensure the "Unlimited" loop logic can handle 50-step research tasks without infinite loops or errors (e.g., repeating the same search).
- **Status**: Pending Verification (V2 Integration & Testing).

### **Map Search Accuracy**

- **Goal**: Tune Overpass API queries to be more forgiving for vague locations (e.g., "hot springs near here").
- **Status**: Pending Validation (V2 Integration & Testing).

### **SMS Summary for Reports**

- **Goal**: Ensure the SMS notification for a completed report provides a concise summary to preview the PDF content.
- **Status**: Pending Verification (V2 Integration & Testing).

### **Web vs. Map Auto-Decision**

- **Goal**: The agent should intelligently decide whether to use Web Search or Map Search for ambiguous queries (e.g., "Find a trail" vs "What is a trail").
- **Status**: Planned (V2 Integration & Testing).

## 2. Infrastructure Enhancements

### **User Manual Update**

- **Goal**: Update the `Off-Grid_Agent_Manual_Full.pdf` to include the new V2 commands (`!research`, `!radar gif`) and capabilities.
- **Status**: Planned (Finalize).

### **System Diagnostics**

- **Goal**: Add V2-specific health checks to `!check` (e.g., check `duckduckgo-search` connectivity, Overpass API limits).
- **Status**: Planned (Refinement).

## 3. Deployment

### **V2 Promotion**

- **Goal**: Promote the V2 codebase (`sms_v2_agent/`) to become the primary production agent (replace root `main.py` or rename folders), ensuring zero downtime.
- **Status**: Planned (Final User Acceptance).

## 4. Chat Memory

### **Persistent Chat History**

- **Goal**: Implement a mechanism to store and retrieve chat history across sessions for a given user.
- **Status**: Planned (Design Phase).

### **Contextual Recall**

- **Goal**: Enable the agent to recall relevant past conversations to inform current responses, improving continuity and reducing redundancy.
- **Status**: Planned (Design Phase).
