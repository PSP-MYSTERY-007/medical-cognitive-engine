import streamlit as st
import requests
import uuid
from memorynvidia import memory_manager

# --- CONFIG ---
SERVER_IP = "127.0.0.1"
LAPTOP_CODE = "STUDENT_LAPTOP_01"

st.set_page_config(page_title="Medical Cognitive Engine", page_icon="🩺", layout="wide")

# Initialize Session ID if not present
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# --- SIDEBAR: CHAT HISTORY ---
with st.sidebar:
    st.title("📂 Medical History")
    
    if st.button("➕ New Consultation", use_container_width=True):
        # Create a new unique ID
        new_id = str(uuid.uuid4())
        # Initialize it in memory manager
        memory_manager.create_new_session(new_id)
        # Switch session
        st.session_state.session_id = new_id
        st.rerun()

    st.divider()

    # Get sorted sessions (Pinned first, then newest)
    sessions = memory_manager.get_session_list()

    for sid, data in sessions:
        # Create a row with columns for the Title and the Pin button
        col_title, col_pin = st.columns([0.8, 0.2])
        
        with col_title:
            is_active = st.session_state.session_id == sid
            label = f"{'⭐ ' if data.get('pinned') else ''}{data['title']}"
            
            if st.button(label, key=f"sel_{sid}", use_container_width=True, 
                         type="primary" if is_active else "secondary"):
                st.session_state.session_id = sid
                st.rerun()
        
        with col_pin:
            pin_label = "📌" if data.get("pinned") else "📍"
            if st.button(pin_label, key=f"pin_{sid}", help="Pin to top"):
                memory_manager.toggle_pin(sid)
                st.rerun()

    st.divider()
    # System Status
    st.session_state.failover_active = st.toggle("Local Failover Mode", value=st.session_state.get("failover_active", False))

# --- MAIN UI ---
current_session = memory_manager.sessions.get(st.session_state.session_id, {"messages": [], "title": "New Chat"})
st.title(f"🩺 {current_session['title']}")

# Display History from Memory Manager
for msg in current_session["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("How can I help you today?"):
    # Display user message
    st.chat_message("user").markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            # 1. Context Rewrite
            standalone_query = memory_manager.rewrite_query(st.session_state.session_id, prompt)
            history_str = memory_manager.get_history_string(st.session_state.session_id)
            
            # 2. Backend Call
            api_url = f"http://{SERVER_IP}:8000/{LAPTOP_CODE}/chat/{st.session_state.session_id}"
            try:
                payload = {
                    "question": standalone_query,
                    "history_summary": history_str,
                    "force_local": st.session_state.failover_active
                }
                response = requests.post(api_url, json=payload, timeout=60)
                answer = response.json().get("answer", "Error: No response from engine.")
                
                st.markdown(answer)
                
                # 3. Save to Persistent Memory
                memory_manager.add_turn(st.session_state.session_id, prompt, answer)
                
            except Exception as e:
                st.error(f"Connection Error: {e}")
