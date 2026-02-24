import streamlit as st
import requests
import uuid
import json
import os
from pathlib import Path
from memorynvidia import memory_manager

# --- CONFIG ---
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
AUTH_CACHE_FILE = Path(__file__).resolve().parent / ".auth_cache.json"

st.set_page_config(page_title="Medical Cognitive Engine", page_icon="🩺", layout="wide")


def clear_auth_state(clear_backend_sessions=True):
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.user = None
    if clear_backend_sessions:
        st.session_state.backend_sessions = {}
    st.session_state.show_login_popup = True


def _read_auth_cache():
    if not AUTH_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(AUTH_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_auth_cache(data):
    try:
        AUTH_CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def persist_auth_cookies():
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    user = st.session_state.get("user")

    if not access_token:
        clear_auth_cookies()
        return

    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }
    _write_auth_cache(payload)


def clear_auth_cookies():
    try:
        if AUTH_CACHE_FILE.exists():
            AUTH_CACHE_FILE.unlink()
    except OSError:
        pass


def restore_auth_from_cookies():
    if st.session_state.get("access_token"):
        return

    auth_cache = _read_auth_cache()
    access_token = auth_cache.get("access_token")
    refresh_token = auth_cache.get("refresh_token")
    user_raw = auth_cache.get("user")

    if not access_token:
        return

    st.session_state.access_token = access_token
    st.session_state.refresh_token = refresh_token
    if user_raw:
        st.session_state.user = user_raw
    st.session_state.show_login_popup = False


