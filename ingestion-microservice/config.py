import os
from pathlib import Path
from dotenv import load_dotenv

# Load env file once, at import time
load_dotenv()

# ---- ROOT & DATA PATHS ----
PROJECT_ROOT = Path(__file__).resolve().parent
# RAW_DATA_DIR = (PROJECT_ROOT / os.getenv("RAW_DATA_DIR", "data/raw")).resolve()
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "../data/raw"))
RAW_PDFS = RAW_DATA_DIR / "pdfs"
RAW_TXTS = RAW_DATA_DIR / "txts"

# ---- MODEL FOR EMBEDDING ----
EMB_MODEL = os.getenv("EMB_MODEL", "nomic-embed-text")

# ---- VDB ----
# CHROMA_PATH  = (PROJECT_ROOT / os.getenv("CHROMA_PATH", "data/chroma_db")).resolve()
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", "../data/chroma_db"))
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "rag_docs")
CHROMA_DISTANCE = os.getenv("CHROMA_DISTANCE", "cosine")

# ---- DATA INGESTION PIPELINE ----
CHARS_PER_TOKEN = float(os.getenv("CHARS_PER_TOKEN", "4.0")) 
CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", "800"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "140"))
CHUNK_CHARS = int(CHUNK_TOKENS * CHARS_PER_TOKEN)
CHUNK_OVERLAP_CHARS = int(CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN)
HASH_ALGO = os.getenv("HASH_ALGO", "xxh3")
INGEST_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "128"))

# ---- LOGGING ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ingestion_service/config.py
DOCUMENT_API_URL = os.getenv("DOCUMENT_API_URL", "https://api.company.com/documents")
API_KEY = os.getenv("DOCUMENT_API_KEY")

# ---- OLLAMA ----
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
