import uuid
import json
import hashlib
from qdrant_client import models
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from medicalchatbot.common.vectorstore import get_qdrant_client
from fastembed import TextEmbedding, SparseTextEmbedding
import os
import gc
import site

# --- REGISTRY HELPERS ---
REGISTRY_PATH = "data/ingestion_registry.json"

def load_registry():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    return {}

def save_registry(registry):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=4)

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

# --- EXISTING DLL FIX ---
ve_packages = site.getsitepackages()
for path in ve_packages:
    nvidia_path = os.path.join(path, "nvidia")
    if os.path.exists(nvidia_path):
        for root, dirs, _ in os.walk(nvidia_path):
            if "bin" in dirs:
                bin_dir = os.path.join(root, "bin")
                os.add_dll_directory(bin_dir)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]

def process_documents(folder_path: str, collection_name: str, doc_type: str):
    """Ingest only NEW or MODIFIED PDFs."""
    client = get_qdrant_client(collection_name)
    registry = load_registry()

    dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])

    if not os.path.exists(folder_path):
        print(f"❌ Folder not found: {folder_path}")
        return

    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    
    # Check each file against the registry
    files_to_process = []
    for pdf_file in pdf_files:
        full_path = os.path.join(folder_path, pdf_file)
        current_hash = calculate_md5(full_path)
        
        # Incremental Check
        if pdf_file in registry and registry[pdf_file] == current_hash:
            print(f"⏩ Skipping {pdf_file} (Already up to date)")
            continue
        
        files_to_process.append((pdf_file, full_path, current_hash))

    if not files_to_process:
        print(f"✅ All files in '{doc_type}' folder are already ingested.")
        return

    print(f"🚀 Found {len(files_to_process)} new/modified files. Starting ingestion...")

    for pdf_name, full_path, file_hash in files_to_process:
        print(f"📄 Processing {pdf_name}...")
        try:
            loader = PyMuPDFLoader(full_path)
            docs = loader.load()

            for d in docs:
                d.metadata["type"] = doc_type

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=120,
                separators=["\n\n", "\n", ".", " "]
            )
            chunks = splitter.split_documents(docs)
            texts = [chunk.page_content for chunk in chunks]

            dense_vectors = list(dense_model.embed(texts, batch_size=4))
            sparse_vectors = list(sparse_model.embed(texts, batch_size=4))

            points_to_upload = []
            for i, chunk in enumerate(chunks):
                points_to_upload.append(
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        payload={
                            "document": chunk.page_content,
                            "source": pdf_name,
                            "page": chunk.metadata.get("page", "unknown"),
                            "type": doc_type
                        },
                        vector={
                            "dense": dense_vectors[i].tolist(),
                            "sparse": models.SparseVector(
                                indices=sparse_vectors[i].indices.tolist(),
                                values=sparse_vectors[i].values.tolist()
                            )
                        }
                    )
                )

            client.upload_points(collection_name=collection_name, points=points_to_upload, wait=True)
            
            # ✅ Update registry only AFTER successful upload
            registry[pdf_name] = file_hash
            save_registry(registry)
            
            print(f"✅ Indexed {pdf_name}.")
            gc.collect()

        except Exception as e:
            print(f"⚠️ Failed to process {pdf_name}: {e}")

    del dense_model, sparse_model
    gc.collect()

if __name__ == "__main__":
    base_folder = os.path.join(os.getcwd(), "data", "pdfs")
    
    # Process Guidelines
    process_documents(
        folder_path=os.path.join(base_folder, "cpg"), 
        collection_name="cpg_docs", 
        doc_type="cpg"
    )
    
    # Process Textbooks
    process_documents(
        folder_path=os.path.join(base_folder, "textbook"), 
        collection_name="textbook_docs", 
        doc_type="textbook"
    )
    
    print("✨ Incremental ingestion complete.")