import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import time
import uuid
import json
from pathlib import Path
import requests
from memorynvidia import (
    memory_manager,
) # Ensure this file is in your directory
from osce_chatbot import (
    GENERAL_VITAL_OPTIONS,
    init_case_workflow_state as init_case_workflow_state_core,
    render_history_results_card as render_history_results_card_core,
    resolve_vital_value as resolve_vital_value_core,
    render_exam_results_card as render_exam_results_card_core,
    build_case_scoped_reply as build_case_scoped_reply_core,
)
from datetime import datetime, date

# --- BACKEND CONFIG ---
SERVER_IP = "127.0.0.1"
LAPTOP_CODE = "STUDENT_LAPTOP_01"
BACKEND_BASE_URL = "http://127.0.0.1:3000"
UI_STATE_FILE = Path(__file__).resolve().parent / ".ui_state.json"

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
        background:
            linear-gradient(135deg, rgba(14, 165, 233, 0.16), rgba(20, 184, 166, 0.12)),
            linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.01));
        border: 1px solid rgba(148, 163, 184, 0.3);
        border-radius: 16px;
        padding: 22px;
        margin-top: 20px;
        margin-bottom: 16px;
        box-shadow: 0 8px 20px rgba(2, 6, 23, 0.24);
        position: relative;
    }

    .osce-hero-top {
        display: flex;
        align-items: flex-start;
        justify-content: flex-start;
        gap: 10px;
        flex-wrap: wrap;
        padding-right: 210px;
    }

    .osce-hero-copy {
        min-width: 260px;
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
        background: linear-gradient(160deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03));
        border: 1px solid rgba(255, 255, 255, 0.13);
        border-radius: 14px;
        padding: 14px 16px;
        min-height: 108px;
        box-shadow: 0 6px 16px rgba(2, 6, 23, 0.22);
        backdrop-filter: blur(10px);
    }

    .osce-competency-panel {
        background:
            linear-gradient(180deg, rgba(14, 165, 233, 0.08), rgba(15, 23, 42, 0.08)),
            rgba(255, 255, 255, 0.05);
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
        padding: 14px 10px 2px 10px;
        border-radius: 12px;
        background: linear-gradient(180deg, rgba(14, 165, 233, 0.06), rgba(2, 6, 23, 0));
    }

    .osce-system-tile {
        text-align: center;
        background: linear-gradient(145deg, rgba(14, 165, 233, 0.68), rgba(37, 99, 235, 0.68));
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 14px;
        padding: 16px 12px;
        margin-bottom: 8px;
        box-shadow: 0 8px 18px rgba(2, 6, 23, 0.24);
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

    .osce-countdown {
        position: absolute;
        top: 16px;
        right: 16px;
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 12px 16px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.18), rgba(20, 184, 166, 0.16));
        box-shadow: 0 6px 16px rgba(2, 6, 23, 0.22);
        backdrop-filter: blur(8px);
        color: #f8fafc;
        font-size: 1.02rem;
        font-weight: 600;
        letter-spacing: 0.2px;
        min-width: 178px;
    }

    .osce-countdown-icon {
        font-size: 2rem;
        line-height: 1;
        margin-top: 1px;
    }

    .osce-countdown-text {
        display: flex;
        flex-direction: column;
        line-height: 1.05;
    }

    .osce-countdown-days {
        font-size: 1.55rem;
        font-weight: 800;
        color: #ffffff;
        line-height: 1;
    }

    .osce-countdown-label {
        margin-top: 6px;
        font-size: 0.95rem;
        font-weight: 600;
        color: #dbeafe;
    }

