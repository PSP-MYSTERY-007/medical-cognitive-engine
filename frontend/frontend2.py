import streamlit as st
import pandas as pd
import numpy as np
import time
import uuid
import requests
from memorynvidia import memory_manager # Ensure this file is in your directory
from datetime import datetime, date

# --- BACKEND CONFIG ---
SERVER_IP = "127.0.0.1"
LAPTOP_CODE = "STUDENT_LAPTOP_01"

# ==============================
# PAGE CONFIGURATION
# ==============================
st.set_page_config(
    page_title="ClinTrial AI | Medical OSCE",
    page_icon="🫀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================
# GLOBAL CSS
# ==============================
st.markdown("""
<style>
    /* Main Background */
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at top right, #1e293b, #0f172a, #020617);
        color: white;
    }
    
    /* Sidebar Style */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b3f33, #0f172a);
        border-right: 1px solid rgba(148, 163, 184, 0.2);
    }

    section[data-testid="stSidebar"] > div {
        background:
            radial-gradient(circle at 100% 0%, rgba(14, 165, 233, 0.22), transparent 42%),
            radial-gradient(circle at 0% 20%, rgba(20, 184, 166, 0.2), transparent 42%);
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    .sidebar-brand {
        background: rgba(255, 255, 255, 0.07);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 14px;
        box-shadow: 0 10px 24px rgba(2, 6, 23, 0.34);
    }

    .sidebar-brand-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #e0f2fe;
        letter-spacing: 0.25px;
    }

    .sidebar-brand-sub {
        margin-top: 3px;
        font-size: 0.8rem;
        color: #99f6e4;
    }

    section[data-testid="stSidebar"] .stButton > button {
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.16);
        background: rgba(255, 255, 255, 0.06);
        color: #f8fafc;
        box-shadow: 0 6px 14px rgba(0, 0, 0, 0.22);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: rgba(14, 165, 233, 0.55);
        box-shadow: 0 10px 18px rgba(2, 6, 23, 0.35);
        transform: translateY(-1px);
    }

    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #14b8a6, #0ea5e9);
        border-color: rgba(255, 255, 255, 0.25);
        font-weight: 700;
    }

    /* User Profile Card */
    .user-profile {
        background: linear-gradient(135deg, rgba(20, 184, 166, 0.85), rgba(37, 99, 235, 0.85));
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 20px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 8px 18px rgba(2, 6, 23, 0.34);
    }

    /* Glass Cards */
    .glass {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(15px);
        border-radius: 15px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }

    /* History Container Hover */
    .history-item {
        padding: 2px;
        border-radius: 8px;
        transition: 0.3s;
    }
    .history-item:hover {
        background: rgba(255, 255, 255, 0.1);
    }

    /* Chat Watermark */
    .watermark {
        position: fixed;
        top: 45%;
        left: 55%;
        transform: translate(-50%, -50%);
        text-align: center;
        opacity: 0.2;
        pointer-events: none;
        z-index: 0;
    }

    /* Chat Bubble Alignment */
    [data-testid="stChatMessage"]:nth-child(even) {
        flex-direction: row-reverse !important;
        text-align: right !important;
    }
    
    .floating-ama-container {
        position: fixed;
        bottom: 20px;
        right: 20px;
        top: 40px;
        z-index: 999;
    }
    
    .ama-button {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #6366f1, #a855f7);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        cursor: pointer;
        border: 2px solid rgba(255,255,255,0.2);
        transition: transform 0.3s ease;
    }
    
    .ama-button:hover {
        transform: scale(1.1);
    }

    .osce-hero {
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.24), rgba(20, 184, 166, 0.2));
        border: 1px solid rgba(148, 163, 184, 0.3);
        border-radius: 16px;
        padding: 22px;
        margin-top: 20px;
        margin-bottom: 16px;
        box-shadow: 0 12px 28px rgba(2, 6, 23, 0.3);
    }

    .osce-hero h1 {
        margin: 0;
        font-size: 1.85rem;
        color: #e2e8f0;
    }

    .osce-hero p {
        margin: 6px 0 0 0;
        color: #cbd5e1;
    }

    .osce-metric-card {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.13);
        border-radius: 14px;
        padding: 14px 16px;
        min-height: 108px;
        box-shadow: 0 8px 20px rgba(2, 6, 23, 0.28);
        backdrop-filter: blur(10px);
    }

    .osce-metric-label {
        color: #94a3b8;
        font-size: 0.85rem;
    }

    .osce-metric-value {
        margin-top: 6px;
        color: #f8fafc;
        font-size: 1.68rem;
        font-weight: 700;
        line-height: 1.1;
    }

    .osce-metric-delta {
        margin-top: 8px;
        color: #5eead4;
        font-size: 0.9rem;
        font-weight: 600;
    }

    .osce-section-title {
        margin: 2px 0 12px 0;
        color: #e2e8f0;
        letter-spacing: 0.2px;
    }

    .osce-chart-shell {
        margin-top: 14px;
        border-top: 1px solid rgba(148, 163, 184, 0.2);
        padding-top: 14px;
    }

    .osce-system-tile {
        text-align: center;
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.9), rgba(37, 99, 235, 0.9));
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 14px;
        padding: 16px 12px;
        margin-bottom: 8px;
        box-shadow: 0 10px 20px rgba(2, 6, 23, 0.3);
    }

    .osce-system-icon {
        font-size: 38px;
        margin-bottom: 4px;
    }

    .osce-system-name {
        color: #f8fafc;
        font-size: 1.08rem;
        font-weight: 700;
        margin: 0;
    }

    .osce-system-sub {
        color: #dbeafe;
        font-size: 0.82rem;
        margin-top: 4px;
    }

</style>
""", unsafe_allow_html=True)

# ==============================
# SESSION STATE
# ==============================
sessions_list = list(memory_manager.sessions.keys())
if "session_id" not in st.session_state:
    if sessions_list:
        st.session_state.session_id = sessions_list[0] # Load last session
    else:
        # Only create one if the file is totally empty
        new_id = str(uuid.uuid4())
        memory_manager.create_new_session(new_id)
        st.session_state.session_id = new_id
    
if "active_page" not in st.session_state: st.session_state.active_page = "ChatAI"
if "show_ama" not in st.session_state: st.session_state.show_ama = False
if "selected_system" not in st.session_state: st.session_state.selected_system = None
if "in_case" not in st.session_state: st.session_state.in_case = False
if "ai_busy" not in st.session_state: st.session_state.ai_busy = False
if "difficulty" not in st.session_state: st.session_state.difficulty = "Medium"

# ==============================
# HELPER: CIRCULAR PROGRESS
# ==============================
def render_circle_progress(label, percent, color="#14b8a6"):
    size = 110
    return f"""
    <div style="text-align:center; padding:5px;">
        <svg width="{size}" height="{size}" viewBox="0 0 36 36">
            <path stroke="#334155" stroke-width="3" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
            <path stroke="{color}" stroke-width="3" stroke-dasharray="{percent}, 100" stroke-linecap="round" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
            <text x="18" y="20.5" text-anchor="middle" font-family="sans-serif" font-size="7" font-weight="700" fill="white">{percent}%</text>
        </svg>
        <div style="margin-top:5px; font-size:11px; color:#cbd5e1;">{label}</div>
    </div>
    """

# 1. Ensure this is in your SESSION STATE section at the top
if "ama_messages" not in st.session_state:
    st.session_state.ama_messages = []

# 2. Update the function
def floating_ama():
    _, col_btn = st.columns([8, 1])
    
    with col_btn:
        with st.popover("💡 AMA...", use_container_width=True):
            st.markdown("### 🤖 Clinical Assistant")
            st.caption("Ask about protocols, red flags, or guidelines.")
            
            # Scrollable area for AMA chat
            ama_container = st.container(height=300)
            
            # Display current AMA history
            for m in st.session_state.ama_messages:
                ama_container.chat_message(m["role"]).write(m["content"])
            
            if p := st.chat_input("Ask a medical doubt...", key="ama_input_active"):
                # 1. Add User message to state
                st.session_state.ama_messages.append({"role": "user", "content": p})
                
                # 2. Call Backend (Using a distinct AMA session ID)
                # We append "_AMA" to the session ID so the backend 
                # treats it as a separate thread from the main consultation
                ama_session_id = f"{st.session_state.session_id}_AMA"
                api_url = f"http://{SERVER_IP}:8000/{LAPTOP_CODE}/chat/{ama_session_id}"
                
                try:
                    # Construct a specialized prompt for the AMA
                    payload = {
                        "question": f"ACT AS A CLINICAL SUPERVISOR. Provide a concise, protocol-based answer to: {p}",
                        "history_summary": "", # Keep AMA context light
                        "force_local": st.session_state.failover_active
                    }
                    
                    response = requests.post(api_url, json=payload, timeout=30)
                    answer = response.json().get("answer", "I'm having trouble connecting to the clinical engine.")
                    
                    # 3. Add Assistant response to state
                    st.session_state.ama_messages.append({"role": "assistant", "content": answer})
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"AMA Error: {e}")

