import ollama
from openai import OpenAI  # Used for the NVIDIA API
from medicalchatbot.common.agenticretriever import MedicalAgentRetriever
import time
import re

# --- CONFIGURATION ---
# Replace with your actual key or set it in your environment variables

# Initialize the NVIDIA Client (Primary)
nv_client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)


def medical_reasoning_pipeline(question: str, history_summary: str, retriever: MedicalAgentRetriever, session_id: str, is_standalone: bool = False):
    """
    Hybrid Reasoning Pipeline:
    Primary: NVIDIA API (Cloud 70B Model)
    Failover: Local Ollama (3B Model)
    """

    start_time = time.time()
    # 1. RETRIEVE CONTEXT (Always local for data privacy and speed)
    # We use the raw question for retrieval to avoid double-processing if frontend already rewrote it
    formatted_context = retriever.run(question, top_k=4)
    history_block = f"CONVERSATION HISTORY:\n{history_summary}\n\n" if not is_standalone else ""

    # 3. DEFINE SYSTEM PROMPT (Your original medical rules)
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

    prompt_content = (
        f"{history_block}\n\n"
        f"RETRIEVED EVIDENCE:\n{formatted_context}\n\n"
        f"CURRENT CLINICAL QUESTION: {question}"
    )

    # 4. PRIMARY ATTEMPT: NVIDIA 70B (High Intelligence)
    try:
        print(f"🚀 [Session: {session_id}] Attempting NVIDIA Cloud Reasoning...")
        completion = nv_client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[
                {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0,
            max_tokens=65536
        )
        answer = completion.choices[0].message.content
        source_tag = "NVIDIA-70B (Cloud)"

    # 5. FAILOVER ATTEMPT: LOCAL OLLAMA (Reliability)
    except Exception as e:
        print(f"⚠️ NVIDIA API Failed/Limit Reached: {e}")
        print("🔄 Switching to Local Failover Mode (Ollama llama3.2:3b)...")
        
        try:
            response = ollama.chat(
                model='llama3.2:3b',
                messages=[
                    {'role': 'system', 'content': MEDICAL_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt_content}
                ],
                options={'temperature': 0, 'num_ctx': 4096}
            )
            answer = response['message']['content']
            source_tag = "Llama-3.2-3B (Local Failover)"
        except Exception as local_e:
            return f"CRITICAL ERROR: Both Cloud and Local models failed. {str(local_e)}"

    # Optional: Append the source so you know which model answered
    answer = answer.replace("+ **", "- **")
    answer = re.sub(r'(?<!\n)\n(?![\n])', '\n\n', answer)
    answer = answer.replace("\n", "  \n")

    elapsed = round(time.time() - start_time, 2)
    final_output = f"{answer}\n\n---\n⏱️ **Latency:** {elapsed}s | 🧠 **Model:** {source_tag}"
#    return f"{answer}\n\n*System Note: Answered by {source_tag}*"
    return final_output