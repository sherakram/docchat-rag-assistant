import sys
import time

from google import genai
from google.genai import types

from backend.config import GEMINI_API_KEY, GEMINI_CHAT_MODEL

model = sys.argv[1] if len(sys.argv) > 1 else GEMINI_CHAT_MODEL
# timeout milliseconds mein hai (30000 = 30 second)
client = genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=30000))

start = time.time()
try:
    response = client.models.generate_content(
        model=model, contents="Reply with the single word: pong"
    )
    print("model:", model, "| seconds:", round(time.time() - start, 1))
    print("reply:", response.text)
except Exception as exc:
    print("FAILED after", round(time.time() - start, 1), "s:", type(exc).__name__, str(exc)[:200])