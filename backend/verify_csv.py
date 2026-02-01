from app.config import Settings
import os

try:
    os.environ["CORS_ORIGINS"] = "http://comma.com,http://separated.com"
    s = Settings()
    print(f"Comma Separated: {s.cors_origins}")
except Exception as e:
    print(f"Comma Separated Failed: {e}")
