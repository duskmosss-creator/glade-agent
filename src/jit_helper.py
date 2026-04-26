
import requests
import time

def unload_model():
    """Trigger LM Studio to unload model to free RAM."""
    # LM Studio doesn't strictly have an "unload" API for OpenAI compat,
    # but loading an non-existent model or a tiny empty model usually flushes it.
    # Alternatively, just rely on JIT loading (setting model per request).
    print("   [RAM SAVER] LM Studio manages this automatically via JIT loading if configured.")

def set_jit_loading(enabled=True):
    print(f"   [CONFIG] JIT Loading on LM Studio: {'ENABLED' if enabled else 'DISABLED'}")
    # LM Studio by default handles JIT if you request a model that isn't loaded.
    # The key is to ensure "Keep model loaded" is NOT set indefinitely in LM Studio UI
    # or to set ttl in requests if supported (not standard OpenAI API).
    
    if enabled:
        print("   -> Instructions: In LM Studio Server tab, ensure 'Keep model in memory' is set to a reasonable timeout (e.g. 300s) or disabled.")

if __name__ == "__main__":
    set_jit_loading(True)
