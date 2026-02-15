import streamlit as st
import requests
import uuid
from memorynvidia import memory_manager  # Import the frontend memory manager

# --- 1. CONFIGURATION ---
SERVER_IP = "127.0.0.1"  # Replace with your GPU Laptop's IP
LAPTOP_CODE = "STUDENT_LAPTOP_01" 

st.set_page_config(page_title="Medical Cognitive Engine", page_icon="🩺")

# Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "failover_active" not in st.session_state:
    st.session_state.failover_active = False

# --- 2. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ System Status")
    status_color = "🔴" if st.session_state.failover_active else "🟢"
    mode_text = "Local Failover" if st.session_state.failover_active else "NVIDIA Cloud"
    st.info(f"**Mode:** {status_color} {mode_text}")
    
    if st.button("🔄 Reset to Cloud Mode"):
        st.session_state.failover_active = False
        st.rerun()

    if st.button("🗑️ New Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

# --- 3. MAIN UI ---
st.title("🩺 Medical Cognitive Engine")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a medical question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # STEP A: REWRITE LOCALLY (using Frontend CPU/Ollama)
        with st.spinner("Processing context..."):
            original_query = prompt
            standalone_query = memory_manager.rewrite_query(st.session_state.session_id, prompt)
        
            # If the query was rewritten, it's now 'standalone'
            is_standalone = (standalone_query != original_query)
            current_history = memory_manager.get_history_string(st.session_state.session_id)
        
        # STEP B: CALL BACKEND
        mode = "chat" # FOR TESTING ONLY
        api_url = f"http://{SERVER_IP}:8000/{LAPTOP_CODE}/{mode}/{st.session_state.session_id}"
        
        try:
            payload = {
                "question": standalone_query,
                "history_summary": current_history if not is_standalone else "", # Clear history if standalone
                "is_standalone": is_standalone,
                "force_local": st.session_state.failover_active
            }
            response = requests.post(api_url, json=payload, timeout=120)
            data = response.json()
                
                # Check if Backend triggered a failover
                
            answer = data.get("answer")
            st.markdown(answer)
                
                # STEP C: UPDATE FRONTEND MEMORY
            memory_manager.add_turn(st.session_state.session_id, prompt, answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

        except Exception as e:
            st.error(f"Connection Error: {e}")
            st.warning("Check if the GPU Laptop is on the same Wi-Fi and the Backend is running.")