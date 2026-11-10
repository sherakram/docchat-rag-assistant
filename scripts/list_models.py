from google import genai

from backend.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or []
    if "generateContent" in actions:
        print(model.name)