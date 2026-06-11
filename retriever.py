import os
import re
import chromadb
from chromadb.api.types import Documents, Embeddings
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
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


class MultilingualE5EmbeddingFunction(chromadb.EmbeddingFunction):

    """
    Custom embedding function class for ChromaDB.
    Uses 'intfloat/multilingual-e5-small' locally on CPU.
    Automatically handles 'passage: ' prefixing for documents and 'query: ' for queries.
    """
    def __init__(self, model_name="intfloat/multilingual-e5-small", device="cpu"):
        self.model = SentenceTransformer(model_name, device=device)
        
    def __call__(self, input: Documents) -> Embeddings:
        # Fallback to document embedding
        return self.embed_documents(input)
        
    def embed_documents(self, input: Documents) -> Embeddings:
        # E5 model requires documents to be prefixed with "passage: "
        prefixed_docs = [f"passage: {doc}" for doc in input]
        embeddings = self.model.encode(prefixed_docs, show_progress_bar=False)
        return embeddings.tolist()
        
    def embed_query(self, input: Documents) -> Embeddings:
        # E5 model requires queries to be prefixed with "query: "
        prefixed_queries = [f"query: {doc}" for doc in input]
        embeddings = self.model.encode(prefixed_queries, show_progress_bar=False)
        return embeddings.tolist()


class LocalBilingualRetriever:
    """
    A modular hybrid retriever that combines dense semantic search (E5 vectors via ChromaDB)
    and sparse keyword search (BM25) with Reciprocal Rank Fusion (RRF).
    Supports English and Swedish natively.
    """
    def __init__(self, db_path="./local_chroma_db", collection_name="bilingual_rag"):
        """Initializes database, embedding function, and registers runtime state."""
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Load local bilingual E5 embedding function
        self.dense_ef = MultilingualE5EmbeddingFunction(
            model_name="intfloat/multilingual-e5-small",
            device="cpu"
        )
        
        # Connect to ChromaDB collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.dense_ef
        )
        
        # Keyword index tracking variables
        self.bm25 = None
        self.indexed_chunks = []
        self.indexed_metadatas = []
        
        # Sync keyword index with existing data if database is already populated
        if not self.is_empty():
            self._rebuild_keyword_index()

    def is_empty(self) -> bool:
        """Returns True if the database contains zero documents."""
        return self.collection.count() == 0

    def _rebuild_keyword_index(self):
        """Fetches all documents from ChromaDB and rebuilds the BM25 keyword index."""
        existing_data = self.collection.get(include=["documents", "metadatas"])
        if existing_data and existing_data["documents"]:
            self.indexed_chunks = existing_data["documents"]
            self.indexed_metadatas = existing_data["metadatas"]
            
            # Tokenize documents using bilingual tokenizer and stemmer
            tokenized_corpus = [tokenize_and_stem(doc) for doc in self.indexed_chunks]
            self.bm25 = BM25Okapi(tokenized_corpus)

    def clear_database(self):
        """Deletes all documents inside the collection to allow a fresh ingest."""
        existing = self.collection.get()
        if existing and existing["ids"]:
            self.collection.delete(ids=existing["ids"])
        self.bm25 = None
        self.indexed_chunks = []
        self.indexed_metadatas = []
        print("🧹 Local database collection cleared successfully.")

    def chunk_and_add_document(self, text: str, source_name: str, chunk_size: int = 50, overlap: int = 10):
        """Splits a document into overlapping word-level chunks and saves them in ChromaDB."""
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
            current_count = self.collection.count()
            ids = [f"doc_{current_count + idx}" for idx in range(len(chunks))]
            
            # Save dense vectors and text chunks into ChromaDB
            self.collection.add(documents=chunks, metadatas=metadatas, ids=ids)
            
            # Rebuild keyword index to include new chunks
            self._rebuild_keyword_index()
            print(f"📥 Indexed and saved '{source_name}' ({len(chunks)} chunks).")

    # =========================================================================
    # MODULAR RETRIEVAL PIPELINE STAGES
    # =========================================================================

    def preprocess_query(self, query: str) -> str:
        """
        Stage 1: Preprocesses the query.
        This serves as a placeholder where modular features (e.g., query translation,
        query rewriting, or synonym expansion) can be added in the future.
        """
        # Currently passes the query through unchanged
        return query

    def dense_search(self, query: str, limit: int) -> list[dict]:
        """
        Stage 2: Dense Semantic Search.
        Queries ChromaDB using the multilingual E5 embedding model.
        Query strings are prefixed with 'query: ' as required by the E5 model.
        """
        if self.is_empty():
            return []
            
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            include=["documents", "distances", "metadatas"]
        )
        
        dense_hits = []
        if results and results["documents"] and results["documents"][0]:
            documents = results["documents"][0]
            distances = results["distances"][0]
            metadatas = results["metadatas"][0]
            
            for doc, dist, meta in zip(documents, distances, metadatas):
                dense_hits.append({
                    "text": doc,
                    "score": float(dist),
                    "metadata": meta,
                    "source": meta.get("source_document", "Unknown Source")
                })
        return dense_hits

    def sparse_search(self, query: str, limit: int) -> list[dict]:
        """
        Stage 3: Sparse Keyword Search.
        Evaluates exact keyword overlap scores using BM25 across all indexed chunks.
        """
        if self.is_empty() or not self.bm25:
            return []
            
        tokenized_query = tokenize_and_stem(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        sparse_hits = []
        for idx, (doc, meta) in enumerate(zip(self.indexed_chunks, self.indexed_metadatas)):
            score = float(bm25_scores[idx])
            if score > 0:
                sparse_hits.append({
                    "text": doc,
                    "score": score,
                    "metadata": meta,
                    "source": meta.get("source_document", "Unknown Source")
                })
                
        # Sort by BM25 score descending
        sparse_hits.sort(key=lambda x: x["score"], reverse=True)
        return sparse_hits[:limit]

    def hybrid_fuse(self, dense_hits: list[dict], sparse_hits: list[dict], limit: int) -> list[dict]:
        """
        Stage 4: Hybrid Rank Fusion.
        Merges dense search results and sparse keyword search results using
        Reciprocal Rank Fusion (RRF). This avoids scale compatibility issues.
        """
        k = 60  # RRF constant
        rrf_scores = {}
        
        # Score dense results based on rank position
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
            
        # Score sparse results based on rank position
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
            
        # Sort candidates by combined RRF score descending
        sorted_hits = sorted(rrf_scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        
        # Calculate a normalized confidence percentage (max RRF possible is 2/(k+1) if rank 1 in both lists)
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
        Runs the full modular pipeline: preprocessing -> searches -> hybrid fusion.
        """
        if self.is_empty():
            return []
            
        # 1. Preprocess Query
        processed_query = self.preprocess_query(query)
        
        # Over-fetch search candidates to ensure rank overlap for RRF
        overfetch_limit = limit * 3
        
        # 2. Dense Semantic Search
        dense_hits = self.dense_search(processed_query, limit=overfetch_limit)
        
        # 3. Sparse Keyword Search
        sparse_hits = self.sparse_search(processed_query, limit=overfetch_limit)
        
        # 4. Reciprocal Rank Fusion
        fused_hits = self.hybrid_fuse(dense_hits, sparse_hits, limit=limit)
        
        return fused_hits
