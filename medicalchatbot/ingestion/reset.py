from medicalchatbot.common.vectorstore import get_qdrant_client
import os

def reset_storage():
    # We just need any client to access the list_collections method
    # Passing 'temp' since get_qdrant_client now requires a name
    client = get_qdrant_client("temp")
    
    # 1. Get all existing collections
    collections_response = client.get_collections()
    collection_names = [c.name for c in collections_response.collections]
    
    if not collection_names:
        print("📭 No collections found. Nothing to delete.")
        return

    print(f"🔍 Found collections: {collection_names}")
    
    # 2. Iterate and delete the relevant ones
    # You can also use: target_collections = ["cpg_docs", "textbook_docs"]
    for name in collection_names:
        client.delete_collection(name)
        print(f"🔥 Deleted {name}.")

    registry_file = "data/ingestion_registry.json"
    if os.path.exists(registry_file):
        os.remove(registry_file)
        print(f"🗑️  Deleted {registry_file}.")
    else:
        print(f"ℹ️  {registry_file} not found, skipping.")

    print("\n✅ Reset complete. Now run ingest.py to recreate your collections correctly.")

if __name__ == "__main__":
    reset_storage()