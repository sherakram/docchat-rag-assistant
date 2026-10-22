from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Chat with Your Documents")


@app.get("/api/health")
def health():
    """Chhota sa check: kya server zinda hai?"""
    return {"status": "ok"}

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")