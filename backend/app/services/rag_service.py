import os
import traceback
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

QDRANT_HOST = os.getenv("QDRANT_URL", "http://vector_db:6333")
COLLECTION_NAME = "clinical_guidelines"

_client: Optional[QdrantClient] = None
_embedding_model = None


def get_qdrant_client():
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_HOST, timeout=10)
    return _client


class EmbeddingModelWrapper:
    """Flexible embedding wrapper supporting SentenceTransformers, OpenAI, or fastembed as fallbacks.
    Provides a single `embed(texts: List[str]) -> List[List[float]]` method.
    """
    def __init__(self):
        import os
        self.backend = "dummy"
        self.model = None
        self.dim = 384
        # Prefer local SentenceTransformers model
        try:
            from sentence_transformers import SentenceTransformer
            model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
            print(f"[Embeddings] Loading SentenceTransformers model: {model_name}")
            self.model = SentenceTransformer(model_name)
            self.backend = "sbert"
            # many SBERT models (all-MiniLM-L6-v2) output 384-d
            self.dim = getattr(self.model, 'get_sentence_embedding_dimension', lambda: 384)()
        except Exception:
            # Optionally allow OpenAI only when explicitly enabled via env var USE_OPENAI=true
            try:
                if os.getenv("USE_OPENAI", "false").lower() == "true":
                    import openai
                    api_key = os.getenv("OPENAI_API_KEY")
                    if api_key:
                        openai.api_key = api_key
                        self.backend = "openai"
                        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
                        print(f"[Embeddings] Using OpenAI Embeddings: {self.model} (enabled by USE_OPENAI=true)")
                    else:
                        raise Exception("USE_OPENAI is true but OPENAI_API_KEY is not set")
                else:
                    raise Exception("OpenAI disabled by USE_OPENAI env var")
            except Exception:
                # Fallback to fastembed if available
                try:
                    from fastembed import TextEmbedding
                    print("[Embeddings] Loading FastEmbed BAAI/bge-small-en-v1.5 as fallback...")
                    self.model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                    self.backend = "fastembed"
                    # fastembed models may return numpy arrays with .shape[-1]
                    try:
                        sample = list(self.model.embed(["test"]))[0]
                        self.dim = len(sample)
                    except Exception:
                        self.dim = 1536
                except Exception:
                    print("[Embeddings] No embedding backend available; using dummy vectors.")
                    self.backend = "dummy"
                    self.dim = 384

    def embed(self, texts):
        # Accepts list[str] and returns list[list[float]]
        if not texts:
            return []
        if self.backend == "sbert":
            embs = self.model.encode(texts, show_progress_bar=False)
            # ensure python lists of floats
            return [list(map(float, e)) for e in embs]
        elif self.backend == "openai":
            import openai
            # OpenAI can accept list of texts
            resp = openai.Embedding.create(model=self.model, input=texts)
            return [d["embedding"] for d in resp["data"]]
        elif self.backend == "fastembed":
            embs = list(self.model.embed(texts))
            return [list(map(float, e)) for e in embs]
        else:
            # Dummy deterministic vector for reproducibility
            return [[0.01 * ((i + 1) % 10) for i in range(self.dim)] for _ in texts]


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModelWrapper()
    return _embedding_model


SAMPLE_GUIDELINES = [
    {
        "id": 1,
        "title": "ACR Appropriateness Criteria: Acute Chest Pain - Suspected Pulmonary Embolism",
        "source": "American College of Radiology (ACR)",
        "content": "For patients presenting with acute chest pain, dyspnea, and elevated D-Dimer levels, CT Pulmonary Angiography (CTPA) is the initial imaging procedure of choice. Chest radiographs are recommended as an initial complementary examination.",
        "category": "Cardiothoracic"
    },
    {
        "id": 2,
        "title": "ACC/AHA Guidelines for Evaluation of Acute Chest Pain",
        "source": "American College of Cardiology / AHA",
        "content": "In intermediate-high risk patients with chest pain and elevated biomarkers, early coronary CT angiography or invasive coronary angiography should be considered. Serial high-sensitivity troponin testing is required.",
        "category": "Cardiology"
    },
    {
        "id": 3,
        "title": "ACR Appropriateness Criteria: Head Trauma & Stroke",
        "source": "American College of Radiology (ACR)",
        "content": "Non-contrast CT of the head is the standard initial imaging modality for acute head trauma, focal neurological deficits, or suspected intracranial hemorrhage within 3 hours of symptom onset.",
        "category": "Neuroradiology"
    },
    {
        "id": 4,
        "title": "GOLD Guidelines for Acute Exacerbation of COPD",
        "source": "Global Initiative for Chronic Obstructive Lung Disease",
        "content": "Patients presenting with dyspnea, increased sputum volume, and room air O2 saturation < 92% should receive supplemental oxygen target 88-92%, bronchodilator therapy, and evaluation for systemic corticosteroids.",
        "category": "Pulmonology"
    }
]


