from .base import VectorStore
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings

class ChromaStore(VectorStore):
    def __init__(self, dir_path: str = "./data/chroma"):
        self.client = chromadb.PersistentClient(path=dir_path, settings=Settings(anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"})

    def upsert(self, points: List[Dict[str, Any]]) -> None:
        self.collection.upsert(
            ids=[p["id"] for p in points],
            embeddings=[p["embedding"] for p in points],
            documents=[p["text"] for p in points],
            metadatas=[p["metadata"] for p in points]
        )

    def query(self, query_vec: List[float], top_k: int, filter_by: Dict[str, Any]) -> List[Dict[str, Any]]:
        where = filter_by or {}
        res = self.collection.query(query_embeddings=[query_vec], n_results=top_k, where=where)
        out = []
        if res["ids"]:
            for i in range(len(res["ids"][0])):
                # Chroma returns cosine distance; convert distance -> similarity
                sim = 1.0 - float(res["distances"][0][i])
                out.append({
                    "id": res["ids"][0][i],
                    "text": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "score": sim
                })
        return out

    def delete_where(self, where: Dict[str, Any]) -> None:
        self.collection.delete(where=where)
