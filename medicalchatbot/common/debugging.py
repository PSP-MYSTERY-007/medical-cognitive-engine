from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)

for name in ["cpg_docs", "textbook_docs"]:
    if client.collection_exists(name):
        info = client.get_collection(name)
        count = info.points_count
        # This will show you exactly what names Qdrant is using
        vectors = info.config.params.vectors
        sparse = info.config.params.sparse_vectors
        print(f"Collection: {name} | Points: {count}")
        print(f" - Dense Names: {list(vectors.keys()) if isinstance(vectors, dict) else 'default'}")
        print(f" - Sparse Names: {list(sparse.keys()) if sparse else 'None'}")
    else:
        print(f"❌ {name} does not exist!")