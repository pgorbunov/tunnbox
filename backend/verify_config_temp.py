from app.config import Settings
import os

try:
    # Test default
    s = Settings()
    print(f"Default CORS: {s.cors_origins}")
    assert "http://localhost:5173" in s.cors_origins

    # Test env var override
    # Note: pydantic-settings reads from env vars.
    # We need to set it before instantiating if we want to test override.
    # However, env vars might be cached or read at import time depending on implementation details
    # but Settings() usually reads fresh.
    
    os.environ["CORS_ORIGINS"] = "[\"http://foo.com\",\"http://bar.com\"]" 
    # Wait, pydantic-settings for list[str] usually expects JSON formatted string for complex types or simple parsing? 
    # Standard pydantic-settings v2 usually parses JSON for list types in env vars OR comma separated if configured.
    # Let's test what behavior we get. If it fails, we know we might need to adjust config or doc.
    # Actually, for `list[str]`, pydantic-settings often expects a JSON array string.
    # If we want comma separated, we might need a Validator or specific configuration.
    # Let's try JSON first as that's safer default for pydantic.
    
    s2 = Settings()
    print(f"Override CORS (JSON): {s2.cors_origins}")
    
    # If user wants comma separated (which is what .env.example implies), we might need to change implementation 
    # or confirm pydantic behaviors. 
    # Let's try comma separated next if this works or fails.
except Exception as e:
    print(f"Error: {e}")
