# Weather Integration for AnythingLLM

## How It Works

The SMS agent now automatically detects weather-related queries and injects real NOAA weather data into AnythingLLM's context. This means users can ask natural language questions and get accurate, real-time weather information.

## Example Queries

**Natural Language (Automatic Detection):**
- "What's the weather in Seattle?" → Auto-fetches NOAA data + sends to AI
- "Is it going to rain in Miami?" → Auto-fetches NOAA data + sends to AI
- "What's the temperature in 98101?" → Auto-fetches NOAA data + sends to AI
- "How hot is it in Los Angeles?" → Auto-fetches NOAA data + sends to AI

**Command Format (Direct Response):**
- `!weather_Seattle` → Instant NOAA weather response (no AI)
- `!weather_98101` → Instant NOAA weather response (no AI)

## How Detection Works

The system detects weather queries by looking for:

**Keywords:**
- weather, temperature, temp, forecast
- rain, snow, sunny, cloudy
- hot, cold, warm, climate

**Location Patterns:**
- "in <location>" → "weather in Miami"
- "at <location>" → "temperature at Denver"  
- "for <location>" → "forecast for Chicago"
- ZIP codes → "weather in 90210"

## What Gets Sent to AnythingLLM

When a weather query is detected, the system:

1. Extracts the location from the query
2. Fetches real-time NOAA weather data
3. Prepends it to the user's question as context
4. Sends both to AnythingLLM

**Example:**
```
User asks: "What's the weather like in Seattle today?"

AnythingLLM receives:
[CURRENT WEATHER DATA FROM NOAA]
Weather in Seattle, King County, Washington:
🌡️ Temperature: 36°F
☁️ Conditions: Slight Chance Light Rain
💨 Wind: 1 mph

[USER QUESTION]
What's the weather like in Seattle today?
```

AnythingLLM then responds naturally using the real data!

## Supported Locations

- **US ZIP Codes:** 98101, 90210, 10001, etc.
- **City Names:** Seattle, Miami, Denver
- **City,State:** "Miami,FL", "Austin,TX"

## Benefits

✅ **No agent mode required** - Works with standard AnythingLLM chat
✅ **Real NOAA data** - Accurate, official weather information
✅ **Natural language** - Users ask however they want
✅ **Cached responses** - 10-minute cache reduces API calls
✅ **Automatic** - No special commands needed

## If Location Not Detected

If the system detects a weather query but can't find a location:
```
User: "What's the weather?"
Response: "I can get weather information for you! Please specify a location..."
```

## Testing

Try these queries to test the integration:
1. "What's the weather in your city?"
2. "Is it raining in 98101?"
3. "How cold is it in Denver?"
4. "Tell me about the forecast in Miami,FL"