</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    .st-key-back_system_detail,
    .st-key-back_case_sim {
        position: fixed;
        top: 78px;
        left: 290px;
        z-index: 3000;
        width: auto;
        pointer-events: auto !important;
    }

    .st-key-back_system_detail button,
    .st-key-back_case_sim button {
        background: linear-gradient(135deg, #14b8a6, #0ea5e9) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-radius: 999px !important;
        font-weight: 700 !important;
        padding: 0.45rem 0.95rem !important;
        box-shadow: 0 8px 18px rgba(2, 6, 23, 0.35) !important;
    }

    .st-key-back_system_detail button:hover,
    .st-key-back_case_sim button:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 20px rgba(2, 6, 23, 0.4) !important;
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
if "selected_system_id" not in st.session_state: st.session_state.selected_system_id = None
if "selected_case" not in st.session_state: st.session_state.selected_case = None
if "in_case" not in st.session_state: st.session_state.in_case = False
if "ai_busy" not in st.session_state: st.session_state.ai_busy = False
if "difficulty" not in st.session_state: st.session_state.difficulty = "Medium"
if "osce_case_messages" not in st.session_state: st.session_state.osce_case_messages = {}
if "case_differential_note" not in st.session_state: st.session_state.case_differential_note = ""
if "case_investigation_note" not in st.session_state: st.session_state.case_investigation_note = ""
if "case_management_note" not in st.session_state: st.session_state.case_management_note = ""
if "case_notes_hint" not in st.session_state: st.session_state.case_notes_hint = None
if "osce_case_workflow" not in st.session_state: st.session_state.osce_case_workflow = {}
if "ui_state_restored" not in st.session_state: st.session_state.ui_state_restored = False
if "case_active_panel" not in st.session_state: st.session_state.case_active_panel = "History"
if "focus_chat_input" not in st.session_state: st.session_state.focus_chat_input = False


def load_ui_state():
    if not UI_STATE_FILE.exists():
        return {}
    try:
        return json.loads(UI_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_ui_state():
    payload = {
        "active_page": st.session_state.get("active_page", "ChatAI"),
        "selected_system": st.session_state.get("selected_system"),
        "selected_system_id": st.session_state.get("selected_system_id"),
        "selected_case": st.session_state.get("selected_case"),
        "in_case": st.session_state.get("in_case", False),
        "difficulty": st.session_state.get("difficulty", "Medium"),
        "osce_subpage": st.session_state.get("osce_subpage")
    }
    try:
        UI_STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def restore_ui_state_once():
    if st.session_state.ui_state_restored:
        return
    cached = load_ui_state()
    if not isinstance(cached, dict) or not cached:
        st.session_state.ui_state_restored = True
        return

    for key in ["active_page", "selected_system", "selected_system_id", "selected_case", "in_case", "difficulty", "osce_subpage"]:
        if key in cached:
            st.session_state[key] = cached.get(key)
    st.session_state.ui_state_restored = True


restore_ui_state_once()


def get_patient_name(case_item):
    return "Sara"


def get_door_note(case_item):
    patient_name = get_patient_name(case_item)
    age = case_item.get("age", "N/A")
    gender = case_item.get("gender", "N/A")
    complaint = case_item.get("chiefComplaint", "Not specified")
    clinic = "Outpatient Clinic"
    return {
        "name": patient_name,
        "age": age,
        "gender": gender,
        "clinic": clinic,
        "chief_complaint": complaint
    }


def request_backend_json(method, path, json_body=None, timeout=15):
    url = f"{BACKEND_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    response = requests.request(method, url, json=json_body, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def fetch_backend_systems():
    try:
        body = request_backend_json("GET", "/systems")
        return body.get("systems", [])
    except Exception:
        return []


def fetch_cardiology_medical_cases(selected_difficulty):
    difficulty_map = {
        "Easy": "easy",
        "Medium": "medium",
        "Hard": "hard"
    }
    normalized = str(selected_difficulty or "").strip()
    mapped = difficulty_map.get(normalized) or (normalized.lower() if normalized else None)
    query = f"?difficulty={mapped}" if mapped else ""
    paths = [
        f"/cases/medical-cases{query}",
        f"/medical-cases{query}"
    ]

    non_404_errors = []
    for path in paths:
        try:
            body = request_backend_json("GET", path)
            return body.get("medicalCases", [])
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            if status_code == 404:
                continue
            non_404_errors.append(e)
        except Exception as e:
            non_404_errors.append(e)

    if non_404_errors:
        raise non_404_errors[-1]

    return []


def format_difficulty_symbol(difficulty_value):
    value = str(difficulty_value or "").strip().lower()

    if value in ["easy", "beginner"]:
        return '<span style="color:#22c55e; font-weight:700;">🟢 Easy</span>'
    if value in ["medium", "intermediate"]:
        return '<span style="color:#eab308; font-weight:700;">🟡 Medium</span>'
    if value in ["hard", "difficult", "advanced"]:
        return '<span style="color:#ef4444; font-weight:700;">🔴 Difficult</span>'

    return f'<span style="color:#94a3b8; font-weight:700;">⚪ {difficulty_value or "Unknown"}</span>'


def build_case_opening_message(case_item):
    note = get_door_note(case_item)
    return (
        f"- Name: {note['name']}\n"
        f"- Age: {note['age']}\n"
        f"- Gender: {note['gender']}\n"
        f"- Cheif Complaint: {note['chief_complaint']}"
    )


def build_case_context_summary(case_item):
    structured = case_item.get("structuredData") or {}
    history = structured.get("history") if isinstance(structured, dict) else {}
    symptoms = history.get("symptoms") if isinstance(history, dict) else []
    prior_history = history.get("priorHistory") if isinstance(history, dict) else []

    symptoms_text = ", ".join(symptoms) if isinstance(symptoms, list) and symptoms else "not specified"
    prior_text = ", ".join(prior_history) if isinstance(prior_history, list) and prior_history else "none"

    return (
        f"System: Cardiology | Difficulty: {case_item.get('difficulty', 'unknown')} | "
        f"Age: {case_item.get('age', 'N/A')} | Gender: {case_item.get('gender', 'N/A')} | "
        f"Chief complaint: {case_item.get('chiefComplaint', 'N/A')} | "
        f"Symptoms: {symptoms_text} | Prior history: {prior_text}"
    )


def format_case_history_markdown(case_item):
    structured = case_item.get("structuredData") or case_item.get("structuredCaseData") or {}
    history = structured.get("history") if isinstance(structured, dict) else {}
    if not isinstance(history, dict) or not history:
        return "No seeded history available for this case."

    markdown_lines = ["### Seeded Case History"]

    onset = history.get("onset")
    markdown_lines.append("#### Onset")
    markdown_lines.append(f"- {onset}" if onset else "- Not specified")

    symptoms = history.get("symptoms")
    markdown_lines.append("#### Current Symptoms")
    if isinstance(symptoms, list) and symptoms:
        markdown_lines.extend([f"- {item}" for item in symptoms])
    else:
        markdown_lines.append("- Not specified")

    prior_history = history.get("priorHistory")
    markdown_lines.append("#### Prior History")
    if isinstance(prior_history, list) and prior_history:
        markdown_lines.extend([f"- {item}" for item in prior_history])
    else:
        markdown_lines.append("- Not specified")

    social_history = history.get("socialHistory")
    markdown_lines.append("#### Social History")
    if isinstance(social_history, list) and social_history:
        markdown_lines.extend([f"- {item}" for item in social_history])
    else:
        markdown_lines.append("- Not specified")

    return "\n".join(markdown_lines)


def format_case_physical_exam_markdown(case_item):
    structured = case_item.get("structuredData") or case_item.get("structuredCaseData") or {}
    if not isinstance(structured, dict):
        return "No seeded physical exam available for this case."

    physical_exam = structured.get("physicalExam")

    if not isinstance(physical_exam, dict) or not physical_exam:
        history = structured.get("history") if isinstance(structured.get("history"), dict) else {}
        fallback_exam = history.get("exam") if isinstance(history, dict) else {}
        if isinstance(fallback_exam, dict) and fallback_exam:
            physical_exam = {
                "vitals": fallback_exam.get("vitals"),
                "findings": fallback_exam.get("findings")
            }

    if not isinstance(physical_exam, dict) or not physical_exam:
        return "No seeded physical exam available for this case."

    markdown_lines = ["### Seeded Physical Exam"]

    vitals = physical_exam.get("vitals")
    markdown_lines.append("#### Vitals")
    if isinstance(vitals, dict) and vitals:
        for key, value in vitals.items():
            label = str(key).replace("_", " ")
            markdown_lines.append(f"- {label}: {value}")
    else:
        markdown_lines.append("- Not specified")

    return "\n".join(markdown_lines)


def extract_case_sections(case_item):
    structured = case_item.get("structuredData") or case_item.get("structuredCaseData") or {}
    history = structured.get("history") if isinstance(structured, dict) and isinstance(structured.get("history"), dict) else {}

    physical_exam = structured.get("physicalExam") if isinstance(structured, dict) and isinstance(structured.get("physicalExam"), dict) else {}
    if not physical_exam and isinstance(history.get("exam"), dict):
        physical_exam = {
            "vitals": history.get("exam", {}).get("vitals"),
            "findings": history.get("exam", {}).get("findings")
        }

    investigations = structured.get("investigations") if isinstance(structured, dict) and isinstance(structured.get("investigations"), dict) else {}
    if not investigations and isinstance(history.get("investigations"), dict):
        investigations = history.get("investigations")

    management_key_points = structured.get("managementKeyPoints") if isinstance(structured, dict) and isinstance(structured.get("managementKeyPoints"), list) else []
    if not management_key_points and isinstance(history.get("managementKeyPoints"), list):
        management_key_points = history.get("managementKeyPoints")

    vitals = physical_exam.get("vitals") if isinstance(physical_exam.get("vitals"), dict) else {}
    return history, physical_exam, investigations, management_key_points, vitals


def init_case_workflow_state(case_key):
    return init_case_workflow_state_core(st.session_state.osce_case_workflow, case_key)


def render_exam_results_card(case_item, workflow_state):
    return render_exam_results_card_core(case_item, workflow_state, extract_case_sections)


def render_history_results_card(case_item, workflow_state):
    return render_history_results_card_core(case_item, workflow_state, extract_case_sections)


def resolve_vital_value(case_item, workflow_state, vital_key):
    return resolve_vital_value_core(case_item, workflow_state, vital_key, extract_case_sections)


def resolve_lab_result(investigations, test_name):
    key = str(test_name or "").strip().lower()
    if key == "ecg":
        return investigations.get("ecg") or "ECG not specified"
    if key == "troponin":
        labs = investigations.get("labs") if isinstance(investigations.get("labs"), dict) else {}
        return labs.get("troponin") or "Troponin not specified"
    if key == "cxr":
        return investigations.get("imaging") or investigations.get("cxr") or "CXR not specified"
    return None


def order_investigations(case_item, requested_tests, workflow_state):
    _, _, investigations, _, _ = extract_case_sections(case_item)
    allowed_tests = {"ECG", "Troponin", "CXR"}
    penalty_tests = {"Brain MRI"}

    for test_name in requested_tests:
        if test_name in workflow_state["ordered_tests"]:
            continue

        workflow_state["ordered_tests"].append(test_name)

        if test_name in penalty_tests:
            workflow_state["waste_penalty"] += 10
            workflow_state["investigation_results"][test_name] = "Ordered but low-yield for this presentation (resource waste penalty applied)."
            continue

        if test_name in allowed_tests:
            workflow_state["investigation_results"][test_name] = resolve_lab_result(investigations, test_name)
        else:
            workflow_state["waste_penalty"] += 5
            workflow_state["investigation_results"][test_name] = "No relevant result available."

    if workflow_state["ordered_tests"]:
        workflow_state["phase"] = "investigations"


def grade_transcript_with_llm(transcript_user, management_key_points):
    grading_prompt = (
        "You are a strict OSCE grader.\n"
        "Given transcript and expected management key points, return ONLY valid JSON with keys: matched_points, total_points, summary.\n"
        f"Transcript: {transcript_user}\n"
        f"Key points: {json.dumps(management_key_points, ensure_ascii=False)}"
    )

    response = memory_manager.client.chat.completions.create(
        model="meta/llama-3.1-70b-instruct",
        messages=[{"role": "user", "content": grading_prompt}],
        temperature=0,
        max_tokens=220
    )
    raw = (response.choices[0].message.content or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    parsed = json.loads(raw[start:end + 1])
    return {
        "matched_points": int(parsed.get("matched_points", 0)),
        "total_points": int(parsed.get("total_points", len(management_key_points))),
        "summary": str(parsed.get("summary", ""))
    }


def score_case_transcript(case_item, messages, workflow_state):
    transcript_user = " ".join([
        str(m.get("content", "")) for m in messages if m.get("role") == "user"
    ]).lower()
    _, _, _, management_key_points, _ = extract_case_sections(case_item)

    keyword_hits = sum(1 for v in workflow_state["keywords_tracked"].values() if v)
    max_keyword = max(len(workflow_state["keywords_tracked"]), 1)
    history_score = round((keyword_hits / max_keyword) * 100)

    matched_points = 0
    llm_summary = ""
    try:
        llm_grade = grade_transcript_with_llm(transcript_user, management_key_points)
        if llm_grade:
            matched_points = min(llm_grade["matched_points"], max(llm_grade["total_points"], 0))
            llm_summary = llm_grade.get("summary", "")
    except Exception:
        llm_grade = None

    if not llm_grade:
        for point in management_key_points:
            point_tokens = [token for token in str(point).lower().replace("(", " ").replace(")", " ").replace(",", " ").split() if len(token) > 3]
            if any(token in transcript_user for token in point_tokens[:4]):
                matched_points += 1

    management_score = round((matched_points / max(len(management_key_points), 1)) * 100) if management_key_points else 0
    penalty = workflow_state.get("waste_penalty", 0)
    total_score = max(0, round((history_score * 0.5) + (management_score * 0.5) - penalty))

    result = {
        "history_score": history_score,
        "management_score": management_score,
        "waste_penalty": penalty,
        "total_score": total_score,
        "matched_management_points": matched_points,
        "management_points_total": len(management_key_points),
        "keywords_tracked": workflow_state.get("keywords_tracked", {}),
        "grader_summary": llm_summary
    }
    workflow_state["score"] = result
    workflow_state["phase"] = "completed"
    return result


def build_case_scoped_reply(case_item, prompt, workflow_state, case_chat_key):
    return build_case_scoped_reply_core(
        case_item,
        prompt,
        workflow_state,
        case_chat_key,
        extract_case_sections,
        order_investigations
    )

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
                <div class="osce-hero-top">
                    <div class="osce-hero-copy">
                        <h1>Welcome back, Dr. Praveen</h1>
                    </div>
                    <div class="osce-countdown">
                        <span class="osce-countdown-icon">⏳</span>
                        <span class="osce-countdown-text">
                            <span class="osce-countdown-days">80 days</span>
                            <span class="osce-countdown-label">OSCE exam</span>
                        </span>
                    </div>
                </div>
                <p>Continue your OSCE training journey with focused practice and real-time feedback.</p>
            </div>
        ''', unsafe_allow_html=True)
        
        # Original Metrics
        c1, c2, c3, c4 = st.columns(4)
        m_list = [("Total Sessions", "160", "12%"), ("Clinical Score", "74%", "5%"), ("Current Rank", "Registrar", "Lvl 3"), ("Current Streak", "7 Days", "3%")]
        for col, (lab, val, det) in zip([c1, c2, c3, c4], m_list):
            with col:
                st.markdown(
                    f'''
                    <div class="metric-card">
                        <div class="metric-label">{lab}</div>
                        <div class="metric-value">{val}</div>
                        <div class="metric-detail">{det}</div>
                    </div>
                    ''',
                    unsafe_allow_html=True
                )

        st.line_chart(pd.DataFrame({"Score": [42, 55, 62, 72, 82]}), color="#14b8a6")

        # System Grid
        st.markdown('<h3 class="osce-section-title">Select Medical System</h3>', unsafe_allow_html=True)
        backend_systems = fetch_backend_systems()
        systems = {
            (s.get("name") or ""): "❤️" if (s.get("name") or "").lower() == "cardiology" else "🩺"
            for s in backend_systems
            if s.get("name")
        }
        if not systems:
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
                            st.session_state.selected_system_id = next((x.get("id") for x in backend_systems if x.get("name") == name), None)
                            st.rerun()

# ==============================
# PAGE: SYSTEM DETAIL (Lovable Style)
# ==============================
def render_system_detail():
    sys = st.session_state.selected_system

    def _trigger_browser_back():
        components.html(
            """
            <script>
              window.parent.history.back();
            </script>
            """,
            height=0,
            width=0,
        )

    def _back_to_dashboard():
        st.session_state.in_case = False
        st.session_state.selected_system = None
        st.session_state.selected_system_id = None

    back_col, _ = st.columns([1, 8])
    with back_col:
        if st.button("⬅ Back", key="back_system_detail"):
            _back_to_dashboard()
            _trigger_browser_back()
            st.rerun()

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
        st.session_state.difficulty = "Easy"
        st.rerun()
    if d2.button("🟡 Medium", use_container_width=True):
        st.session_state.difficulty = "Medium"
        st.rerun()
    if d3.button("🔴 Hard", use_container_width=True):
        st.session_state.difficulty = "Hard"
        st.rerun()

    if (sys or "").lower() == "cardiology":
        st.markdown("#### Available Cardiology Cases")
        try:
            cardiology_cases = fetch_cardiology_medical_cases(None)
            if cardiology_cases:
                for idx, case_item in enumerate(cardiology_cases, start=1):
                    difficulty_label = format_difficulty_symbol(case_item.get('difficulty'))
                    c_info, c_action = st.columns([5, 1])
                    with c_info:
                        st.markdown(
                            f"{idx}. **{case_item.get('chiefComplaint', 'Unknown complaint')}** "
                            f"| Age {case_item.get('age', 'N/A')} | {case_item.get('gender', 'N/A')} "
                            f"| {difficulty_label}",
                            unsafe_allow_html=True
                        )
                    with c_action:
                        case_id = case_item.get("id", f"case_{idx}")
                        if st.button("Start", key=f"start_case_{case_id}", use_container_width=True):
                            st.session_state.selected_case = case_item
                            st.session_state.difficulty = str(case_item.get("difficulty", st.session_state.difficulty)).title()
                            st.session_state.in_case = True
                            st.rerun()
            else:
                st.info("No cardiology cases found yet. Seed data first.")
        except Exception as e:
            st.warning(f"Unable to load cardiology cases: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Disease Breakdown")
    st.table(pd.DataFrame({"Disease": ["ACS", "Heart Failure", "Pericarditis"], "Accuracy": ["88%", "72%", "65%"], "Status": ["Strong", "Moderate", "Weak"]}))

# ==============================
# PAGE: CASE SIMULATION
# ==============================
def render_case_simulation():
    # Floating AMA logic

    def _trigger_browser_back():
        components.html(
            """
            <script>
              window.parent.history.back();
            </script>
            """,
            height=0,
            width=0,
        )

    def _back_to_system_detail():
        st.session_state.in_case = False

    back_col, _ = st.columns([1, 8])
    with back_col:
        if st.button("⬅ Back", key="back_case_sim"):
            _back_to_system_detail()
            _trigger_browser_back()
            st.rerun()

    selected_case = st.session_state.get("selected_case")
    if isinstance(selected_case, dict) and selected_case.get("id"):
        try:
            live_cases = fetch_cardiology_medical_cases(None)
            selected_id = selected_case.get("id")
            refreshed = next((c for c in live_cases if c.get("id") == selected_id), None)
            if refreshed:
                st.session_state.selected_case = refreshed
                selected_case = refreshed
        except Exception:
            pass

    if not selected_case:
        st.warning("Please select a cardiology case from Available Cardiology Cases.")
        st.session_state.in_case = False
        st.rerun()

    case_difficulty = selected_case.get("difficulty", st.session_state.difficulty)
    st.markdown(f"### OSCE Session: {st.session_state.selected_system} ({str(case_difficulty).title()})")
    st.caption(
        f"Case: {selected_case.get('chiefComplaint', 'Unknown complaint')} | "
        f"Age {selected_case.get('age', 'N/A')} | {selected_case.get('gender', 'N/A')}"
    )

    floating_ama()

    css_block = """
        <style>
        :root {
            --chat-pane-left: clamp(19.5rem, 25vw, 27rem);
        }

        .glass {
            text-align: left;
        }

        .stRadio > div[role="radiogroup"] {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-start;
            gap: 0.4rem 0.7rem;
        }

        .st-key-quick_investigate,
        .st-key-quick_manage,
        .st-key-quick_dx,
        .st-key-quick_ask,
        .st-key-exam_btn,
        .st-key-score_btn {
            position: fixed !important;
            bottom: 0.9rem !important;
            z-index: 4000 !important;
            width: 3.2rem;
            pointer-events: auto !important;
        }
        .st-key-quick_ask { left: var(--chat-pane-left); }
        .st-key-quick_investigate { left: calc(var(--chat-pane-left) + 3.6rem); }
        .st-key-quick_manage { left: calc(var(--chat-pane-left) + 7.2rem); }
        .st-key-quick_dx { left: calc(var(--chat-pane-left) + 10.8rem); }
        .st-key-exam_btn { left: calc(var(--chat-pane-left) + 14.4rem); }
        .st-key-score_btn { left: calc(var(--chat-pane-left) + 18rem); }

        .st-key-quick_investigate button,
        .st-key-quick_manage button,
        .st-key-quick_dx button,
        .st-key-quick_ask button,
        .st-key-exam_btn button,
        .st-key-score_btn button {
            width: 3.2rem !important;
            height: 2.6rem !important;
            min-height: 2.6rem !important;
            padding: 0 !important;
            font-size: 1rem !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            line-height: 1 !important;
        }

        .osce-split-boundary {
            height: 72vh;
            border-left: 1px solid rgba(148, 163, 184, 0.35);
            border-right: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 999px;
            margin: 0 auto 0.4rem auto;
            width: 2px;
        }

        @media (max-width: 1200px) {
            .st-key-quick_ask { left: 1rem; bottom: 8.8rem; }
            .st-key-quick_investigate { left: 4.6rem; bottom: 8.8rem; }
            .st-key-quick_manage { left: 8.2rem; bottom: 8.8rem; }
            .st-key-quick_dx { left: 11.8rem; bottom: 8.8rem; }
            .st-key-exam_btn { left: 15.4rem; bottom: 8.8rem; }
            .st-key-score_btn { left: 19rem; bottom: 8.8rem; }
        }
        </style>
        """
    st.markdown(css_block, unsafe_allow_html=True)

    col_chat, col_split, col_notes = st.columns([65, 2, 35])

    with col_split:
        st.markdown('<div class="osce-split-boundary"></div>', unsafe_allow_html=True)

    with col_chat:
        case_id = selected_case.get("id", "unknown_case")
        case_chat_key = f"osce_case_{case_id}"
        workflow_state = init_case_workflow_state(case_chat_key)

        st.markdown('<div id="osce-chat-left-anchor" style="height:0; margin:0; padding:0;"></div>', unsafe_allow_html=True)

        components.html(
            """
            <script>
            (function() {
                const updateAnchor = () => {
                    const anchor = window.parent.document.getElementById('osce-chat-left-anchor');
                    if (!anchor) return;
                    const left = Math.max(8, Math.round(anchor.getBoundingClientRect().left));
                    window.parent.document.documentElement.style.setProperty('--chat-pane-left', `${left}px`);

                    const leftCol = anchor.closest('[data-testid="column"]');
                    if (leftCol) {
                        leftCol.style.position = 'relative';
                        leftCol.style.zIndex = '20';
                        leftCol.style.overflow = 'visible';
                    }

                    const notesAnchor = window.parent.document.getElementById('osce-notes-anchor');
                    if (notesAnchor) {
                        const rightCol = notesAnchor.closest('[data-testid="column"]');
                        if (rightCol) {
                            rightCol.style.position = 'relative';
                            rightCol.style.zIndex = '5';
                        }
                    }
                };

                updateAnchor();
                window.parent.addEventListener('resize', updateAnchor);

                if (window.parent.__osceAnchorObserver) {
                    window.parent.__osceAnchorObserver.disconnect();
                }
                const observer = new window.parent.MutationObserver(() => updateAnchor());
                observer.observe(window.parent.document.body, { childList: true, subtree: true });
                window.parent.__osceAnchorObserver = observer;
            })();
            </script>
            """,
            height=0,
            width=0
        )

        if case_chat_key not in st.session_state.osce_case_messages:
            st.session_state.osce_case_messages[case_chat_key] = [
                {"role": "assistant", "content": build_case_opening_message(selected_case)}
            ]

        with st.container(height=500, border=True):
            for msg in st.session_state.osce_case_messages[case_chat_key]:
                st.chat_message(msg["role"]).write(msg["content"])

        quick_col1, quick_col2, quick_col3, quick_col4 = st.columns(4)
        with quick_col1:
            if st.button("❓", key="quick_ask", use_container_width=True, help="Ask question"):
                st.session_state.focus_chat_input = True
                st.session_state.case_notes_hint = "ask_question"
                st.rerun()
        with quick_col2:
            if st.button("🔬", key="quick_investigate", use_container_width=True, help="Enter investigation"):
                st.session_state.case_notes_hint = "investigations"
                workflow_state["phase"] = "investigations"
                st.session_state.case_active_panel = "Investigations"
                st.rerun()
        with quick_col3:
            if st.button("📑", key="quick_manage", use_container_width=True, help="Enter management"):
                st.session_state.case_notes_hint = "management"
                st.session_state.case_active_panel = "Management"
                st.rerun()
        with quick_col4:
            if st.button("✅", key="quick_dx", use_container_width=True, help="Submit diagnosis"):
                st.session_state.case_notes_hint = "diagnosis"
                st.session_state.case_active_panel = "Differential diagnosis"
                st.rerun()

        exam_col, score_col = st.columns(2)
        with exam_col:
            if st.button("🩺", key="exam_btn", use_container_width=True, help="Examine (/examine)"):
                workflow_state["phase"] = "exam"
                workflow_state["exam_unlocked"] = True
                st.session_state.case_active_panel = "Physical Exam"
                st.session_state.osce_case_messages[case_chat_key].append({"role": "assistant", "content": "Okay, what would you like to check?"})
                st.rerun()
        with score_col:
            if st.button("🏁", key="score_btn", use_container_width=True, help="Finish & Score"):
                result = score_case_transcript(selected_case, st.session_state.osce_case_messages[case_chat_key], workflow_state)
                st.session_state.osce_case_messages[case_chat_key].append(
                    {
                        "role": "assistant",
                        "content": (
                            f"Scoring complete. Total score: {result['total_score']}%. "
                            f"History: {result['history_score']}%, Management: {result['management_score']}%, "
                            f"Waste penalty: -{result['waste_penalty']}"
                        )
                    }
                )
                st.rerun()

        input_label_map = {
            "ask_question": "ask question",
            "investigations": "Enter investigation...",
            "management": "Enter management...",
            "diagnosis": "Submit diagnosis..."
        }
        active_input_label = input_label_map.get(st.session_state.case_notes_hint, "Talk to the patient...")

        if prompt := st.chat_input(active_input_label, key="osce_chat_input"):
            st.session_state.osce_case_messages[case_chat_key].append({"role": "user", "content": prompt})

            answer = build_case_scoped_reply(selected_case, prompt, workflow_state, case_chat_key)

            st.session_state.osce_case_messages[case_chat_key].append({"role": "assistant", "content": answer})
            st.session_state.case_notes_hint = None
            st.rerun()

        if st.session_state.focus_chat_input:
            components.html(
                """
                <script>
                const labels = ["ask question", "Talk to the patient...", "Enter investigation...", "Enter management...", "Submit diagnosis..."];
                let target = null;

                for (const label of labels) {
                    target = window.parent.document.querySelector(`textarea[aria-label="${label}"]`);
                    if (target) break;
                }

                if (!target) {
                    const inputs = window.parent.document.querySelectorAll('[data-testid="stChatInput"] textarea');
                    if (inputs.length) {
                        target = inputs[inputs.length - 1];
                    }
                }

                if (target) {
                    const wrapper = target.closest('[data-testid="stChatInput"]');
                    if (wrapper) {
                        wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    } else {
                        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    setTimeout(() => target.focus(), 120);
                }
                </script>
                """,
                height=0,
                width=0
            )
            st.session_state.focus_chat_input = False

    with col_notes:
        st.markdown('<div id="osce-notes-anchor" style="height:0; margin:0; padding:0;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        panel_options = ["History", "Physical Exam", "Differential diagnosis", "Investigations", "Management"]
        if st.session_state.case_active_panel not in panel_options:
            st.session_state.case_active_panel = "History"

        active_panel = st.radio(
            "Side Tab",
            options=panel_options,
            key="case_active_panel",
            horizontal=True,
            label_visibility="collapsed"
        )

        if active_panel == "History":
            st.markdown(render_history_results_card(selected_case, workflow_state))
        elif active_panel == "Physical Exam":
            if workflow_state.get("exam_unlocked"):
                selected_vital = st.selectbox(
                    "General physical exam vitals",
                    options=GENERAL_VITAL_OPTIONS,
                    key=f"exam_vital_select_{case_id}"
                )
                if selected_vital:
                    value, generated = resolve_vital_value(selected_case, workflow_state, selected_vital)
                    label = str(selected_vital).replace("_", " ").title()
                    if selected_vital not in workflow_state["revealed_vitals"]:
                        workflow_state["revealed_vitals"].append(selected_vital)
                    if generated:
                        st.info(f"{label}: {value} (generated for this case)")
                    else:
                        st.success(f"{label}: {value}")
                st.markdown(render_exam_results_card(selected_case, workflow_state))
            else:
                st.info("🩺Physical exam is locked. . examine first")
        elif active_panel == "Differential diagnosis":
            if st.session_state.case_notes_hint == "diagnosis":
                st.info("Quick link opened: Submit diagnosis")
            st.text_area("Differential diagnosis", key="case_differential_note", height=300)
        elif active_panel == "Investigations":
            if st.session_state.case_notes_hint == "investigations":
                st.info("Quick link opened: Enter investigation")
            lab_choices = st.multiselect(
                "Lab Menu",
                options=["ECG", "Troponin", "CXR", "Brain MRI"],
                key=f"lab_menu_{case_id}"
            )
            if st.button("Order Selected Tests", key=f"order_labs_{case_id}", use_container_width=True):
                order_investigations(selected_case, lab_choices, workflow_state)
                st.session_state.case_active_panel = "Investigations"
                st.rerun()

            if workflow_state.get("investigation_results"):
                st.markdown("**Investigation Results**")
                for test_name, test_result in workflow_state["investigation_results"].items():
                    st.markdown(f"- **{test_name}:** {test_result}")

            if workflow_state.get("waste_penalty", 0) > 0:
                st.warning(f"Waste of Resources Penalty: -{workflow_state['waste_penalty']}")
            st.text_area("Ordered Investigations", key="case_investigation_note", height=300)
        elif active_panel == "Management":
            if st.session_state.case_notes_hint == "management":
                st.info("Quick link opened: Enter management")
            st.text_area("Management Plan", key="case_management_note", height=300)

        if workflow_state.get("score"):
            score = workflow_state["score"]
            st.markdown("### Final Score")
            st.markdown(
                f"- History score: {score['history_score']}%\n"
                f"- Management score: {score['management_score']}%\n"
                f"- Waste penalty: -{score['waste_penalty']}\n"
                f"- **Total: {score['total_score']}%**"
            )
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================
# ROUTER
# ==============================
save_ui_state()

if st.session_state.active_page == "ChatAI":
    render_chat()
else:
    render_osce()
