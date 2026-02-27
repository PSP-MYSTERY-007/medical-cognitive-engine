import json
import os
from openai import OpenAI
import ollama

OSCE_PATIENT_BLOCKED_TOPICS = [
    "diagnosis", "differential", "investigation", "investigations", "management", "treatment", "plan"
]

OSCE_PATIENT_HISTORY_KEYWORDS = [
    "history", "onset", "symptom", "prior", "past", "social", "smoke", "smoker", "smoking", "drug", "caffeine", "alcohol"
]

OSCE_PATIENT_EXAM_KEYWORDS = [
    "physical", "pjhysical", "exam", "exe", "vitals", "bp", "blood pressure", "heart rate", "hr", "rr", "spo2", "temperature", "temp", "finding"
]


def build_osce_patient_system_prompt(case_data):
    safe_case_data = case_data if isinstance(case_data, dict) else {}
    case_json = json.dumps(safe_case_data, ensure_ascii=False)
    return (
        "You are an OSCE patient simulator. "
        "Act like a real human patient in a natural conversational tone.\n\n"
        "Rules you must always follow:\n"
        "1) Only answer using the provided case data. Do not invent facts.\n"
        "2) You may answer only about history and physical exam.\n"
        "3) If asked about diagnosis, differential diagnosis, investigations, management, treatment plan, or anything outside history/physical exam, reply exactly: that's your part\n"
        "4) Speak like a patient, using short natural first-person sentences.\n"
        "5) Contextualize frequency words naturally: 'Occasional' means a few times a week, sometimes once a day.\n"
        "6) If a detail is missing from case data, say it is not specified.\n\n"
        f"Case data: {case_json}"
    )

class MedicalMemory:
    def __init__(self, window_size=5, storage_file="chat_history.json"):
        self.storage_file = storage_file
        self.window_size = window_size
        self.sessions = self._load_sessions()
        
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key="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"
        )

    def _load_sessions(self):
        if os.path.exists(self.storage_file):
            with open(self.storage_file, "r") as f:
                return json.load(f)
        return {}

    def _save_sessions(self):
        """Saves sessions to JSON with clear formatting and line breaks."""
        with open(self.storage_file, "w") as f:
            # indent=4 makes it pretty-printed
            # sort_keys=True keeps it organized
            json.dump(self.sessions, f, indent=4, sort_keys=True)
            # This adds a final newline at the very end of the file
            f.write("\n")

    def get_session_list(self):
        """Returns sessions sorted by pinned status then recency."""
        return sorted(
            self.sessions.items(), 
            key=lambda x: (x[1].get("pinned", False), x[1].get("timestamp", 0)), 
            reverse=True
        )

    def create_new_session(self, session_id):
        self.sessions[session_id] = {
            "title": "New Consultation",
            "messages": [],
            "pinned": False,
            "timestamp": 0
        }
        self._save_sessions()

    def update_session_meta(self, session_id, **kwargs):
        if session_id not in self.sessions:
            self.create_new_session(session_id)
        self.sessions[session_id].update(kwargs)
        self._save_sessions()

    def delete_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_sessions()

    def clear_all_sessions(self):
        self.sessions = {}
        self._save_sessions()

    def toggle_pin(self, session_id):
        if session_id in self.sessions:
            self.sessions[session_id]["pinned"] = not self.sessions[session_id].get("pinned", False)
            self._save_sessions()

    def _generate_ai_title(self, query, answer):
        """Uses local Ollama to create a 3-5 word title."""
        title_prompt = f"""Summarize this medical query into a 3-5 word title. 
        Query: {query}
        Answer: {answer[:100]}...
        Title:"""
        
        try:
            res = ollama.chat(
                model='llama3.2:3b', 
                messages=[{'role': 'user', 'content': title_prompt}],
                options={'temperature': 0.3}
            )
            title = res['message']['content'].strip().replace('"', '')
            return title if title else query[:30]
        except:
            return query[:30] # Fallback to text slice if Ollama fails

    def add_turn(self, session_id, query, answer):
        if session_id not in self.sessions:
            self.create_new_session(session_id)
        
        # 1. Generate AI Title if this is the first interaction
        if len(self.sessions[session_id]["messages"]) == 0:
            ai_title = self._generate_ai_title(query, answer)
            self.sessions[session_id]["title"] = ai_title
            
        # 2. Append the User message
        self.sessions[session_id]["messages"].append({"role": "user", "content": query})
        
        # 3. Append the Assistant message WITH a visual newline/separator
        # This makes it easier to read when printed or viewed in the history
        visual_answer = f"{answer}\n\n"
        self.sessions[session_id]["messages"].append({"role": "assistant", "content": visual_answer})
        
        # 4. Update metadata
        import time
        self.sessions[session_id]["timestamp"] = time.time()
        
        # 5. Save to JSON
        self._save_sessions()

    def get_history_string(self, session_id):
        # 1. Access the session data from the self.sessions dictionary loaded from JSON
        session_data = self.sessions.get(session_id, {})
        messages = session_data.get("messages", [])
        
        # 2. Get the last N turns (user + assistant)
        recent = messages[-(self.window_size * 2):]
        
        # 3. Clean and Format
        history_lines = []
        for m in recent:
            role = m['role'].capitalize()
            content = m['content']
            
            # Remove the visual separator '---' so the AI doesn't see it in its memory
            clean_content = content.replace("\n\n---", "").strip()
            
            history_lines.append(f"{role}: {clean_content}")
            
        return "\n".join(history_lines)

    def rewrite_query(self, session_id, current_query):
        """Uses NVIDIA API to rewrite follow-ups into standalone queries."""
        # FIX: Access the 'messages' list within the specific session
        session_data = self.sessions.get(session_id, {})
        history = session_data.get("messages", [])
        
        if not history:
            return current_query

        history_context = self.get_history_string(session_id)

        # 1. LOCAL CHECK: Is this a follow-up?
        check_prompt = f"""Is the query "{current_query}" a follow-up to previous chat? 
        Reply 'YES' if it uses pronouns (it, they, him) or refers to the previous context. 
        Reply 'NO' if it is a new/standalone topic.
        Reply ONLY 'YES' or 'NO'."""
        
        try:
            check_res = ollama.chat(
                model='llama3.2:3b', 
                messages=[{'role': 'user', 'content': check_prompt}],
                options={'temperature': 0}
            )
            is_followup = "YES" in check_res['message']['content'].upper()
        except Exception as e:
            print(f"Local Ollama Error: {e}")
            is_followup = True 

        if not is_followup:
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
            response = self.client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[{"role": "user", "content": rewrite_prompt}],
                temperature=0,
                max_tokens=64
            )
                
            rewritten = response.choices[0].message.content.strip()
            # Clean up potential model prefixes
            return rewritten.split('\n')[-1].replace('Standalone Query:', '').strip()
                
        except Exception as e:
            print(f"NVIDIA Rewrite Error: {e}")
            return current_query
    
memory_manager = MedicalMemory()
