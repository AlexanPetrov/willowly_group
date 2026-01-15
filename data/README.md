# Data Directory

Shared data storage for the Willowly Group microservices platform. Contains vector embeddings, raw documents, and ingestion metadata.

## Structure

```
data/
├── chroma_db/              # Persistent vector database (ChromaDB)
│   ├── chroma.sqlite3      # SQLite backend for embeddings and metadata
│   └── [UUID folders]/     # Document collection data
├── raw/                    # Raw source documents (not version controlled)
│   ├── pdfs/               # PDF documents for ingestion
│   └── txts/               # Plain text documents for ingestion
├── logs/                   # Ingestion operation logs
├── ingestion_log.json      # Metadata: processed files, timestamps, status
└── .gitignore              # Excludes large files from version control
```

## Usage

### Adding Documents
Place raw documents in `raw/pdfs/` or `raw/txts/`. The ingestion-microservice will process them automatically.

```bash
# Run ingestion pipeline
python3 -m scripts.ingest

# Rebuild vector database (clear old embeddings)
python3 -m scripts.ingest --rebuild

# Clear all data and rebuild
python3 -m scripts.ingest --purge
```

### Accessing Vectors
The RAG microservice reads from ChromaDB automatically. Vector embeddings are used for semantic search and document retrieval.

## Notes

- **ChromaDB** is persistent and survives container restarts via volume mounts
- **Raw documents** are excluded from version control (see `.gitignore`)
- **Ingestion metadata** (`ingestion_log.json`) tracks which documents were processed and when
- All services use the shared path `/data/chroma_db` for consistency

## Security

Sensitive data (embeddings, documents) is stored locally and not committed to version control.
