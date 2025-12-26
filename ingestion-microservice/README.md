# Ingestion Service

The **Ingestion Service** is responsible for processing raw documents (PDFs, TXTs), splitting them into chunks, generating embeddings via Ollama, and storing them in a ChromaDB vector database. This enables efficient semantic search and retrieval in the RAG system.

---

## Features
- Extracts text from PDFs and TXTs.
- Splits text into overlapping chunks for better retrieval.
- Generates stable IDs via hashing for deduplication.
- Uses Ollama embeddings for vectorization.
- Stores vectors and metadata in ChromaDB (idempotent upserts).
- Configurable via environment variables.

---

## Project Structure
```
ingestion_service/
├── config.py              # Configuration (paths, models, env vars)
├── embeddings.py          # Embedding logic (Ollama + L2 normalization)
├── scripts/
│   ├── ingest.py          # Main ingestion pipeline
│   └── utils.py           # Helpers for PDF text extraction, chunking, hashing
├── requirements.txt       # Python dependencies
├── Dockerfile             # Containerization (optional)
└── ingestion_notes.txt    # Local notes (ignored by git)
```

---

## Environment Variables (`.env`)
```env
# Embedding model
EMB_MODEL=nomic-embed-text
OLLAMA_HOST=http://127.0.0.1:11434

# ChromaDB
CHROMA_PATH=../data/chroma_db
CHROMA_COLLECTION_NAME=rag_docs
CHROMA_DISTANCE=cosine

# Chunking
CHARS_PER_TOKEN=4.0
CHUNK_TOKENS=800
CHUNK_OVERLAP_TOKENS=140
HASH_ALGO=xxh3
INGEST_BATCH_SIZE=128

# Logging
LOG_LEVEL=INFO
```

---

## Installation
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Usage
Run the ingestion pipeline with:

```bash
# Standard ingest
python3 -m scripts.ingest

# Rebuild collection (drop & recreate)
python3 -m scripts.ingest --rebuild

# Purge database directory and start fresh
python3 -m scripts.ingest --purge

# Change batch size
python3 -m scripts.ingest --batch 256
```

---

## Output Example
```
ingest_done files=2 chunks=2 added=2 skipped=0 secs=5.94
```

This means:
- 2 files processed
- 2 chunks created
- 2 new chunks added
- 0 duplicates skipped
- Process completed in 5.94 seconds
