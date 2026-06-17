import os
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    SparseVectorParams,
    SparseIndexParams,
    Filter,
)

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

class QdrantDatabaseManager:
    """
    Manages direct connections and CRUD operations with the Qdrant database.
    """
    def __init__(self, db_path: str, collection_name: str):
        self.db_path = db_path
        self.collection_name = collection_name
        self.client = QdrantClient(path=db_path)
        self.collection = QdrantCollectionWrapper(self.client, collection_name)
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        collection_exists = False
        try:
            self.client.get_collection(self.collection_name)
            collection_exists = True
        except Exception:
            pass
            
        if not collection_exists:
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

    def is_empty(self) -> bool:
        """Returns True if the database contains zero documents."""
        try:
            count = self.client.get_collection(self.collection_name).points_count
            return count is None or count == 0
        except Exception:
            return True

    def get_all_points(self):
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

    def clear_database(self):
        """Deletes all documents inside the collection to allow a fresh ingest."""
        try:
            # Delete all points inside the collection using a match-all filter.
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter()
            )
        except Exception as e:
            print(f"Note: failed to delete points via selector: {e}")
            try:
                self.client.delete_collection(self.collection_name)
                self._ensure_collection_exists()
            except Exception as ex:
                print(f"Error recreating collection: {ex}")
