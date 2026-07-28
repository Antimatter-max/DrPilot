This draft PR summarizes the applied backend changes to enable local SentenceTransformers embeddings and source-restricted RAG querying.

What was changed (code already present in 'main'):

- backend/app/services/rag_service.py
  - Added an EmbeddingModelWrapper earlier (supports SBERT, OpenAI, fastembed) and ensured SBERT is preferred when available.
  - Added allowed_sources support to query_clinical_guidelines (builds a Qdrant Filter to restrict results by payload.source).

- backend/app/api/v1/governance.py
  - Ingestion now calls the embedding model to generate vectors for PDF chunks and upserts to Qdrant.

- backend/app/services/vlm_service.py
  - If VLM_API_URL is set, the VLM API will be called with a PNG rendering; otherwise the code falls back to a local heuristic analyzer.

- backend/app/services/chat_service.py
  - process_patient_chat now accepts allowed_sources and passes them to RAG queries.

- backend/app/api/v1/patient.py
  - ChatRequest schema extended with `allowed_sources: Optional[List[str]]`.
  - patient chat endpoint forwards allowed_sources to the backend.
  - guideline-recommendations endpoint accepts `sources` query param (comma-separated) and restricts RAG queries accordingly.

- backend/requirements.txt
  - Added sentence-transformers to enable local SBERT.

Notes for reviewers / testers:
- The code changes have already been committed to the repository's 'main' branch. This PR adds this summary so a draft PR can be opened for discussion and review.
- To fully enable local SBERT, install sentence-transformers (and its dependencies such as torch) in the backend environment or Docker image.
- Ensure Qdrant collection vector size matches the SBERT model (default all-MiniLM-L6-v2 -> 384 dims).

How to test (short):
1. Install dependencies and set up Qdrant.
2. Start backend and ingest a PDF via /api/v1/governance/ingest/mass-upload.
3. Call /api/v1/patients/{uid}/chat with a JSON body including `allowed_sources` to restrict RAG results.

If you'd like, I can convert these applied changes into a fully-diffed PR (i.e., move the code to a feature branch and open a PR that contains the code diffs). That would require adjusting which branch currently contains the commits. Let me know if you want that and I'll proceed.