def init_qdrant_guidelines():
    """Initializes vector collection and seeds reference guidelines if collection is empty."""
    try:
        client = get_qdrant_client()
        collections = [c.name for c in client.get_collections().collections]

        if COLLECTION_NAME not in collections:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print(f"[Qdrant] Created collection '{COLLECTION_NAME}'")

        collection_info = client.get_collection(COLLECTION_NAME)
        if collection_info.points_count == 0:
            print("[Qdrant] Seeding clinical guidelines into vector database...")
            model = get_embedding_model()
            texts = [g["content"] for g in SAMPLE_GUIDELINES]
            embeddings = model.embed(texts)

            points = []
            for doc, emb in zip(SAMPLE_GUIDELINES, embeddings):
                # emb is expected as list[float]
                points.append(
                    PointStruct(
                        id=doc["id"],
                        vector=list(map(float, emb)),
                        payload={
                            "title": doc["title"],
                            "source": doc["source"],
                            "content": doc["content"],
                            "category": doc["category"]
                        }
                    )
                )
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"[Qdrant] Successfully indexed {len(points)} guidelines.")
    except Exception as e:
        print(f"[Qdrant Init Warning]: {str(e)}")


def query_clinical_guidelines(query_text: str, top_k: int = 3, allowed_sources: list = None):
    """Encodes query text and performs cosine similarity search against Qdrant."""
    try:
        client = get_qdrant_client()
        model = get_embedding_model()

        print(f"\n--- [RAG SEARCH QUERY Context] ---\n{query_text[:150]}...\n---------------------------------")

        # Generate embedding
        embeddings = model.embed([query_text])
        if not embeddings:
            print("[RAG Warning]: Empty embedding returned from model.")
            return []

        query_vector = list(map(float, embeddings[0]))

        # Build optional Qdrant filter for allowed sources (OR semantics via 'should')
        q_filter = None
        try:
            if allowed_sources:
                should_conditions = [
                    FieldCondition(key="source", match=MatchValue(value=src)) for src in allowed_sources
                ]
                q_filter = Filter(should=should_conditions)
        except Exception as fe:
            print(f"[RAG Filter Warning]: Could not build filter: {fe}")
            q_filter = None

        # Query Qdrant
        search_results = []
        if hasattr(client, "search"):
            # use query_filter if supported
            if q_filter is not None:
                search_results = client.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=query_vector,
                    limit=top_k,
                    query_filter=q_filter
                )
            else:
                search_results = client.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=query_vector,
                    limit=top_k
                )
        elif hasattr(client, "query_points"):
            # older API path
            if q_filter is not None:
                res = client.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=query_vector,
                    limit=top_k,
                    query_filter=q_filter
                )
                search_results = res
            else:
                res = client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=query_vector,
                    limit=top_k
                )
                search_results = res.points

        print(f"[RAG SUCCESS]: Qdrant returned {len(search_results)} results.")

        guidelines = []
        for result in search_results:
            payload = getattr(result, "payload", {}) or {}
            score = getattr(result, "score", 0.0)
            guidelines.append({
                "score": round(score * 100, 1),
                "title": payload.get("title", "Clinical Practice Guideline"),
                "source": payload.get("source", "Medical Reference"),
                "content": payload.get("content", ""),
                "category": payload.get("category", "General")
            })
        return guidelines

    except Exception as e:
        print(f"[Qdrant Search Exception]: {str(e)}")
        traceback.print_exc()
        return []