def auth_headers():
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def request_json(method, path, json_body=None, auth=False, timeout=30):
    url = f"{BACKEND_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if auth:
        headers.update(auth_headers())

    try:
        response = requests.request(method, url, json=json_body, headers=headers, timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Cannot reach backend at {BACKEND_BASE_URL}. "
            "Start ClinTrial backend with: cd clintrial-backend && npm run start"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Request to backend failed: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = None

    if response.status_code == 401 and auth:
        clear_auth_state(clear_backend_sessions=False)
        clear_auth_cookies()
        st.rerun()

    if response.status_code >= 400:
        if isinstance(body, dict):
            detail = body.get("error") or body.get("detail") or str(body)
        else:
            detail = response.text
        raise RuntimeError(f"{method} {path} failed ({response.status_code}): {detail}")

    return body if isinstance(body, dict) else {}


def is_backend_online(timeout=2):
    try:
        response = requests.get(f"{BACKEND_BASE_URL}/health", timeout=timeout)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def login_user(email, password):
    body = request_json("POST", "/auth/login", {"email": email, "password": password}, auth=False)
    tokens = body.get("tokens") or {}
    st.session_state.access_token = tokens.get("accessToken")
    st.session_state.refresh_token = tokens.get("refreshToken")
    st.session_state.user = body.get("user")
    st.session_state.show_login_popup = False
    persist_auth_cookies()


@st.dialog("Backend Login")
def login_popup():
    st.write("Login is required to continue.")
    login_email = st.text_input("Email", key="popup_login_email")
    login_password = st.text_input("Password", type="password", key="popup_login_password")

    if st.button("Login", key="popup_login_btn", use_container_width=True):
        try:
            login_user(login_email.strip(), login_password)
            st.rerun()
        except Exception as e:
            st.error(str(e))


def fetch_systems():
    body = request_json("GET", "/systems", auth=False)
    return body.get("systems", [])


def create_backend_consultation(system_id, difficulty):
    body = request_json(
        "POST",
        "/cases/select",
        {"systemId": system_id, "difficulty": difficulty},
        auth=True
    )
    backend_session = body.get("session", {})
    case_payload = body.get("case", {})
    backend_session_id = backend_session.get("id")
    if not backend_session_id:
        raise RuntimeError("Backend did not return a session id.")

    return {
        "backend_session_id": backend_session_id,
        "case": case_payload,
        "submitted": False
    }


def fetch_backend_session(backend_session_id):
    body = request_json("GET", f"/sessions/{backend_session_id}", auth=True)
    return body.get("session", {})


def hydrate_backend_mapping(local_session_id):
    existing = st.session_state.backend_sessions.get(local_session_id)
    if existing and existing.get("backend_session_id"):
        return existing

    local_session = memory_manager.sessions.get(local_session_id, {})
    metadata_backend_id = local_session.get("backend_session_id")
    metadata_case = local_session.get("case")

    candidate_ids = []
    if metadata_backend_id:
        candidate_ids.append(metadata_backend_id)
    if local_session_id != metadata_backend_id:
        candidate_ids.append(local_session_id)

    for candidate_id in candidate_ids:
        try:
            backend_session = fetch_backend_session(candidate_id)
            case_data = backend_session.get("case") or metadata_case or {}
            restored = {
                "backend_session_id": candidate_id,
                "case": case_data,
                "submitted": bool(backend_session.get("totalScore"))
            }
            st.session_state.backend_sessions[local_session_id] = restored
            memory_manager.update_session_meta(
                local_session_id,
                backend_session_id=candidate_id,
                case=case_data
            )
            return restored
        except Exception:
            continue

    if metadata_backend_id:
        restored = {
            "backend_session_id": metadata_backend_id,
            "case": metadata_case or {},
            "submitted": False
        }
        st.session_state.backend_sessions[local_session_id] = restored
        return restored

    return {}


def chat_backend(backend_session_id, message, force_local):
    body = request_json(
        "POST",
        f"/sessions/{backend_session_id}/chat",
        {"message": message, "forceLocal": force_local},
        auth=True,
        timeout=60
    )
    return body.get("reply") or "Error: No response from backend assistant."


def submit_case(backend_session_id, final_diagnosis, reasoning, management_plan, duration_seconds=0):
    return request_json(
        "POST",
        f"/sessions/{backend_session_id}/submit",
        {
            "finalDiagnosis": final_diagnosis,
            "reasoning": reasoning,
            "managementPlan": management_plan,
            "durationSeconds": duration_seconds
        },
        auth=True
    )

# Initialize Session ID if not present
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "backend_sessions" not in st.session_state:
    st.session_state.backend_sessions = {}
if "show_login_popup" not in st.session_state:
    st.session_state.show_login_popup = True
if "submit_case_panel_open" not in st.session_state:
    st.session_state.submit_case_panel_open = False
if "confirm_clear_history" not in st.session_state:
    st.session_state.confirm_clear_history = False

restore_auth_from_cookies()

if not st.session_state.access_token:
    if st.session_state.show_login_popup:
        login_popup()
    st.info("Please login to access consultations.")
    if st.button("Open login popup", key="reopen_login_popup", use_container_width=True):
        st.session_state.show_login_popup = True
        st.rerun()
    st.stop()

# --- SIDEBAR: CHAT HISTORY ---
with st.sidebar:
    st.title("📂 Medical History")

    if is_backend_online():
        st.success(f"Backend Online: {BACKEND_BASE_URL}")
    else:
        st.error(f"Backend Offline: {BACKEND_BASE_URL}")

    st.divider()

    st.subheader("Backend Login")
    user_email = (st.session_state.user or {}).get("email", "Logged in")
    st.success(f"Connected as {user_email}")
    if st.button("Switch Account", use_container_width=True):
        clear_auth_state()
        clear_auth_cookies()
        st.rerun()
    if st.button("Logout", use_container_width=True):
        clear_auth_state()
        clear_auth_cookies()
        st.rerun()

    st.divider()

    st.subheader("Case Setup")
    systems = []
    system_labels = []
    selected_system_id = None
    try:
        systems = fetch_systems()
        system_labels = [s["name"] for s in systems]
    except Exception as e:
        st.warning(f"Cannot load systems: {e}")

    if system_labels:
        selected_system_name = st.selectbox("System", options=system_labels)
        selected_system_id = next((s["id"] for s in systems if s["name"] == selected_system_name), None)
    else:
        st.selectbox("System", options=["No systems available"], disabled=True)

    selected_difficulty = st.selectbox("Difficulty", options=["EASY", "MEDIUM", "HARD"], index=1)
    
    if st.button("➕ New Consultation", use_container_width=True):
        if not st.session_state.access_token:
            st.error("Login first to start a backend consultation.")
        elif not selected_system_id:
            st.error("No system selected.")
        else:
            try:
                backend_data = create_backend_consultation(selected_system_id, selected_difficulty)
                new_id = backend_data["backend_session_id"]
                if new_id not in memory_manager.sessions:
                    memory_manager.create_new_session(new_id)
                memory_manager.update_session_meta(
                    new_id,
                    backend_session_id=backend_data["backend_session_id"],
                    case=backend_data.get("case") or {}
                )
                st.session_state.backend_sessions[new_id] = backend_data
                st.session_state.session_id = new_id
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start backend consultation: {e}")

    st.divider()

    # Get sorted sessions (Pinned first, then newest)
    sessions = memory_manager.get_session_list()

    for sid, data in sessions:
        # Create a row with columns for the Title and the Pin button
        col_title, col_pin, col_delete = st.columns([0.64, 0.16, 0.20])
        
        with col_title:
            is_active = st.session_state.session_id == sid
            label = f"{'⭐ ' if data.get('pinned') else ''}{data['title']}"
            
            if st.button(label, key=f"sel_{sid}", use_container_width=True, 
                         type="primary" if is_active else "secondary"):
                st.session_state.session_id = sid
                hydrate_backend_mapping(sid)
                st.rerun()
        
        with col_pin:
            pin_label = "📌" if data.get("pinned") else "📍"
            if st.button(pin_label, key=f"pin_{sid}", help="Pin to top"):
                memory_manager.toggle_pin(sid)
                st.rerun()

        with col_delete:
            if st.button("🗑️", key=f"del_{sid}", help="Delete this history"):
                memory_manager.delete_session(sid)
                st.session_state.backend_sessions.pop(sid, None)

                if st.session_state.session_id == sid:
                    remaining = memory_manager.get_session_list()
                    if remaining:
                        st.session_state.session_id = remaining[0][0]
                    else:
                        fresh_id = str(uuid.uuid4())
                        memory_manager.create_new_session(fresh_id)
                        st.session_state.session_id = fresh_id

                st.rerun()

    if not st.session_state.confirm_clear_history:
        if st.button("🗑️ Clear All History", use_container_width=True):
            st.session_state.confirm_clear_history = True
            st.rerun()
    else:
        st.warning("Confirm delete all history?")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("✅ Yes, clear all", use_container_width=True):
                memory_manager.clear_all_sessions()
                st.session_state.backend_sessions = {}
                fresh_id = str(uuid.uuid4())
                memory_manager.create_new_session(fresh_id)
                st.session_state.session_id = fresh_id
                st.session_state.confirm_clear_history = False
                st.rerun()
        with cancel_col:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.confirm_clear_history = False
                st.rerun()

    st.divider()
    # System Status
    st.session_state.failover_active = st.toggle("Local Failover Mode", value=st.session_state.get("failover_active", False))

# --- MAIN UI ---
if st.session_state.session_id not in memory_manager.sessions:
    memory_manager.create_new_session(st.session_state.session_id)

hydrate_backend_mapping(st.session_state.session_id)
current_session = memory_manager.sessions.get(st.session_state.session_id, {"messages": [], "title": "New Chat"})
st.title(f"🩺 {current_session['title']}")

st.markdown(
    """
    <style>
    .st-key-toggle_submit_case_panel {
        position: fixed;
        right: 1rem;
        top: 5.5rem;
        width: auto;
        z-index: 999;
    }
    .st-key-toggle_submit_case_panel button {
        background-color: #22c55e !important;
        color: white !important;
        border: none !important;
        border-radius: 999px !important;
        min-height: 3rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
    }
    .st-key-submit_case_panel,
    .st-key-submit_case_form {
        position: fixed !important;
        right: 1rem;
        top: 9.5rem;
        width: min(360px, 32vw);
        max-height: calc(100vh - 11rem);
        overflow-y: auto;
        z-index: 998;
    }
    .st-key-submit_case_panel {
        background: var(--background-color);
        padding: 0.75rem;
        border-radius: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if st.button("🟢 Submit Diagnosis", key="toggle_submit_case_panel", help="Submit Diagnosis"):
    st.session_state.submit_case_panel_open = not st.session_state.submit_case_panel_open
    st.rerun()

active_backend = st.session_state.backend_sessions.get(st.session_state.session_id, {})
case_info = active_backend.get("case") or {}
if case_info:
    st.caption(
        f"Case: {case_info.get('chiefComplaint', 'N/A')} | "
        f"Age {case_info.get('age', 'N/A')} | {case_info.get('gender', 'N/A')} | "
        f"Difficulty {case_info.get('difficulty', 'N/A')}"
    )
else:
    st.info("Start a new consultation from the sidebar to open a backend case session.")

chat_col, submit_col = st.columns([0.72, 0.28])

with chat_col:
    # Display History from Memory Manager
    for msg in current_session["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

with submit_col:
    if st.session_state.submit_case_panel_open:
        with st.container(key="submit_case_panel"):
            st.subheader("Submit Diagnosis")
            active_backend = st.session_state.backend_sessions.get(st.session_state.session_id, {})
            active_backend_session_id = active_backend.get("backend_session_id")

            with st.form("submit_case_form", clear_on_submit=False):
                final_dx = st.text_input("Final diagnosis", key="final_dx")
                reasoning = st.text_area("Reasoning", key="final_reasoning", height=100)
                management_plan = st.text_area("Management plan", key="final_management", height=100)
                submit_clicked = st.form_submit_button("Submit Session", use_container_width=True)

            if submit_clicked:
                if not st.session_state.access_token:
                    st.error("Login first.")
                elif not active_backend_session_id:
                    st.error("Start a consultation first.")
                elif not final_dx.strip():
                    st.error("Final diagnosis is required.")
                else:
                    try:
                        submission = submit_case(
                            active_backend_session_id,
                            final_dx.strip(),
                            reasoning.strip(),
                            management_plan.strip(),
                            0
                        )
                        scores = submission.get("scores", {})
                        total_score = scores.get("totalScore", 0)
                        st.success(f"Submitted. Total score: {total_score:.2f}")
                        active_backend["submitted"] = True
                        st.session_state.backend_sessions[st.session_state.session_id] = active_backend
                    except Exception as e:
                        st.error(f"Submit failed: {e}")

# Chat Input
if prompt := st.chat_input("How can I help you today?"):
    if not st.session_state.access_token:
        st.error("Login first in sidebar.")
        st.stop()

    active_backend = hydrate_backend_mapping(st.session_state.session_id)
    backend_session_id = active_backend.get("backend_session_id")
    if not backend_session_id:
        if not selected_system_id:
            st.error("No system selected. Pick a system in the sidebar.")
            st.stop()
        try:
            bootstrapped = create_backend_consultation(selected_system_id, selected_difficulty)
            st.session_state.backend_sessions[st.session_state.session_id] = bootstrapped
            memory_manager.update_session_meta(
                st.session_state.session_id,
                backend_session_id=bootstrapped["backend_session_id"],
                case=bootstrapped.get("case") or {}
            )
            active_backend = bootstrapped
            backend_session_id = bootstrapped.get("backend_session_id")
            st.info("Created a backend consultation for this history.")
        except Exception as e:
            st.error(f"Failed to create consultation: {e}")
            st.stop()

    try:
        fetch_backend_session(backend_session_id)
    except Exception:
        if not selected_system_id:
            st.error("This session is no longer available. Pick a system and start a new consultation.")
            st.stop()
        try:
            bootstrapped = create_backend_consultation(selected_system_id, selected_difficulty)
            st.session_state.backend_sessions[st.session_state.session_id] = bootstrapped
            memory_manager.update_session_meta(
                st.session_state.session_id,
                backend_session_id=bootstrapped["backend_session_id"],
                case=bootstrapped.get("case") or {}
            )
            active_backend = bootstrapped
            backend_session_id = bootstrapped.get("backend_session_id")
            st.info("Previous backend session expired. Started a new consultation for this history.")
        except Exception as e:
            st.error(f"Failed to recover consultation: {e}")
            st.stop()

    # Display user message
    with chat_col:
        st.chat_message("user").markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                # 1. Context Rewrite
                standalone_query = memory_manager.rewrite_query(st.session_state.session_id, prompt)

                try:
                    # 2. Backend Call (Node API -> Python assistant proxy)
                    answer = chat_backend(
                        backend_session_id=backend_session_id,
                        message=standalone_query,
                        force_local=st.session_state.failover_active
                    )

                    st.markdown(answer)

                    # 3. Save to Persistent Memory
                    memory_manager.add_turn(st.session_state.session_id, prompt, answer)

                except Exception as e:
                    st.error(f"Connection Error: {e}")
