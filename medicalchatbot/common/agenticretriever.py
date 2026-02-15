from qdrant_client import models
from flashrank import Ranker, RerankRequest
from medicalchatbot.common.vectorstore import get_qdrant_client
from medicalchatbot.knowledge_graph.graph_engine import MedicalGraphEngine # NEW IMPORT

class MedicalAgentRetriever:
    def __init__(self, llm_model, dense_model, sparse_model):
        self.llm = llm_model
        self.dense_model = dense_model
        self.sparse_model = sparse_model
        self.client = get_qdrant_client("cpg_docs") # Get base client
        self.ranker = Ranker()
        self.kg_engine = MedicalGraphEngine()

# trialcpg/agentic_retriever.py

    def _route_query(self, query: str) -> str:
        """Determines target collections using the official Ollama library."""
        prompt = f"""Identify the medical intent: "{query}"
        - If it's about treatment/dosage/clinical management: Reply 'CPG'
        - If it's about anatomy/physiology/theoretical explanation: Reply 'TEXTBOOK'
        - If it's complex or needs both: Reply 'BOTH'
        Reply with ONLY the word."""
        
        response = self.llm.chat(
            model='llama3.2:3b',
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        # 1. ACCESS FIX: Try the dict key first, then object attribute
        try:
            # Most versions of the ollama-python library use this:
            decision = response['message']['content'].strip().upper()
        except (TypeError, KeyError):
            # Fallback for newer object-based responses
            decision = response.message.content.strip().upper()
            
        # 2. ROBUSTNESS: Simple keyword check
        if "CPG" in decision: return "CPG"
        if "TEXTBOOK" in decision: return "TEXTBOOK"
        return "BOTH"

    def _hybrid_retrieve(self, collection_name: str, query: str, limit: int = 10):
        """Your existing hybrid retrieval logic, modularized."""
        # Embeddings
        query_dense = list(self.dense_model.embed([query]))[0].tolist()
        query_sparse_raw = list(self.sparse_model.embed([query]))[0]
        query_sparse = models.SparseVector(
            indices=query_sparse_raw.indices.tolist(),
            values=query_sparse_raw.values.tolist()
        )

        # Search
        response = self.client.query_points(
            collection_name=collection_name,
            prefetch=[
                models.Prefetch(query=query_dense, using="dense", limit=limit),
                models.Prefetch(query=query_sparse, using="sparse", limit=limit),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit * 2
        )
        return response.points

    def run(self, query: str, top_k: int = 3):
        # 1. PHARMACOPOEIA CHECK (Knowledge Graph)
        kg_alerts = self.kg_engine.get_pharmacopoeia_alerts(query)
        kg_context = "\n".join(kg_alerts) if kg_alerts else "No direct KG contradictions found."

        # 2. Existing Routing & Retrieval
        intent = self._route_query(query)
        collections = ["cpg_docs", "textbook_docs"] if intent == "BOTH" else \
                      (["cpg_docs"] if intent == "CPG" else ["textbook_docs"])

        # 2. Retrieval from target collections
        all_passages = []
        for coll in collections:
            points = self._hybrid_retrieve(coll, query)
            for p in points:
                all_passages.append({
                    "id": p.id,
                    "text": p.payload.get("document", ""),
                    "metadata": p.payload
                })

        # 3. Reranking
        rerank_req = RerankRequest(query=query, passages=all_passages)
        results = self.ranker.rerank(rerank_req)

        # 4. Formatted Output (Enforcing your specific citation rules)
        hits = [f"🛡️ PHARMACOPOEIA RULES:\n{kg_context}\n"]
        for res in results[:top_k]:
            meta = res["metadata"]
            source = meta.get("source", "Unknown")
            
            if meta.get("type") == "cpg":
                # Rule: Page numbers only for CPG
                page = meta.get("page", "N/A")
                header = f"📍 [CLINICAL GUIDELINE] {source} (Page {page})"
            else:
                # Rule: Source title only for Textbooks
                header = f"📖 {source}"
            
            hits.append(f"{header}\n{res['text']}")
            
        return "\n\n---\n\n".join(hits)