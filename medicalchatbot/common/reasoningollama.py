import ollama
from common.agenticretriever import MedicalAgentRetriever
from frontend.memorynvidia import memory_manager  # Use the session-aware manager

def medical_reasoning_pipeline(question: str, retriever: MedicalAgentRetriever, session_id: str):
    """
    RAG-focused reasoning pipeline.
    Identical logic to your original, but refactored for multi-session support.
    """
    
    # 1. MEMORY RE-WRITING (Contextualization)
    # We call the re-writer logic now stored in the session-aware memory_manager
    search_query = memory_manager.rewrite_query(session_id, question)
    
    if search_query != question:
        print(f"🔍 [Session: {session_id}] Contextualized Search: {search_query}")

    # 2. PERSONA & RULES (Your original rules)
    MEDICAL_SYSTEM_PROMPT = (
        "You are a Clinical Reasoning Engine and only doctors and medical students can access you. "
        "You are provided with context from Pharmacopoeias (Knowledge Graph), "
        "Clinical Practice Guidelines (CPG), and Medical Textbooks.\n\n"
        "STRICT OPERATIONAL RULE: Do NOT repeat the previous answers provided in the history. "
        "Provide ONLY the new answer for the current question.\n\n"
        "STRICT RULES:\n"
        "1. PHARMACOPOEIA RULES: These are deterministic safety rules. If a contraindication, "
        "critical side effect, or lab requirement is mentioned here, you MUST lead with a '⚠️ SAFETY WARNING'.\n"
        "2. CLINICAL GUIDELINES (CPG): Prioritize these for treatment protocols and dosing steps.\n"
        "3. TEXTBOOKS: Use for background explanation and anatomy. Do NOT use textbook dosing if it conflicts with CPGs.\n"
        "4. CITATION: Use parentheses for sources, e.g., (Source Title). DO NOT include '.pdf' in the title.\n"
        "5. SYNTHESIS: Merge Pharmacopoeia safety, CPG methods, and Textbook theory into one answer.\n"
        "6. FORMAT: Use bullet points for drug doses or diagnostic criteria.\n"
        "7. MISSING DATA: If the Pharmacopoeia requires a lab value (e.g., eGFR, LFTs) not found in the context, "
        "state: 'ACTION REQUIRED: Verify [Parameter] before proceeding.'\n"
        "8. FALLBACK: If information is missing, say: 'Information not available in current sources.'\n"
        "9. FLEXIBILITY: Only follow rules 1-7 if relevant data exists. Ensure the answer is clear.\n"
        "10. BOLDING: **Bold** the important topic words that relate directly to the user's question."
    )

    # 3. AGENTIC RETRIEVAL
    formatted_context = retriever.run(search_query, top_k=4)

    # 4. PREPARE CONVERSATIONAL CONTEXT
    # Get history summary specific to THIS session/tab
    history_summary = memory_manager.get_history_string(session_id)

    # 5. OLLAMA FINAL CALL
    try:
        response = ollama.chat(
            model='llama3.2:3b',
            messages=[
                {'role': 'system', 'content': MEDICAL_SYSTEM_PROMPT},
                {
                    'role': 'user', 
                    'content': (
                        f"CONVERSATION HISTORY:\n{history_summary}\n\n"
                        f"RETRIEVED EVIDENCE (KG & DB):\n{formatted_context}\n\n"
                        f"CURRENT CLINICAL QUESTION: {question}"
                        )
                }
            ],
            options={'temperature': 0, 'num_ctx': 4096}
        )
        
        answer = response['message']['content']
        
        # 6. UPDATE SESSION MEMORY
        memory_manager.add_turn(session_id, question, answer)
            
        return answer

    except Exception as e:
        return f"Error: {str(e)}"
    
if __name__ == "__main__":
    from fastembed import TextEmbedding, SparseTextEmbedding

    dense = TextEmbedding("BAAI/bge-small-en-v1.5")
    sparse = SparseTextEmbedding("prithivida/Splade_PP_en_v1")
    agent_retriever = MedicalAgentRetriever(ollama, dense, sparse)

    print("🏥 Medical Cognitive Engine (with Memory) is online.")
    print("Commands: '/reset' to clear memory, 'exit' to quit.\n")

    while True:
        user_query = input("🩺 Enter your medical query: ").strip()
        if user_query.lower() in ["exit", "quit"]:
            break

        if user_query == "/reset":
            chat_history = []
            print("✨ Memory cleared.")
            continue

        if not user_query:
            continue

        try:
            result = medical_reasoning_pipeline(user_query, agent_retriever)
            print("-" * 30)
            print(f"✅ RESPONSE:\n{result}")
            print("-" * 30 + "\n")
        except Exception as e:
            print(f"❌ An error occurred: {e}\n")