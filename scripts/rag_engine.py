"""
Authentic RAG Baseline Engine
Implements document ingestion, semantic chunking, TF-IDF vectorization,
cosine similarity retrieval, and RAG prompt synthesis over genuine coastal documents.
"""

import os
import sys
import glob
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from chatbot import call_nvidia_llm

CORPUS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "rag_corpus"))


class CoastalDocumentChunk:
    def __init__(self, text: str, source_file: str, title: str, published_date: str, section: str):
        self.text = text.strip()
        self.source_file = source_file
        self.title = title
        self.published_date = published_date
        self.section = section

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source_file": self.source_file,
            "title": self.title,
            "published_date": self.published_date,
            "section": self.section,
        }


class CoastalRAGEngine:
    def __init__(self, corpus_dir: str = CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self.chunks: List[CoastalDocumentChunk] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.embed_model = None
        self.dense_embeddings = None
        self.cache_path = os.path.join(self.corpus_dir, "corpus_embeddings_minilm.npz")
        self.build_index()

    def build_index(self):
        """Loads text documents from corpus directory, splits into semantic sections, and builds both Sparse (TF-IDF) and Dense (all-MiniLM-L6-v2) indices."""
        self.chunks = []
        files = glob.glob(os.path.join(self.corpus_dir, "*.txt"))
        if not files:
            raise FileNotFoundError(f"No corpus files found in {self.corpus_dir}")

        for filepath in files:
            filename = os.path.basename(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.splitlines()
            title = lines[0].strip() if lines else filename
            published_date = "2023-01-01"
            for line in lines[:10]:
                if line.startswith("Published Date:"):
                    published_date = line.split(":", 1)[1].strip()

            # Split by numbered sections or double newlines
            raw_sections = content.split("\n\n")
            current_section_title = "General Information"

            for sec in raw_sections:
                sec_text = sec.strip()
                if not sec_text:
                    continue
                first_line = sec_text.splitlines()[0].strip()
                if first_line.startswith(("1.", "2.", "3.", "4.", "5.")):
                    current_section_title = first_line

                self.chunks.append(
                    CoastalDocumentChunk(
                        text=sec_text,
                        source_file=filename,
                        title=title,
                        published_date=published_date,
                        section=current_section_title,
                    )
                )

        chunk_texts = [f"{c.title} {c.section} {c.text}" for c in self.chunks]

        # 1. Sparse TF-IDF Vectorizer
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.tfidf_matrix = self.vectorizer.fit_transform(chunk_texts)

        # 2. Dense Embeddings (SentenceTransformer: all-MiniLM-L6-v2) with disk caching
        try:
            from sentence_transformers import SentenceTransformer
            self.embed_model = SentenceTransformer("all-MiniLM-L6-v2")

            if os.path.exists(self.cache_path):
                try:
                    loaded = np.load(self.cache_path)
                    if "embeddings" in loaded and loaded["embeddings"].shape[0] == len(self.chunks):
                        self.dense_embeddings = loaded["embeddings"]
                except Exception:
                    self.dense_embeddings = None

            if self.dense_embeddings is None:
                self.dense_embeddings = self.embed_model.encode(chunk_texts, show_progress_bar=False)
                np.savez_compressed(self.cache_path, embeddings=self.dense_embeddings)
        except Exception as e:
            # Fallback to sparse if sentence-transformers fails
            self.embed_model = None
            self.dense_embeddings = None

    def retrieve_sparse(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """TF-IDF Term-Overlap Cosine Similarity Retrieval."""
        if not self.chunks or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        q_lower = query.lower()
        for i, chunk in enumerate(self.chunks):
            chunk_content = (chunk.title + " " + chunk.text).lower()
            for city in ["chennai", "mumbai", "kochi", "cochin", "visakhapatnam", "vizag", "kolkata", "sundarbans"]:
                if city in q_lower and city in chunk_content:
                    scores[i] += 0.35

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            {
                "score": float(scores[idx]),
                "text": self.chunks[idx].text,
                "source_file": self.chunks[idx].source_file,
                "title": self.chunks[idx].title,
                "published_date": self.chunks[idx].published_date,
                "section": self.chunks[idx].section,
                "retrieval_method": "sparse_tfidf",
            }
            for idx in top_indices
        ]

    def retrieve_dense(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Dense Vector Embedding Cosine Similarity Retrieval (all-MiniLM-L6-v2)."""
        if self.embed_model is None or self.dense_embeddings is None:
            return self.retrieve_sparse(query, top_k=top_k)

        query_emb = self.embed_model.encode([query])
        scores = cosine_similarity(query_emb, self.dense_embeddings).flatten()

        q_lower = query.lower()
        for i, chunk in enumerate(self.chunks):
            chunk_content = (chunk.title + " " + chunk.text).lower()
            for city in ["chennai", "mumbai", "kochi", "cochin", "visakhapatnam", "vizag", "kolkata", "sundarbans"]:
                if city in q_lower and city in chunk_content:
                    scores[i] += 0.35

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            {
                "score": float(scores[idx]),
                "text": self.chunks[idx].text,
                "source_file": self.chunks[idx].source_file,
                "title": self.chunks[idx].title,
                "published_date": self.chunks[idx].published_date,
                "section": self.chunks[idx].section,
                "retrieval_method": "dense_embedding_minilm",
            }
            for idx in top_indices
        ]

    def retrieve(self, query: str, top_k: int = 3, method: str = "dense") -> List[Dict[str, Any]]:
        """Retrieves top_k passages using specified retrieval method ('dense' or 'sparse')."""
        if method == "dense" and self.dense_embeddings is not None:
            return self.retrieve_dense(query, top_k=top_k)
        return self.retrieve_sparse(query, top_k=top_k)

    def query_rag(
        self,
        question: str,
        top_k: int = 3,
        method: str = "dense",
        model: Optional[str] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Executes standard RAG pipeline:
        1. Retrieves relevant corpus chunks via specified method ('dense' or 'sparse')
        2. Injects chunks into standard RAG prompt
        3. Invokes LLM
        4. Calculates document staleness
        """
        retrieved = self.retrieve(question, top_k=top_k, method=method)

        context_blocks = []
        earliest_date = "9999-99-99"
        latest_date = "0000-00-00"

        for i, r in enumerate(retrieved, 1):
            context_blocks.append(
                f"[Document Passage {i}]\n"
                f"Source: {r['title']} ({r['source_file']})\n"
                f"Published Date: {r['published_date']}\n"
                f"Section: {r['section']}\n"
                f"Content:\n{r['text']}"
            )
            pub_date = r["published_date"]
            if pub_date < earliest_date:
                earliest_date = pub_date
            if pub_date > latest_date:
                latest_date = pub_date

        context_str = "\n\n---\n\n".join(context_blocks)

        system_prompt = (
            "You are an environmental conditions assistant. Use ONLY the retrieved reference documents "
            "provided below to answer the user's question. If the documents do not cover current conditions, "
            "synthesize your answer directly from the documented facts and figures available in the reference text."
        )

        user_prompt = (
            f"RETRIEVED REFERENCE DOCUMENTS FROM REPOSITORY:\n"
            f"```text\n{context_str}\n```\n\n"
            f"User Question: {question}\n\n"
            f"Answer the question with specific details (temperatures, wind speeds, wave heights, PM2.5, safety advice) "
            f"using the provided reference documentation."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        answer = call_nvidia_llm(messages, model=model, retries_per_model=retries)

        # Calculate staleness gap in days relative to current time
        try:
            today = datetime.now(timezone.utc)
            doc_dt = datetime.strptime(latest_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            staleness_days = max(0, (today - doc_dt).days)
        except Exception:
            staleness_days = 365

        arch_label = "Dense Embedding RAG (all-MiniLM-L6-v2)" if method == "dense" else "Sparse RAG (TF-IDF)"
        return {
            "question": question,
            "answer": answer,
            "retrieved_chunks": retrieved,
            "earliest_doc_date": earliest_date,
            "latest_doc_date": latest_date,
            "staleness_days": staleness_days,
            "retrieval_method": method,
            "architecture": arch_label,
        }


# Global singleton instance for easy import
rag_engine = CoastalRAGEngine()


if __name__ == "__main__":
    q = "Is it safe to fish near Chennai right now?"
    print(f"Testing RAG retrieval for: '{q}'\n")
    res = rag_engine.query_rag(q, top_k=2)
    print("Retrieved Passages:", len(res["retrieved_chunks"]))
    print(f"Latest Document Date: {res['latest_doc_date']} (Staleness: {res['staleness_days']} days)")
    print("\n--- RAG Generated Answer ---")
    print(res["answer"])
