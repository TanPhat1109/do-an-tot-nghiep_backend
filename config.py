
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Thiếu biến môi trường {name}. "
            "Hãy copy .env.example thành .env và điền giá trị."
        )
    return value


SECRET_KEY = _require("SECRET_KEY")
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24))
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:@localhost:3306/da_ai?charset=utf8mb4",
)

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:57331"
    ).split(",")
    if o.strip()
]

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    ""
)
OPENROUTER_MODEL = "openrouter/free"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

GEMINI_EMBEDDING_API_KEY = os.getenv(
    ""
)
# ==============================
# SCHOOL CONFIGURATION
# ==============================

SCHOOL_NAME = os.getenv(
    "SCHOOL_NAME",
    "Trường Cao đẳng Kỹ thuật Cao Thắng"
)

SCHOOL_WEBSITE = os.getenv(
    "SCHOOL_WEBSITE",
    "https://caothang.edu.vn/"
)