def navigate_to(page_name):
    st.session_state.active_page = page_name

def get_date_category(timestamp):
    msg_date = datetime.fromtimestamp(timestamp).date()
    today = date.today()
    delta = (today - msg_date).days
    
    if delta == 0: return "Today"
    if delta == 1: return "Yesterday"
    return "Previous Days"

def render_session_row(sid, data):
    # Create three columns: Title (wide), Pin (narrow), Delete (narrow)
    col_title, col_pin, col_del = st.sidebar.columns([0.65, 0.17, 0.17])
    
    with col_title:
        is_active = st.session_state.get("session_id") == sid
        # Truncate title if it's too long for the sidebar
        display_title = data['title'] if len(data['title']) < 20 else data['title'][:17] + "..."
        
        if st.button(display_title, key=f"sel_{sid}", use_container_width=True, 
                     type="primary" if is_active else "secondary"):
            st.session_state.session_id = sid
            st.rerun()
            
    with col_pin:
        pin_label = "📌" if data.get("pinned") else "📍"
        if st.button(pin_label, key=f"pin_{sid}", help="Pin Chat"):
            memory_manager.toggle_pin(sid)
            st.rerun()
            
    with col_del:
        if st.button("🗑️", key=f"del_{sid}", help="Delete Chat"):
            memory_manager.delete_session(sid)
            if st.session_state.get("session_id") == sid:
                st.session_state.session_id = None
            st.rerun()


