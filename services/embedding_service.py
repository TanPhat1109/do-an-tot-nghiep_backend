
import os
import time
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

# Số lần gọi tối đa: 2 (lần đầu + 1 lần thử lại)
MAX_RETRIES = 1

# Timeout kết nối 5 giây, chờ phản hồi tối đa 20 giây
TIMEOUT = (5, 20)


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

    for attempt in range(MAX_RETRIES + 1):
        try:
            start_time = time.perf_counter()

            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=TIMEOUT
            )

            response.raise_for_status()

            result = response.json()
            embedding = result["data"][0]["embedding"]

            elapsed = time.perf_counter() - start_time
            print(f"Jina Embedding: {elapsed:.2f} giây")

            return embedding

        except (requests.Timeout, requests.ConnectionError) as e:
            print(
                f"Jina kết nối thất bại "
                f"(lần {attempt + 1}/{MAX_RETRIES + 1}): {e}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(1)
                continue

            raise RuntimeError(
                "Jina AI không phản hồi. Vui lòng thử lại sau."
            ) from e

        except requests.HTTPError as e:
            print("Jina API HTTP error:", e.response.status_code)
            print(e.response.text)
            raise RuntimeError("Jina API trả về lỗi") from e

        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise RuntimeError(
                "Dữ liệu embedding Jina trả về không hợp lệ"
            ) from e


def embed_passage(text: str) -> list[float]:
    return embed_text(text, "retrieval.passage")


def embed_query(text: str) -> list[float]:
    return embed_text(text, "retrieval.query")
