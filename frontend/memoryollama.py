import ollama

class MedicalMemory:
    def __init__(self, window_size=3):
        # Keeps different chat sessions isolated
        self.history_store = {} 
        self.window_size = window_size

    def get_history_string(self, session_id):
        """Formats conversation history for the specific session."""
        history = self.history_store.get(session_id, [])
        return "\n".join([f"User: {q}\nAI: {a}" for q, a in history[-self.window_size:]])

    def add_turn(self, session_id, query, answer):
        """Saves a new interaction to the session history."""
        if session_id not in self.history_store:
            self.history_store[session_id] = []
        self.history_store[session_id].append((query, answer))
        
        # Keep the memory footprint small
        if len(self.history_store[session_id]) > self.window_size:
            self.history_store[session_id].pop(0)

    def rewrite_query(self, session_id, current_query):
        """
        Rewrites ambiguous follow-ups into standalone medical queries.
        This runs on the Frontend (CPU/Ollama).
        """
        history = self.history_store.get(session_id, [])
        if not history:
            return current_query

        history_context = self.get_history_string(session_id)
        
        rewrite_prompt = f"""
        Current Conversation:
        {history_context}
        
        New Follow-up: "{current_query}"
        
        Task: 
        1. Identify the medical condition or drug being discussed.
        2. Re-write the 'New Follow-up' into a standalone search query for a medical database.
        3. Provide ONLY the search query. No preamble.
        
        Standalone Query:"""

        try:
            # Note: Using llama3.2 (1b is even faster for CPU if available)
            response = ollama.chat(
                model='llama3.2:3b', 
                messages=[{'role': 'user', 'content': rewrite_prompt}],
                options={
                    'temperature': 0,
                    'num_ctx': 512,      # Small context is enough for rewriting
                    'num_predict': 50,    # Stop early to keep it snappy
                }
            )
            
            rewritten = response['message']['content'].strip()
            # Clean up potential model prefixes
            return rewritten.replace('Standalone Query:', '').strip()
            
        except Exception as e:
            print(f"Frontend Memory Error: {e}")
            return current_query

# Singleton instance for the frontend app to import
memory_manager = MedicalMemory()