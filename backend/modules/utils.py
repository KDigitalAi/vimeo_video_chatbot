# backend/modules/utils.py
import logging
from pathlib import Path

LOG_DIR = Path("backend/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("vimeo_chatbot")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_DIR / "chatbot.log")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

def safe_get(d, key, default=None):
    return d.get(key, default) if isinstance(d, dict) else default










# if __name__ == "__main__":
#     print("🔍 Testing utils.py ...")

#     # Test logging
#     logger.info("This is a test log entry.")
#     logger.warning("This is a warning log entry.")
#     print("✅ Log entries written to backend/logs/chatbot.log")

#     # Test safe_get()
#     d = {"name": "Chatbot", "type": "RAG"}
#     print("safe_get existing key:", safe_get(d, "name", "N/A"))
#     print("safe_get missing key:", safe_get(d, "version", "unknown"))
