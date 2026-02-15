# trialcpg/vectorstore.py
from qdrant_client import QdrantClient, models

def get_qdrant_client(collection_name: str):
    client = QdrantClient(host="localhost", port=6333)
    
    # We still set these so the client knows WHICH models to use for .embed()
#    client.set_model("BAAI/bge-small-en-v1.5")
#    client.set_sparse_model("prithivida/Splade_PP_en_v1")
    
    if not client.collection_exists(collection_name):
        print(f"🏗️ Creating collection: {collection_name}")
        
        client.create_collection(
            collection_name=collection_name,
            # MANUAL CONFIG: No more helper dictionaries that cause KeyErrors
            vectors_config={
                "dense": models.VectorParams(
                    size=384, # Fixed size for bge-small-en-v1.5
                    distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=True)
                )
            }
        )
    return client