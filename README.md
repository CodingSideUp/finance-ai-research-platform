# Finance AI Research Platform

A cloud-first(GCP) AI engineering platform for large-scale financial research using SEC filings.

The platform ingests SEC 10-K and 10-Q filings, stores immutable source documents in Google Cloud Storage, processes and validates heterogeneous SEC HTML, and prepares retrieval-ready chunks for hybrid search, embeddings, and agentic financial research.

---

## Architecture

```text
SEC EDGAR
    ↓
SEC Ingestion Pipeline
    ↓
GCS RAW
    ↓
Parser → Normalizer → Validator → Chunker
    ↓
GCS PROCESSED
    ↓
Vertex AI Embeddings
    ↓
Weaviate Hybrid Search
    ↓
LangGraph Research Agents
    ↓
FastAPI
    ↓
React UI