import uuid
import json
import hashlib
import time
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

def get_embedding_providers():
    use_cuda = os.getenv("MEDICAL_INGEST_USE_CUDA", "0").strip().lower() in {"1", "true", "yes", "y"}
    if use_cuda:
        print("⚙️ Embedding provider mode: CUDA+CPU")
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    print("⚙️ Embedding provider mode: CPU")
    return ["CPUExecutionProvider"]

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
    started_at = time.time()
    client = get_qdrant_client(collection_name)
    registry = load_registry()

    providers = get_embedding_providers()
    dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", providers=providers)
    sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1", providers=providers)

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
        print(f"⏱️ {doc_type.upper()} ingestion time: {time.time() - started_at:.2f}s")
        return

    print(f"🚀 Found {len(files_to_process)} new/modified files. Starting ingestion...")

    for pdf_name, full_path, file_hash in files_to_process:
        print(f"📄 Processing {pdf_name}...")
        try:
            loader = PyMuPDFLoader(full_path)
            docs = loader.load()
            print(f"   • Loaded pages: {len(docs)}")

            for d in docs:
                d.metadata["type"] = doc_type

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=120,
                separators=["\n\n", "\n", ".", " "]
            )
            chunks = splitter.split_documents(docs)
            texts = [chunk.page_content for chunk in chunks]
            total_chunks = len(chunks)
            print(f"   • Created chunks: {total_chunks}")

            print("   • Generating dense embeddings...")
            dense_vectors = list(dense_model.embed(texts, batch_size=4))
            print("   • Generating sparse embeddings...")
            sparse_vectors = list(sparse_model.embed(texts, batch_size=4))

            points_to_upload = []
            progress_step = max(1, total_chunks // 20)  # ~5% updates
            point_build_started_at = time.time()
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
                if (i + 1) % progress_step == 0 or (i + 1) == total_chunks:
                    elapsed = time.time() - point_build_started_at
                    processed = i + 1
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = total_chunks - processed
                    eta = (remaining / rate) if rate > 0 else 0
                    print(f"   • Building points: {processed}/{total_chunks} | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s")

            print(f"   • Uploading {len(points_to_upload)} points to Qdrant...")
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
    print(f"⏱️ {doc_type.upper()} ingestion time: {time.time() - started_at:.2f}s")

if __name__ == "__main__":
    total_started_at = time.time()
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
    print(f"⏱️ Total ingestion time: {time.time() - total_started_at:.2f}s")