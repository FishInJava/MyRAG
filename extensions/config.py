"""
MyRAG Config — 配置加载

从环境变量和默认值加载配置。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ─── 项目根目录 ────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─── 目录配置 ──────────────────────────────────────────────────────

NEWDATA_DIR = PROJECT_ROOT / "newData"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"
MYOBSIDIAN_DIR = PROJECT_ROOT / "myObsidian"
TEMPLATES_DIR = PROJECT_ROOT / "template"
PROCESSED_LOG = NEWDATA_DIR / ".processed"
CHROMA_DB_PATH = PROJECT_ROOT / "chroma"

# ─── LLM 配置 ──────────────────────────────────────────────────────

load_dotenv()

LLM_PROVIDER = os.getenv("MYRAG_LLM_PROVIDER", "anthropic")
LLM_MODEL = os.getenv("MYRAG_LLM_MODEL", "claude-sonnet-4-20250514")
LLM_API_KEY = os.getenv(f"{LLM_PROVIDER.upper()}_API_KEY", "")

# ─── Embedding 配置 ────────────────────────────────────────────────

EMBEDDING_PROVIDER = os.getenv("MYRAG_EMBEDDING_PROVIDER", "openai")
EMBEDDING_MODEL = os.getenv("MYRAG_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_API_KEY = os.getenv(f"{EMBEDDING_PROVIDER.upper()}_API_KEY", "")

# ─── 处理配置 ──────────────────────────────────────────────────────

MAX_RETRIES = int(os.getenv("MYRAG_MAX_RETRIES", "1"))
SIMILARITY_THRESHOLD = float(os.getenv("MYRAG_SIMILARITY_THRESHOLD", "0.8"))
TOP_K = int(os.getenv("MYRAG_TOP_K", "5"))

# ─── 验证 ──────────────────────────────────────────────────────────

def validate_config() -> list[str]:
    """验证配置是否完整，返回错误列表"""
    errors = []
    if not LLM_API_KEY:
        errors.append(f"Missing {LLM_PROVIDER.upper()}_API_KEY environment variable")
    if not EMBEDDING_API_KEY:
        errors.append(f"Missing {EMBEDDING_PROVIDER.upper()}_API_KEY environment variable")
    if not NEWDATA_DIR.exists():
        errors.append(f"newData directory not found: {NEWDATA_DIR}")
    return errors
