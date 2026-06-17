import os
import re
import math
import json
from sentence_transformers import SentenceTransformer
from snowballstemmer import stemmer

def tokenize_and_stem(text: str) -> list[str]:
    """
    Cleans punctuation, lowercases, and stems tokens using English and Swedish stemmers.
    Matches words on word boundaries and stems consistently for bilingual search.
    """
    if not hasattr(tokenize_and_stem, "_en_stemmer"):
        tokenize_and_stem._en_stemmer = stemmer('english')
        tokenize_and_stem._sv_stemmer = stemmer('swedish')
    
    # Extract alphanumeric words (strips punctuation)
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Stem each word using both Swedish and English stemmers
    stemmed_words = []
    for w in words:
        stemmed_words.append(
            tokenize_and_stem._en_stemmer.stemWord(
                tokenize_and_stem._sv_stemmer.stemWord(w)
            )
        )
    return stemmed_words


class CustomBM25Vectorizer:
    """
    Manages custom bilingual vocabulary mapping, IDF tracking, and
    calculates document and query sparse vectors compatible with Qdrant.
    """
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.vocab = {}      # term -> unique integer ID
        self.idf = {}        # term -> IDF weight
        self.avgdl = 0.0
        
    def fit(self, tokenized_corpus: list[list[str]]):
        """Builds vocabulary, calculates term IDFs, and finds average document length."""
        if not tokenized_corpus:
            self.vocab = {}
            self.idf = {}
            self.avgdl = 0.0
            return
            
        doc_freqs = {}
        total_len = 0
        for doc in tokenized_corpus:
            total_len += len(doc)
            unique_terms = set(doc)
            for term in unique_terms:
                doc_freqs[term] = doc_freqs.get(term, 0) + 1
                
        self.avgdl = total_len / len(tokenized_corpus)
        
        # Build deterministic vocab mapping sorted by term
        self.vocab = {term: idx for idx, term in enumerate(sorted(doc_freqs.keys()))}
        
        N = len(tokenized_corpus)
        # Standard rank-bm25 BM25Okapi IDF formula
        for term, freq in doc_freqs.items():
            self.idf[term] = math.log(1.0 + (N - freq + 0.5) / (freq + 0.5))
            
    def get_document_sparse_vector(self, tokenized_doc: list[str]) -> tuple[list[int], list[float]]:
        """
        Computes the sparse vector representing a document chunk.
        Value for term t = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len / avgdl))
        """
        if not tokenized_doc or not self.vocab:
            return [], []
            
        doc_len = len(tokenized_doc)
        term_counts = {}
        for term in tokenized_doc:
            if term in self.vocab:
                term_counts[term] = term_counts.get(term, 0) + 1
                
        indices = []
        values = []
        
        sorted_terms = sorted(term_counts.keys(), key=lambda t: self.vocab[t])
        
        for term in sorted_terms:
            idx = self.vocab[term]
            tf = term_counts[term]
            denominator = tf + self.k1 * (1.0 - self.b + self.b * doc_len / self.avgdl)
            weight = (tf * (self.k1 + 1.0)) / denominator
            
            indices.append(idx)
            values.append(float(weight))
            
        return indices, values

    def get_query_sparse_vector(self, tokenized_query: list[str]) -> tuple[list[int], list[float]]:
        """
        Computes the sparse vector representing a search query.
        Value for term t = IDF(t) * query_tf.
        """
        if not tokenized_query or not self.vocab:
            return [], []
            
        term_counts = {}
        for term in tokenized_query:
            if term in self.vocab:
                term_counts[term] = term_counts.get(term, 0) + 1
                
        indices = []
        values = []
        
        sorted_terms = sorted(term_counts.keys(), key=lambda t: self.vocab[t])
        
        for term in sorted_terms:
            idx = self.vocab[term]
            weight = self.idf.get(term, 0.0) * term_counts[term]
            if weight > 0:
                indices.append(idx)
                values.append(float(weight))
                
        return indices, values

    def save(self, filepath: str):
        """Saves vectorizer configuration to a JSON file."""
        state = {
            "k1": self.k1,
            "b": self.b,
            "vocab": self.vocab,
            "idf": self.idf,
            "avgdl": self.avgdl
        }
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load(self, filepath: str):
        """Loads vectorizer configuration from a JSON file."""
        if not os.path.exists(filepath):
            return
        with open(filepath, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.k1 = state["k1"]
        self.b = state["b"]
        self.vocab = state["vocab"]
        self.idf = state["idf"]
        self.avgdl = state["avgdl"]


class QdrantCollectionWrapper:
    """Provides compatibility wrapper for app.py that expects Chroma's collection.count() API."""
    def __init__(self, client, collection_name):
        self.client = client
        self.collection_name = collection_name
        
    def count(self) -> int:
        try:
            count = self.client.get_collection(self.collection_name).points_count
            return count if count is not None else 0
        except Exception:
            return 0


class LocalBilingualRetriever:
    """
    A modular hybrid retriever that combines dense semantic search (E5 vectors via Qdrant)
    and sparse keyword search (BM25) with Reciprocal Rank Fusion (RRF) at the database level.
    Supports English and Swedish natively.
    """
    def __init__(self, db_path="./local_qdrant_db", collection_name="bilingual_rag"):
        """Initializes database, embedding function, and registers runtime state."""
        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams, Distance, SparseVectorParams, SparseIndexParams
        
        self.db_path = db_path
        self.collection_name = collection_name
        self.client = QdrantClient(path=db_path)
        
        # Load local bilingual E5 embedding function
        self.model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
        
        # Setup BM25 vectorizer configuration
        self.bm25_vectorizer = CustomBM25Vectorizer()
        self.bm25_state_path = os.path.join(db_path, "bm25_state.json")
        
        # Verify collection exists with dense and sparse configs
        collection_exists = False
        try:
            self.client.get_collection(collection_name)
            collection_exists = True
        except Exception:
            pass
            
        if not collection_exists:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=384,
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=SparseIndexParams(
                            on_disk=False
                        )
                    )
                }
            )
            
        # UI backward compatibility wrapper
        self.collection = QdrantCollectionWrapper(self.client, collection_name)
        
        # Keyword index tracking variables
        self.indexed_chunks = []
        self.indexed_metadatas = []
        
        # Sync keyword index with existing data if database is already populated
        if os.path.exists(self.bm25_state_path):
            self.bm25_vectorizer.load(self.bm25_state_path)
            
        if not self.is_empty():
            self._sync_local_lists()

    def is_empty(self) -> bool:
        """Returns True if the database contains zero documents."""
        try:
            count = self.client.get_collection(self.collection_name).points_count
            return count is None or count == 0
        except Exception:
            return True

    def _get_all_points(self):
        """Fetches all points from Qdrant using pagination."""
        all_points = []
        offset = None
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=False,
                offset=offset
            )
            all_points.extend(records)
            if offset is None:
                break
        return all_points

    def _sync_local_lists(self):
        """Syncs local in-memory structures from database contents."""
        all_points = self._get_all_points()
        # Sort by point ID to maintain insertion order
        all_points.sort(key=lambda p: p.id if isinstance(p.id, int) else 0)
        
        self.indexed_chunks = [p.payload.get("text", "") for p in all_points if p.payload]
        self.indexed_metadatas = [
            {"source_document": p.payload.get("source_document", "Unknown")}
            for p in all_points if p.payload
        ]

    def _rebuild_keyword_index(self):
        """Fetches all documents from Qdrant, fits the BM25 vectorizer, and updates sparse vectors."""
        all_points = self._get_all_points()
        all_points.sort(key=lambda p: p.id if isinstance(p.id, int) else 0)
        
        self.indexed_chunks = [p.payload.get("text", "") for p in all_points if p.payload]
        self.indexed_metadatas = [
            {"source_document": p.payload.get("source_document", "Unknown")}
            for p in all_points if p.payload
        ]
        
        if not self.indexed_chunks:
            self.bm25_vectorizer = CustomBM25Vectorizer()
            if os.path.exists(self.bm25_state_path):
                try:
                    os.remove(self.bm25_state_path)
                except Exception:
                    pass
            return
            
        # Tokenize documents using bilingual tokenizer and stemmer
        tokenized_corpus = [tokenize_and_stem(doc) for doc in self.indexed_chunks]
        self.bm25_vectorizer.fit(tokenized_corpus)
        self.bm25_vectorizer.save(self.bm25_state_path)
        
        # Generate and update sparse vectors in Qdrant
        from qdrant_client.models import PointVectors, SparseVector
        
        point_vectors = []
        for point, tokenized_doc in zip(all_points, tokenized_corpus):
            indices, values = self.bm25_vectorizer.get_document_sparse_vector(tokenized_doc)
            point_vectors.append(
                PointVectors(
                    id=point.id,
                    vector={
                        "sparse": SparseVector(
                            indices=indices,
                            values=values
                        )
                    }
                )
            )
            
        if point_vectors:
            self.client.update_vectors(
                collection_name=self.collection_name,
                points=point_vectors
            )

    def clear_database(self):
        """Deletes all documents inside the collection to allow a fresh ingest."""
        from qdrant_client.models import Filter
        
        try:
            # Delete all points inside the collection using a match-all filter.
            # This is extremely robust and avoids file locking issues on Windows.
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter()
            )
        except Exception as e:
            print(f"Note: failed to delete points via selector: {e}")
            try:
                self.client.delete_collection(self.collection_name)
                # Recreate the collection
                from qdrant_client.models import VectorParams, Distance, SparseVectorParams, SparseIndexParams
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "dense": VectorParams(
                            size=384,
                            distance=Distance.COSINE
                        )
                    },
                    sparse_vectors_config={
                        "sparse": SparseVectorParams(
                            index=SparseIndexParams(
                                on_disk=False
                            )
                        )
                    }
                )
            except Exception as ex:
                print(f"Error recreating collection: {ex}")
        
        # Clear BM25 state
        if os.path.exists(self.bm25_state_path):
            try:
                os.remove(self.bm25_state_path)
            except Exception:
                pass
                
        self.bm25_vectorizer = CustomBM25Vectorizer()
        self.indexed_chunks = []
        self.indexed_metadatas = []
        print("[clean] Local database collection cleared successfully.")

    def chunk_and_add_document(self, text: str, source_name: str, chunk_size: int = 50, overlap: int = 10):
        """Splits a document into overlapping word-level chunks and saves them in Qdrant."""
        words = text.split()
        chunks = []
        metadatas = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i : i + chunk_size]
            chunk_text = " ".join(chunk_words)
            chunks.append(chunk_text)
            metadatas.append({"source_document": source_name})
            
            if i + chunk_size >= len(words):
                break

        if chunks:
            # E5 model requires documents to be prefixed with "passage: "
            prefixed_docs = [f"passage: {doc}" for doc in chunks]
            embeddings = self.model.encode(prefixed_docs, show_progress_bar=False).tolist()
            
            current_count = self.collection.count()
            ids = [current_count + idx for idx in range(len(chunks))]
            
            from qdrant_client.models import PointStruct
            
            points = []
            for point_id, doc, meta, dense_vector in zip(ids, chunks, metadatas, embeddings):
                points.append(
                    PointStruct(
                        id=point_id,
                        vector={
                            "dense": dense_vector
                        },
                        payload={
                            "text": doc,
                            "source_document": meta["source_document"]
                        }
                    )
                )
                
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            # Print status; keyword index will be rebuilt at the end of ingestion by app.py calling _rebuild_keyword_index()
            print(f"[ingest] Indexed and saved '{source_name}' ({len(chunks)} chunks).")

    # =========================================================================
    # MODULAR RETRIEVAL PIPELINE STAGES
    # =========================================================================

    def preprocess_query(self, query: str) -> str:
        """
        Stage 1: Preprocesses the query.
        """
        return query

    def dense_search(self, query: str, limit: int) -> list[dict]:
        """
        Stage 2: Dense Semantic Search.
        Queries Qdrant using the multilingual E5 embedding model.
        """
        if self.is_empty():
            return []
            
        prefixed_query = f"query: {query}"
        dense_query_vector = self.model.encode(prefixed_query, show_progress_bar=False).tolist()
        
        query_res = self.client.query_points(
            collection_name=self.collection_name,
            query=dense_query_vector,
            using="dense",
            limit=limit
        )
        
        dense_hits = []
        for point in query_res.points:
            score = point.score if point.score is not None else 0.0
            dense_hits.append({
                "text": point.payload.get("text", ""),
                "score": float(score),
                "metadata": {"source_document": point.payload.get("source_document")},
                "source": point.payload.get("source_document", "Unknown Source")
            })
        return dense_hits

    def sparse_search(self, query: str, limit: int) -> list[dict]:
        """
        Stage 3: Sparse Keyword Search.
        Queries Qdrant using the BM25 sparse index.
        """
        if self.is_empty():
            return []
            
        tokenized_query = tokenize_and_stem(query)
        sparse_indices, sparse_values = self.bm25_vectorizer.get_query_sparse_vector(tokenized_query)
        if not sparse_indices:
            return []
            
        from qdrant_client.models import SparseVector
        
        query_res = self.client.query_points(
            collection_name=self.collection_name,
            query=SparseVector(
                indices=sparse_indices,
                values=sparse_values
            ),
            using="sparse",
            limit=limit
        )
        
        sparse_hits = []
        for point in query_res.points:
            score = point.score if point.score is not None else 0.0
            sparse_hits.append({
                "text": point.payload.get("text", ""),
                "score": float(score),
                "metadata": {"source_document": point.payload.get("source_document")},
                "source": point.payload.get("source_document", "Unknown Source")
            })
        return sparse_hits

    def hybrid_fuse(self, dense_hits: list[dict], sparse_hits: list[dict], limit: int) -> list[dict]:
        """
        Stage 4: Hybrid Rank Fusion.
        This remains for backwards compatibility only.
        """
        k = 60
        rrf_scores = {}
        
        for rank, hit in enumerate(dense_hits):
            doc_text = hit["text"]
            if doc_text not in rrf_scores:
                rrf_scores[doc_text] = {
                    "text": doc_text,
                    "metadata": hit["metadata"],
                    "source": hit["source"],
                    "rrf_score": 0.0
                }
            rrf_scores[doc_text]["rrf_score"] += 1.0 / (k + (rank + 1))
            
        for rank, hit in enumerate(sparse_hits):
            doc_text = hit["text"]
            if doc_text not in rrf_scores:
                rrf_scores[doc_text] = {
                    "text": doc_text,
                    "metadata": hit["metadata"],
                    "source": hit["source"],
                    "rrf_score": 0.0
                }
            rrf_scores[doc_text]["rrf_score"] += 1.0 / (k + (rank + 1))
            
        sorted_hits = sorted(rrf_scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        max_rrf_possible = 2.0 / (k + 1)
        
        final_hits = []
        for hit in sorted_hits[:limit]:
            confidence = round((hit["rrf_score"] / max_rrf_possible) * 100, 1)
            final_hits.append({
                "text": hit["text"],
                "confidence": confidence,
                "source": hit["source"],
                "metadata": hit["metadata"]
            })
        return final_hits

    def retrieve(self, query: str, limit: int = 3) -> list[dict]:
        """
        Orchestration Entry Point.
        Runs the hybrid retrieval using Qdrant's native query API with RRF fusion.
        """
        if self.is_empty():
            return []
            
        processed_query = self.preprocess_query(query)
        overfetch_limit = max(20, limit * 3)
        
        # Dense representation
        prefixed_query = f"query: {processed_query}"
        dense_query_vector = self.model.encode(prefixed_query, show_progress_bar=False).tolist()
        
        # Sparse representation
        tokenized_query = tokenize_and_stem(processed_query)
        sparse_indices, sparse_values = self.bm25_vectorizer.get_query_sparse_vector(tokenized_query)
        
        from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
        
        if sparse_indices:
            # Query Qdrant with both dense and sparse sub-queries and fuse via RRF
            query_res = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    Prefetch(
                        query=dense_query_vector,
                        using="dense",
                        limit=overfetch_limit
                    ),
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_indices,
                            values=sparse_values
                        ),
                        using="sparse",
                        limit=overfetch_limit
                    )
                ],
                query=FusionQuery(
                    fusion=Fusion.RRF
                ),
                limit=limit
            )
        else:
            # Fallback to dense-only query if search term does not map to vocabulary
            query_res = self.client.query_points(
                collection_name=self.collection_name,
                query=dense_query_vector,
                using="dense",
                limit=limit
            )
            
        # Qdrant RRF uses k=1 by default; the maximum score with 2 query lists is 1/(1+1) + 1/(1+1) = 1.0
        max_rrf_possible = 1.0
        results = []
        for point in query_res.points:
            score = point.score if point.score is not None else 0.0
            if sparse_indices:
                confidence = round((score / max_rrf_possible) * 100, 1)
            else:
                confidence = round(score * 100, 1)
                
            results.append({
                "text": point.payload.get("text", ""),
                "confidence": confidence,
                "source": point.payload.get("source_document", "Unknown Source"),
                "metadata": {"source_document": point.payload.get("source_document")}
            })
            
        return results