# ==============================
# SIDEBAR
# ==============================
with st.sidebar:
    st.markdown(
        """<div class="sidebar-brand">
                <div class="sidebar-brand-title">🫀 ClinTrial AI</div>
                <div class="sidebar-brand-sub">Medical OSCE Command Center</div>
            </div>""",
        unsafe_allow_html=True
    )
    st.markdown(f"""<div class="user-profile">
                <small>User Profile</small><br>
                <b>Dr. Praveen</b><br>
                <small>Senior Registrar</small>
                </div>
                """, unsafe_allow_html=True)

    # 1. Page Navigation
    chat_type = "primary" if st.session_state.active_page == "ChatAI" else "secondary"
    if st.button("💬 AI Chatbox", use_container_width=True, type=chat_type):
        st.session_state.active_page = "ChatAI"
        st.rerun()

    osce_type = "primary" if st.session_state.active_page == "OSCE" else "secondary"
    if st.button("🩺 OSCE Dashboard", use_container_width=True, type=osce_type):
        st.session_state.active_page = "OSCE"
        st.rerun()

    st.divider()

    # ==============================
    # MODE-SPECIFIC SIDEBAR CONTENT
    # ==============================
    
    if st.session_state.active_page == "ChatAI":
        st.subheader("Consultations")

        if st.button("➕ New Consultation", use_container_width=True):
            new_id = str(uuid.uuid4())
            memory_manager.create_new_session(new_id)
            st.session_state.session_id = new_id
            # RESET AMA ON NEW SESSION
            st.session_state.ama_messages = [] 
            st.rerun()

        # 2. History Loop (Using the helper function you defined earlier)
        all_sessions = memory_manager.get_session_list()
        pinned_sessions = [s for s in all_sessions if s[1].get("pinned")]
        unpinned_sessions = [s for s in all_sessions if not s[1].get("pinned")]

        if pinned_sessions:
            st.caption("PINNED")
            for sid, data in pinned_sessions:
                render_session_row(sid, data)

        current_group = None
        for sid, data in unpinned_sessions:
            session_group = get_date_category(data.get("timestamp", 0))
            if session_group != current_group:
                st.caption(session_group)
                current_group = session_group
            
            # This one line replaces all the manual column code you had
            render_session_row(sid, data)

        st.divider()
        st.session_state.failover_active = st.toggle("Local Failover Mode", value=st.session_state.get("failover_active", False))

    else:
        # --- OSCE MODE SIDEBAR ---
        st.subheader("OSCE Training")
        
        # Dashboard Option
        if st.button("📊 Training Overview", use_container_width=True, 
                     type="primary" if not st.session_state.get("osce_subpage") else "secondary"):
            st.session_state.osce_subpage = None # Reset to main dashboard
            st.rerun()
            
        # Leaderboard Option
        if st.button("🏆 Global Leaderboard", use_container_width=True,
                     type="primary" if st.session_state.get("osce_subpage") == "Leaderboard" else "secondary"):
            st.session_state.osce_subpage = "Leaderboard"
            st.rerun()

        # Analytics Option
        if st.button("📈 Performance Analytics", use_container_width=True,
                     type="primary" if st.session_state.get("osce_subpage") == "Analytics" else "secondary"):
            st.session_state.osce_subpage = "Analytics"
            st.rerun()
            
        st.divider()
        st.info("💡 Tip: Complete 3 Cardiology cases to unlock the 'Senior Registrar' badge.")

