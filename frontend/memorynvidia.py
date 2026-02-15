from openai import OpenAI
import ollama

class MedicalMemory:
    def __init__(self, window_size=3):
        # Isolation for different sessions
        self.history_store = {} 
        self.window_size = window_size
        
        # Initialize NVIDIA Client
        # You can hardcode the key here as requested, or use os.getenv
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key="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"
        )

    def get_history_string(self, session_id):
        """Formats history ONLY for the specific session/tab."""
        history = self.history_store.get(session_id, [])
        return "\n".join([f"User: {q}\nAI: {a}" for q, a in history[-self.window_size:]])

    def add_turn(self, session_id, query, answer):
        if session_id not in self.history_store:
            self.history_store[session_id] = []
        self.history_store[session_id].append((query, answer))
        
        # Keep it lean
        if len(self.history_store[session_id]) > self.window_size:
            self.history_store[session_id].pop(0)

    def rewrite_query(self, session_id, current_query):
        """Uses NVIDIA API to rewrite follow-ups into standalone queries."""
        history = self.history_store.get(session_id, [])
        if not history:
            return current_query

        history_context = self.get_history_string(session_id)

            # 1. LOCAL CHECK: Is this a follow-up?
        # Use your local 3050 to save Cloud API credits
        check_prompt = f"""Is the query "{current_query}" a follow-up to previous chat? 
        Reply 'YES' if it uses pronouns (it, they, him) or refers to the previous context. 
        Reply 'NO' if it is a new/standalone topic.
        Reply ONLY 'YES' or 'NO'."""
        
        try:
            # Use a very low temperature for deterministic YES/NO
            check_res = ollama.chat(
                model='llama3.2:3b', 
                messages=[{'role': 'user', 'content': check_prompt}],
                options={'temperature': 0}
            )
            is_followup = "YES" in check_res['message']['content'].upper()
        except Exception as e:
            print(f"Local Ollama Error: {e}")
            is_followup = True # Default to True to be safe if local fails

        if not is_followup:
            print("✨ Standalone query detected locally. Skipping NVIDIA rewrite.")
            return current_query
        
        rewrite_prompt = f"""
        Current Conversation:
        {history_context}
            
        New Follow-up: "{current_query}"
            
        Task: 
        1. Identify the medical condition or drug being discussed.
        2. Re-write the 'New Follow-up' into a standalone medical search query.
        3. Provide ONLY the search query. No preamble.
            
        Standalone Query:"""

        try:
            # Using NVIDIA's Llama 3.3 70B for high-accuracy rewriting
            response = self.client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[{"role": "user", "content": rewrite_prompt}],
                temperature=0,
                max_tokens=64
            )
                
            rewritten = response.choices[0].message.content.strip()
            print("Successfully used nvidia gpu")
            # Clean up potential model prefixes
            return rewritten.split('\n')[-1].replace('Standalone Query:', '').strip()
                
        except Exception as e:
            print(f"NVIDIA Rewrite Error: {e}")
            # If API fails, return original query so the system doesn't break
            return current_query
    
memory_manager = MedicalMemory()