
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

JINA_API_KEY = os.getenv("JINA_API_KEY")

if not JINA_API_KEY:
    raise ValueError("Chưa cấu hình JINA_API_KEY")

API_URL = "https://api.jina.ai/v1/embeddings"
MODEL = "jina-embeddings-v5-text-small"


def embed_text(text: str, task: str = "retrieval.passage") -> list[float]:
    if not text or not text.strip():
        raise ValueError("Văn bản không được để trống")

    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "input": [text],
        "task": task,
        "normalized": True
    }

    response = requests.post(
        API_URL,
        headers=headers,
        json=payload,
        timeout=90
    )

    if response.status_code != 200:
        print("Jina API error:", response.status_code)
        print(response.text)
        raise RuntimeError("Không thể tạo embedding")

    result = response.json()
    return result["data"][0]["embedding"]


def embed_passage(text: str) -> list[float]:
    return embed_text(text, "retrieval.passage")


def embed_query(text: str) -> list[float]:
    return embed_text(text, "retrieval.query")