# ==============================
# PAGE: CHAT (Lovable Style)
# ==============================
def render_chat():
    # --- Integration with Memory Manager ---
    # Retrieve current session data from memory_manager using the session_id
    current_session = memory_manager.sessions.get(st.session_state.session_id, {"messages": [], "title": "New Chat"})
    messages = current_session["messages"]

    st.title(f"🩺 {current_session['title']}")

    # --- WATERMARK LOGIC (Corrected Condition) ---
    if not messages:
        st.markdown(f"""
            <div class="watermark">
                <h2 style="margin:0;">Clinical Assistant Intelligent Decision Support</h2>
                <p style="font-size: 1.2rem;">Hi Dr Praveen, how may i help you today?</p>
            </div>
        """, unsafe_allow_html=True)

    # Display History
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if prompt := st.chat_input("How can I help you today?"):
        # 1. Immediately add user message to the UI to trigger the watermark disappearance
        st.chat_message("user").markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                standalone_query = memory_manager.rewrite_query(st.session_state.session_id, prompt)
                history_str = memory_manager.get_history_string(st.session_state.session_id)
                
                api_url = f"http://{SERVER_IP}:8000/{LAPTOP_CODE}/chat/{st.session_state.session_id}"
                try:
                    payload = {
                        "question": standalone_query,
                        "history_summary": history_str,
                        "force_local": st.session_state.failover_active
                    }
                    response = requests.post(api_url, json=payload, timeout=60)
                    answer = response.json().get("answer", "Error: No response from engine.")
                    
                    placeholder = st.empty()
                    typed = ""
                    for char in answer:
                        typed += char
                        placeholder.markdown(typed + "▌")
                        time.sleep(0.005)
                    placeholder.markdown(typed)
                    
                    # 2. Save to Memory
                    memory_manager.add_turn(st.session_state.session_id, prompt, answer)
                    
                    # 3. FORCE RERUN to clear watermark and update state
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# ==============================
# PAGE: OSCE DASHBOARD (Your Original Style)
# ==============================
def render_osce():
    if st.session_state.in_case:
        render_case_simulation()
    elif st.session_state.selected_system:
        render_system_detail()
    else:
        st.markdown('''
            <div class="osce-hero">
                <h1>Welcome back, Dr. Praveen</h1>
                <p>Continue your OSCE training journey with focused practice and real-time feedback.</p>
            </div>
        ''', unsafe_allow_html=True)
        
        # Original Metrics
        c1, c2, c3, c4 = st.columns(4)
        m_list = [("Total Sessions", "160", "12%"), ("Clinical Score", "74%", "5%"), ("Current Rank", "Registrar", "Lvl 3"), ("Current Streak", "7 Days", "3%")]
        for col, (lab, val, det) in zip([c1, c2, c3, c4], m_list):
            with col:
                st.markdown(f'''
                    <div class="osce-metric-card">
                        <div class="osce-metric-label">{lab}</div>
                        <div class="osce-metric-value">{val}</div>
                        <div class="osce-metric-delta">↑ {det}</div>
                    </div>
                ''', unsafe_allow_html=True)

        # Original Competency Overview
        st.markdown('<div class="glass" style="margin-top:20px;">', unsafe_allow_html=True)
        st.markdown('<h3 class="osce-section-title">Clinical Competency Overview</h3>', unsafe_allow_html=True)
        gauges = [("Overall Competency", 74, "#14b8a6"), ("History Taking", 82, "#10b981"), ("Diagnostic Accuracy", 68, "#06b6d4"), ("Clinical Reasoning", 71, "#0ea5e9"), ("Management", 76, "#0891b2")]
        g_cols = st.columns([1.5, 1, 1, 1, 1])
        for col, (lab, val, colr) in zip(g_cols, gauges):
            with col: st.markdown(render_circle_progress(lab, val, colr), unsafe_allow_html=True)

        st.markdown('<div class="osce-chart-shell">', unsafe_allow_html=True)
        st.line_chart(pd.DataFrame({"Score": [42, 55, 62, 72, 82]}), color="#14b8a6")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # System Grid
        st.markdown('<h3 class="osce-section-title">Select Medical System</h3>', unsafe_allow_html=True)
        systems = {"Cardiology": "❤️", "Respiratory": "🫁", "Neurology": "🧠", "Gastro": "🩺", "Orthopedics": "🦴", "Dermatology": "🧴"}
        sys_items = list(systems.items())
        for i in range(0, len(sys_items), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(sys_items):
                    name, icon = sys_items[i+j]
                    with cols[j]:
                        st.markdown(f'''
                            <div class="osce-system-tile">
                                <div class="osce-system-icon">{icon}</div>
                                <h3 class="osce-system-name">{name}</h3>
                                <div class="osce-system-sub">Simulation • Assessment • Feedback</div>
                            </div>
                        ''', unsafe_allow_html=True)
                        if st.button(f"Enter {name} System", key=f"btn_{name}", use_container_width=True):
                            st.session_state.selected_system = name
                            st.rerun()

# ==============================
# PAGE: SYSTEM DETAIL (Lovable Style)
# ==============================
def render_system_detail():
    sys = st.session_state.selected_system
    st.button("⬅ Back", on_click=lambda: setattr(st.session_state, 'selected_system', None))
    
    st.title(f"{sys} System Detail")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="glass"><h3>Skills breakdown</h3>', unsafe_allow_html=True)
        skills = {"History taking": 85, "Diagnosis accuracy": 70, "Clinical reasoning": 75, "Management": 80}
        for s, v in skills.items():
            st.write(f"{s}: {v}%")
            st.progress(v/100)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with c2:
        st.markdown('<div class="glass" style="text-align:center;">', unsafe_allow_html=True)
        st.markdown(render_circle_progress("System Mastery", 78, "#10b981"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="glass" style="text-align:center;"><h3>Start New Case Simulation</h3>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    if d1.button("🟢 Easy", use_container_width=True): 
        st.session_state.difficulty = "Easy"; st.session_state.in_case = True; st.rerun()
    if d2.button("🟡 Medium", use_container_width=True): 
        st.session_state.difficulty = "Medium"; st.session_state.in_case = True; st.rerun()
    if d3.button("🔴 Hard", use_container_width=True): 
        st.session_state.difficulty = "Hard"; st.session_state.in_case = True; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Disease Breakdown")
    st.table(pd.DataFrame({"Disease": ["ACS", "Heart Failure", "Pericarditis"], "Accuracy": ["88%", "72%", "65%"], "Status": ["Strong", "Moderate", "Weak"]}))

# ==============================
# PAGE: CASE SIMULATION
# ==============================
def render_case_simulation():
    # Floating AMA logic

    st.markdown(f"### OSCE Session: {st.session_state.selected_system} ({st.session_state.difficulty})")
    floating_ama()
    
    col_chat, col_notes = st.columns([1, 1])
    
    with col_chat:
        # Create a container with a fixed height to act as your "box"
        with st.container(height=500, border=True):
            # Message history
            st.chat_message("assistant").write("Hello doctor, I've been feeling quite short of breath lately...")
            
            # Example of how you'd loop through session state messages:
            # for msg in st.session_state.messages:
            #     st.chat_message(msg["role"]).write(msg["content"])

        # Placing the input immediately after the container keeps it in the column
        if prompt := st.chat_input("Talk to the patient..."):
            # Logic to handle the message
            pass

    with col_notes:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        tabs = st.tabs(["📝 History", "📝 Differential diagnosis", "🔬 Investigations", "📑 Management"])
        with tabs[0]: st.text_area("Patient History Notes", height=300)
        with tabs[1]: st.text_area("Differential diagnosis", height=300)
        with tabs[2]: st.text_area("Ordered Investigations", height=300)
        with tabs[3]: st.text_area("Management Plan", height=300)
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================
# ROUTER
# ==============================
if st.session_state.active_page == "ChatAI":
    render_chat()
else:
    render_osce()
