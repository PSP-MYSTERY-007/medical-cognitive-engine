from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import uvicorn
import ollama
from fastembed import TextEmbedding, SparseTextEmbedding
from medicalchatbot.common.agenticretriever import MedicalAgentRetriever
import site
import os

# Import your custom modules
from medicalchatbot.common.agenticretriever import MedicalAgentRetriever
from medicalchatbot.common.reasoningnvidia import medical_reasoning_pipeline
from medicalchatbot.common.logger_config import log_clinical_interaction

app = FastAPI(title="Medical Engine Server")

ve_packages = site.getsitepackages()
for path in ve_packages:
    nvidia_path = os.path.join(path, "nvidia")
    if os.path.exists(nvidia_path):
        for root, dirs, _ in os.walk(nvidia_path):
            if "bin" in dirs:
                bin_dir = os.path.join(root, "bin")
                os.add_dll_directory(bin_dir)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]

# Initialize models once on the CPU
dense = TextEmbedding("BAAI/bge-small-en-v1.5")
sparse = SparseTextEmbedding("prithivida/Splade_PP_en_v1")
agent_retriever = MedicalAgentRetriever(ollama, dense, sparse)

class QueryRequest(BaseModel):
    question: str
    history_summary:str
    force_local: bool = False  # Added this to match Frontend payload

@app.post("/{laptop_code}/{mode}/{session_id}")
async def medical_engine_endpoint(laptop_code: str, mode: str, session_id: str, data: QueryRequest, request: Request):
    client_ip = request.client.host

    try:
        if mode.lower() == "chat":
        # The session_id from the URL ensures isolated memory in reasoning.py
            answer = medical_reasoning_pipeline(
                question=data.question,
                history_summary=data.history_summary,
                retriever=agent_retriever,
                session_id=session_id,
            )
            
            # Centralized Audit Logging
            log_clinical_interaction(
                mode=mode,
                module_tag=f"{laptop_code}_{mode.upper()}",
                session_id=session_id,
                client_ip=client_ip,
                query=data.question,
                response=answer
            )
            
        
        elif mode.lower() == "dd":
            # 1. Run Differential Diagnosis Logic
            # (You would call your specific DD function here)
            answer = f"Differential Diagnosis for: {data.question} - still on the way building" # THIS IS WHERE THE FRONTEND WILL COMMUNICATE 
            
            # 2. Log to the DIAGNOSTIC_ANALYSIS audit stream
            log_clinical_interaction(
                mode=mode,
                module_tag=f"{laptop_code}_DD_LOG",
                session_id=session_id,
                client_ip=client_ip,
                query=data.question,
                response=answer,
            )

        else:
            raise HTTPException(status_code=400, detail="Unsupported mode.")
        
        return {"answer": answer, "session_id": session_id, "status": "success"}
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Use 0.0.0.0 to be visible on the local network
    uvicorn.run(app, host="0.0.0.0", port=8000)