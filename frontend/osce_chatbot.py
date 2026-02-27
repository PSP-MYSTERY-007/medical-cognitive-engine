import json
import re

from memorynvidia import (
    memory_manager,
    OSCE_PATIENT_BLOCKED_TOPICS,
    OSCE_PATIENT_HISTORY_KEYWORDS,
    OSCE_PATIENT_EXAM_KEYWORDS,
)

GENERAL_VITAL_OPTIONS = ["bp", "hr", "rr", "spo2", "temp"]

VITAL_QUERY_ALIASES = {
    "bp": ["bp", "blood pressure", "pressure"],
    "hr": ["hr", "heart rate", "pulse"],
    "rr": ["rr", "respiratory", "resp rate", "respiratory rate,respi"],
    "spo2": ["spo2", "oxygen", "saturation", "o2 sat", "oxygen saturation"],
    "temp": ["temp", "temperature", "fever"]
}

HISTORY_FIELD_KEYWORDS = {
    "onset": ["onset", "start", "started", "when"],
    "symptoms": ["symptom", "complaint", "feel", "feeling"],
    "associatedSymptoms": ["associated", "other symptom", "accompanying"],
    "priorHistory": ["prior", "past", "medical history", "past history"],
    "familyHistory": ["family", "father", "mother", "relative"],
    "socialHistory": ["social", "smoking", "smoker", "alcohol", "drug", "caffeine", "living"],
    "medications": ["medication", "medicine", "drug", "tablet"],
    "rhythmDescription": ["rhythm", "palpitations", "palpitation", "flutter"],
    "redFlags": ["chest pain", "syncope", "weakness", "numb", "speech"],
    "location": ["location", "where", "located"],
    "relievingFactors": ["relieve", "better", "eases", "improves"]
}

RED_FLAG_ALIASES = {
    "chestPain": ["chest pain", "angina"],
    "syncope": ["syncope", "faint", "fainted", "pass out", "loss of consciousness"],
    "focalWeakness": ["weakness", "numb", "numbness", "speech", "slurred speech"]
}

DEFAULT_RED_FLAGS = {
    "chestPain": "None",
    "syncope": "None",
    "focalWeakness": "None"
}

SOCIAL_HISTORY_ALIASES = {
    "smoking": ["smoke", "smoker", "smoking", "cigarette", "tobacco"],
    "alcohol": ["alcohol", "drink", "drinking", "wine", "beer"],
    "caffeine": ["caffeine", "coffee", "tea"],
    "livingSituation": ["living", "living situation", "live with", "home"],
    "drugUse": ["drug", "drugs", "illicit", "substance", "recreational"]
}


def init_case_workflow_state(workflow_store, case_key):
    if case_key not in workflow_store:
        workflow_store[case_key] = {
            "phase": "history",
            "chief_complaint_shared": False,
            "exam_unlocked": False,
            "ordered_tests": [],
            "investigation_results": {},
            "waste_penalty": 0,
            "keywords_tracked": {"rest": False, "exertion": False, "smoking": False},
            "revealed_vitals": [],
            "generated_vitals": {},
            "revealed_history_fields": [],
            "revealed_investigations": [],
            "score": None
        }
    return workflow_store[case_key]


def _normalize_text(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

QUESTION_STOPWORDS = {
    "the", "a", "an", "is", "are", "am", "was", "were", "be", "been", "being",
    "do", "does", "did", "can", "could", "would", "should", "will", "shall", "may",
    "might", "to", "for", "of", "on", "in", "at", "about", "tell", "me", "your",
    "you", "have", "has", "had", "any", "please", "what", "when", "where", "which",
    "who", "how", "if", "it", "this", "that", "my", "our", "we", "i"
}


def _humanize_key(value):
    text = str(value or "")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ")
    return _normalize_text(text)


def _key_terms(value):
    humanized = _humanize_key(value)
    pieces = re.findall(r"[a-z0-9]+", humanized)
    terms = set()
    if humanized and humanized not in {"history"}:
        terms.add(humanized)
    terms.update([p for p in pieces if len(p) > 2 and p not in {"history"}])
    return terms


def _canonical_key_name(value):
    humanized = _humanize_key(value)
    return re.sub(r"[^a-z0-9]", "", humanized)


def _lookup_dict_value(mapping, target_key, default=None):
    if not isinstance(mapping, dict):
        return default

    if target_key in mapping:
        return mapping.get(target_key)

    target_norm = _canonical_key_name(target_key)
    for key, value in mapping.items():
        if _canonical_key_name(key) == target_norm:
            return value
    return default


def _lookup_dict_subvalue(mapping, target_key, default=None):
    value = _lookup_dict_value(mapping, target_key, default)
    return default if value is None else value


def _parse_social_history_text(social_history_text):
    text = str(social_history_text or "").strip()
    if not text:
        return {}

    parts = [p.strip() for p in re.split(r"[,;|]", text) if p.strip()]
    parsed = {}

    def contains_alias(segment, aliases):
        normalized_segment = _normalize_text(segment)
        return any(_normalize_text(alias) in normalized_segment for alias in aliases)

    for part in parts:
        if contains_alias(part, SOCIAL_HISTORY_ALIASES.get("smoking", [])):
            parsed["smoking"] = part
            continue
        if contains_alias(part, SOCIAL_HISTORY_ALIASES.get("alcohol", [])):
            parsed["alcohol"] = part
            continue
        if contains_alias(part, SOCIAL_HISTORY_ALIASES.get("caffeine", [])):
            parsed["caffeine"] = part
            continue
        if contains_alias(part, SOCIAL_HISTORY_ALIASES.get("drugUse", [])):
            parsed["drugUse"] = part
            continue
        if contains_alias(part, SOCIAL_HISTORY_ALIASES.get("livingSituation", [])):
            parsed["livingSituation"] = part

    if parsed:
        return parsed

    return {"socialSummary": text}


def _get_history_social_history(history):
    social_history = _lookup_dict_value(history, "socialHistory", {})
    if isinstance(social_history, dict):
        return social_history
    if isinstance(social_history, str):
        return _parse_social_history_text(social_history)
    return {}


def _get_history_red_flags(history):
    red_flags = _lookup_dict_value(history, "redFlags", {})
    return red_flags if isinstance(red_flags, dict) else {}


def _format_history_value(value):
    if isinstance(value, list):
        if not value:
            return "Not specified"
        return ", ".join([str(x) for x in value])
    if isinstance(value, dict):
        if not value:
            return "Not specified"
        parts = [f"{str(k).replace('_', ' ').title()}: {v}" for k, v in value.items()]
        return " | ".join(parts)
    if value is None or str(value).strip() == "":
        return "Not specified"
    return str(value)


def _detect_red_flag_key(prompt_text):
    normalized_prompt = _normalize_text(prompt_text)
    for key, aliases in RED_FLAG_ALIASES.items():
        if any(alias in normalized_prompt for alias in aliases):
            return key
    return None


def _resolve_red_flag_value(history, red_flag_key):
    if not red_flag_key:
        return None

    red_flags = _get_history_red_flags(history)
    resolved = _lookup_dict_subvalue(red_flags, red_flag_key)
    if str(resolved or "").strip():
        return resolved
    return DEFAULT_RED_FLAGS.get(red_flag_key, "None")


def _history_field_requested(prompt_text, field_name, field_value=None):
    normalized_prompt = _normalize_text(prompt_text)
    field_key = str(field_name or "")
    aliases = set(HISTORY_FIELD_KEYWORDS.get(field_key, []))
    aliases.update(_key_terms(field_key))

    if isinstance(field_value, dict):
        for nested_key in field_value.keys():
            aliases.update(_key_terms(nested_key))
    elif isinstance(field_value, list):
        for item in field_value:
            if isinstance(item, dict):
                for nested_key in item.keys():
                    aliases.update(_key_terms(nested_key))

    if any(alias and alias in normalized_prompt for alias in aliases):
        return True

    return False


def _matched_nested_keys_in_dict(field_value, prompt_text):
    if not isinstance(field_value, dict) or not field_value:
        return []

    normalized_prompt = _normalize_text(prompt_text)
    matched_keys = []
    for nested_key in field_value.keys():
        aliases = _key_terms(nested_key)
        if any(alias and alias in normalized_prompt for alias in aliases):
            matched_keys.append(nested_key)
    return matched_keys


def _prompt_terms(prompt_text):
    return [term for term in re.findall(r"[a-z0-9]+", _normalize_text(prompt_text)) if len(term) > 2]


def _question_keywords(prompt_text):
    return [
        term for term in _prompt_terms(prompt_text)
        if term not in QUESTION_STOPWORDS
    ]


def _should_start_with_intro(prompt_text):
    text = _normalize_text(prompt_text)
    if not text:
        return True

    greeting_markers = ["hi", "hello", "hey", "start", "begin", "good morning", "good afternoon"]
    if text in greeting_markers:
        return True

    if len(_question_keywords(prompt_text)) == 0 and not text.endswith("?"):
        return True

    return False


def _best_keyword_history_payload(history, prompt_text):
    if not isinstance(history, dict) or not history:
        return {}

    prompt_keywords = set(_question_keywords(prompt_text))
    prompt_norm = _normalize_text(prompt_text)
    if not prompt_keywords and not prompt_norm:
        return {}

    best_match = None

    def consider_payload(payload, aliases):
        nonlocal best_match
        alias_set = set([_normalize_text(a) for a in aliases if a])
        alias_tokens = set()
        for alias in alias_set:
            alias_tokens.update(_prompt_terms(alias))

        score = 0
        if alias_set and any(alias in prompt_norm for alias in alias_set):
            score += 4
        score += len(prompt_keywords.intersection(alias_tokens))

        if score <= 0:
            return

        if best_match is None or score > best_match[0]:
            best_match = (score, payload)

    for field_name, field_value in history.items():
        aliases = set(HISTORY_FIELD_KEYWORDS.get(field_name, []))
        aliases.update(_key_terms(field_name))
        aliases.update(_value_terms(field_value))

        if field_name == "socialHistory":
            social_history_map = field_value if isinstance(field_value, dict) else _parse_social_history_text(field_value)
            for social_key, social_value in social_history_map.items():
                social_aliases = set(SOCIAL_HISTORY_ALIASES.get(social_key, []))
                social_aliases.update(_key_terms(social_key))
                social_aliases.update(_value_terms(social_value))
                consider_payload({"socialHistory": {social_key: social_value}}, social_aliases)
            continue

        if field_name == "redFlags" and isinstance(field_value, dict):
            for red_key, red_value in field_value.items():
                red_aliases = set(RED_FLAG_ALIASES.get(red_key, []))
                red_aliases.update(_key_terms(red_key))
                red_aliases.update(_value_terms(red_value))
                consider_payload({"redFlags": {red_key: red_value}}, red_aliases)
            continue

        consider_payload({field_name: field_value}, aliases)

    return best_match[1] if best_match else {}


def _expand_onset_payload_with_symptoms(payload, history, case_item):
    if not isinstance(payload, dict) or "onset" not in payload:
        return payload

    expanded = dict(payload)
    if "associatedSymptoms" in expanded:
        return expanded

    associated = _lookup_dict_value(history, "associatedSymptoms", [])
    if not isinstance(associated, list):
        associated = []

    complaint_text = str(case_item.get("chiefComplaint") or "").strip()
    complaint_parts = [part.strip() for part in re.split(r",| and | with ", complaint_text, flags=re.IGNORECASE) if part.strip()]

    merged = []
    seen = set()
    for symptom in [*associated, *complaint_parts]:
        symptom_text = str(symptom or "").strip()
        symptom_norm = _normalize_text(symptom_text)
        if symptom_norm and symptom_norm not in seen:
            seen.add(symptom_norm)
            merged.append(symptom_text)

    if merged:
        expanded["associatedSymptoms"] = merged

    return expanded


def _value_terms(value):
    terms = set()
    if isinstance(value, dict):
        for _, nested_value in value.items():
            terms.update(_value_terms(nested_value))
        return terms
    if isinstance(value, list):
        for item in value:
            terms.update(_value_terms(item))
        return terms

    text = _normalize_text(value)
    terms.update([term for term in re.findall(r"[a-z0-9]+", text) if len(term) > 2])
    return terms


def _case_keyword_set(case_item, history, physical_exam, investigations):
    keywords = set()
    keywords.update(_value_terms(history))
    keywords.update(_value_terms(physical_exam))
    keywords.update(_value_terms(investigations))
    keywords.update(_value_terms(case_item.get("chiefComplaint")))
    keywords.update(_value_terms(case_item.get("gender")))
    keywords.update(_value_terms(case_item.get("age")))
    return keywords


def _prompt_is_case_relevant(prompt_text, history, case_keywords):
    text = _normalize_text(prompt_text)

    if _detect_social_history_key(text):
        social_history = _get_history_social_history(history)
        detected_social_key = _detect_social_history_key(text)
        if _lookup_dict_subvalue(social_history, detected_social_key) is not None:
            return True

    if _detect_red_flag_key(text):
        return True

    prompt_terms = _prompt_terms(text)
    if not prompt_terms:
        return False

    return any(term in case_keywords for term in prompt_terms)


def _selective_list_items_for_prompt(items, prompt_text):
    if not isinstance(items, list) or not items:
        return []

    terms = _prompt_terms(prompt_text)
    if not terms:
        return []

    selected = []
    for item in items:
        text = _normalize_text(item)
        if any(term in text for term in terms):
            selected.append(item)
    return selected


def _selective_family_history_for_prompt(family_history_value, prompt_text):
    if not isinstance(family_history_value, str) or not family_history_value.strip():
        return None

    terms = _prompt_terms(prompt_text)
    if not terms:
        return None

    clauses = [segment.strip() for segment in re.split(r"[;]", family_history_value) if segment.strip()]
    if not clauses:
        return None

    matched_clauses = []
    for clause in clauses:
        normalized_clause = _normalize_text(clause)
        if any(term in normalized_clause for term in terms):
            matched_clauses.append(clause)

    if not matched_clauses:
        return None
    return "; ".join(matched_clauses)


def _detect_social_history_key(prompt_text):
    normalized_prompt = _normalize_text(prompt_text)
    for key, key_aliases in SOCIAL_HISTORY_ALIASES.items():
        alias_set = set(key_aliases)
        alias_set.update(_key_terms(key))
        if any(alias and alias in normalized_prompt for alias in alias_set):
            return key
    return None


def _is_generic_history_prompt(prompt_text):
    text = _normalize_text(prompt_text)
    generic_markers = ["history", "symptom", "complaint", "tell me", "more"]
    return any(marker in text for marker in generic_markers)


def _persona_descriptor(case_item):
    age = case_item.get("age")
    gender = _normalize_text(case_item.get("gender"))
    persona = str(case_item.get("patientPersona") or "").strip()

    parts = []
    if age is not None:
        parts.append(f"{age}-year-old")
    if gender:
        parts.append(gender)
    descriptor = " ".join(parts).strip()
    if persona:
        descriptor = f"{descriptor} ({persona})".strip()
    return descriptor or "patient"


def _intro_chief_complaint(case_item):
    complaint = str(case_item.get("chiefComplaint") or "").strip()
    if not complaint:
        return "irrelevant"
    return f"I am a {_persona_descriptor(case_item)}. My main complaint is: {complaint}."


def _is_exam_intent(prompt_text):
    text = _normalize_text(prompt_text)
    exam_markers = [
        "examine", "examination", "physical exam", "inspect", "palpate", "percuss", "auscultate",
        "listen to", "check", "measure", "take my"
    ]
    return any(marker in text for marker in exam_markers)


def _has_investigation_order_intent(prompt_text):
    text = _normalize_text(prompt_text)
    order_markers = ["order", "request", "do", "run", "send", "get", "take"]
    return any(marker in text for marker in order_markers)


def _known_symptom_phrases(history, case_item):
    phrases = []
    for key in ["symptoms", "associatedSymptoms"]:
        values = _lookup_dict_value(history, key, [])
        if isinstance(values, list):
            phrases.extend([str(x).strip() for x in values if str(x).strip()])

    complaint = str(case_item.get("chiefComplaint") or "").strip()
    if complaint:
        complaint_parts = re.split(r",| and | with ", complaint, flags=re.IGNORECASE)
        phrases.extend([part.strip() for part in complaint_parts if part.strip()])

    unique_phrases = []
    seen = set()
    for phrase in phrases:
        normalized = _normalize_text(phrase)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_phrases.append(phrase)
    return unique_phrases


def _is_symptom_query(prompt_text):
    text = _normalize_text(prompt_text)
    symptom_markers = ["symptom", "pain", "shortness of breath", "breath", "palpitation", "dizzy", "fatigue", "fever", "cough"]
    question_markers = ["do you have", "are you having", "have you had", "any", "?"]
    return any(marker in text for marker in symptom_markers) and any(marker in text for marker in question_markers)


def _symptom_response(prompt_text, history, case_item):
    prompt_norm = _normalize_text(prompt_text)
    known_phrases = _known_symptom_phrases(history, case_item)

    generic_symptom_asks = [
        "what symptoms",
        "which symptoms",
        "what are your symptoms",
        "tell me your symptoms",
        "describe your symptoms",
        "symptoms"
    ]

    if any(ask in prompt_norm for ask in generic_symptom_asks):
        if known_phrases:
            symptoms_text = ", ".join([str(x).strip() for x in known_phrases if str(x).strip()])
            if symptoms_text:
                return f"My symptoms are {symptoms_text}."
        return "I am mainly feeling unwell, but specific symptoms are not listed."

    for phrase in known_phrases:
        phrase_norm = _normalize_text(phrase)
        if phrase_norm and phrase_norm in prompt_norm:
            return f"Yes, I have noticed {phrase_norm}."
    return "No, I haven't noticed that."


def _matched_history_fields(history, prompt_text):
    if not isinstance(history, dict) or not history:
        return []
    return [
        field_name
        for field_name, field_value in history.items()
        if _history_field_requested(prompt_text, field_name, field_value)
    ]


def _select_history_payload_for_prompt(history, prompt_text):
    if not isinstance(history, dict) or not history:
        return {}

    selected = {}

    detected_red_flag = _detect_red_flag_key(prompt_text)
    if detected_red_flag:
        selected["redFlags"] = {
            detected_red_flag: _resolve_red_flag_value(history, detected_red_flag)
        }

    detected_social_history_key = _detect_social_history_key(prompt_text)
    if detected_social_history_key:
        social_history = _get_history_social_history(history)
        selected["socialHistory"] = {
            detected_social_history_key: _lookup_dict_subvalue(social_history, detected_social_history_key, "Not specified")
        }

    matched_fields = _matched_history_fields(history, prompt_text)
    for field_name in matched_fields:
        if field_name in selected:
            continue
        field_value = history.get(field_name)
        if field_name == "priorHistory" and isinstance(field_value, list):
            selected_items = _selective_list_items_for_prompt(field_value, prompt_text)
            selected[field_name] = selected_items if selected_items else field_value
            continue

        if field_name == "familyHistory":
            selected_family = _selective_family_history_for_prompt(field_value, prompt_text)
            selected[field_name] = selected_family if selected_family else field_value
            continue

        if isinstance(field_value, dict):
            matched_nested = _matched_nested_keys_in_dict(field_value, prompt_text)
            if matched_nested:
                selected[field_name] = {nested_key: field_value.get(nested_key) for nested_key in matched_nested}
            else:
                selected[field_name] = field_value
        elif field_name == "socialHistory":
            parsed_social = _get_history_social_history(history)
            detected_social_history_key = _detect_social_history_key(prompt_text)
            if detected_social_history_key and parsed_social:
                selected[field_name] = {
                    detected_social_history_key: _lookup_dict_subvalue(parsed_social, detected_social_history_key, "Not specified")
                }
            else:
                selected[field_name] = parsed_social if parsed_social else field_value
        else:
            selected[field_name] = field_value

    if selected:
        return selected

    if any(keyword in _normalize_text(prompt_text) for keyword in OSCE_PATIENT_HISTORY_KEYWORDS) and _is_generic_history_prompt(prompt_text):
        for fallback_field in ["symptoms", "onset"]:
            if fallback_field in history:
                selected[fallback_field] = history.get(fallback_field)
    return selected


def render_history_results_card(case_item, workflow_state, extract_case_sections_fn):
    history, _, _, _, _ = extract_case_sections_fn(case_item)
    revealed_fields = workflow_state.get("revealed_history_fields", [])
    social_history_items = []

    lines = ["### History Results"]
    if not isinstance(history, dict) or not history:
        lines.append("- No seeded history available for this case.")
        return "\n".join(lines)

    if not revealed_fields:
        lines.append("- No history fields requested yet.")
        return "\n".join(lines)

    for field_name in revealed_fields:
        if isinstance(field_name, str) and field_name.startswith("redFlags."):
            red_flag_key = field_name.split(".", 1)[1]
            label = _humanize_key(red_flag_key).title()
            value = _resolve_red_flag_value(history, red_flag_key)
            lines.append(f"- **{label}:** {_format_history_value(value)}")
            continue

        if isinstance(field_name, str) and field_name.startswith("socialHistory."):
            social_key = field_name.split(".", 1)[1]
            social_history = _get_history_social_history(history)
            social_value = _lookup_dict_subvalue(social_history, social_key)
            if social_value is not None:
                social_history_items.append((social_key, social_value))
            continue

        if field_name == "socialHistory":
            continue

        if field_name not in history:
            continue
        label = str(field_name).replace("_", " ").title()
        lines.append(f"- **{label}:** {_format_history_value(history.get(field_name))}")

    if social_history_items:
        lines.append("- **Social History**")
        for social_key, social_value in social_history_items:
            lines.append(f"  - {str(social_key).replace('_', ' ').title()}: {_format_history_value(social_value)}")

    if len(lines) == 1:
        lines.append("- No matching seeded history field was found.")
    return "\n".join(lines)


def _build_information_gatekeeper_prompt(case_item):
    age = case_item.get("age", "Unknown")
    gender = case_item.get("gender", "Unknown")
    persona = str(case_item.get("patientPersona") or "").strip()
    complaint = case_item.get("chiefComplaint", "a concern")
    return (
        f"You are a {age}-year-old {gender} patient with {complaint}.\n"
        f"Patient persona: {persona if persona else 'No extra persona provided.'}\n"
        "CRITICAL RULE: You only know your symptoms and history. You DO NOT know your diagnosis, your lab results, or your internal physical findings (like heart sounds).\n"
        "Use natural layperson wording and avoid medical jargon unless patientPersona says the patient has a medical background.\n"
        "If the student asks a history question, answer using structuredData.history only.\n"
        "If the student says they want to examine you, reply exactly: 'Okay, what would you like to check?'\n"
        "DO NOT reveal vitals or exam findings unless the system has explicitly unlocked physical exam.\n"
    )


def _generate_history_answer_with_nvidia(gatekeeper_prompt, selective_history_payload, student_question):
    response = memory_manager.client.chat.completions.create(
        model="meta/llama-3.1-70b-instruct",
        messages=[
            {"role": "system", "content": gatekeeper_prompt},
            {
                "role": "user",
                "content": (
                    f"History data (JSON): {json.dumps(selective_history_payload, ensure_ascii=False)}\n"
                    f"Student question: {student_question}\n"
                    "Answer naturally as a patient in 1-2 sentences. Preserve all factual values exactly from History data (numbers, units, frequency, negations). Do not change any quantity or timing. "
                    "Do not output JSON, list syntax, square brackets, key names, or labels like 'social history'."
                )
            }
        ],
        temperature=0.2,
        max_tokens=120
    )
    return _clean_generated_answer(response.choices[0].message.content or "")


def _clean_generated_answer(answer_text):
    text = str(answer_text or "").strip()
    if not text:
        return ""

    text = re.sub(r"^\s*for\s+social\s+history\s*,?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[a-zA-Z\s]+:\s*\[\s*['\"]?", "", text)
    text = re.sub(r"\[\s*['\"]?", "", text)
    text = re.sub(r"['\"]?\s*\]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    if text and text[-1] not in ".!?":
        text += "."
    return text


def _collect_fact_strings(payload):
    facts = []

    def walk(value):
        if isinstance(value, dict):
            for nested_value in value.values():
                walk(nested_value)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        text = str(value or "").strip()
        if text:
            facts.append(text)

    walk(payload)
    return facts


def _answer_preserves_facts(answer_text, fact_strings):
    normalized_answer = _normalize_text(answer_text)
    for fact in fact_strings:
        if _normalize_text(fact) not in normalized_answer:
            return False
    return True


def _deterministic_history_response(selective_history_payload):
    def _clean_fact(value):
        text = _format_history_value(value)
        return str(text).strip().rstrip(".")

    if isinstance(selective_history_payload.get("redFlags"), dict):
        red_flag_key, red_flag_value = next(iter(selective_history_payload["redFlags"].items()))
        return f"For {_humanize_key(red_flag_key)}: {_clean_fact(red_flag_value)}."

    if isinstance(selective_history_payload.get("socialHistory"), dict):
        social_key, social_value = next(iter(selective_history_payload["socialHistory"].items()))
        return _social_history_nlp_response(social_key, social_value)

    selected_field = next(iter(selective_history_payload.items()))
    field_name, field_value = selected_field

    if field_name == "onset":
        onset_text = _clean_fact(field_value)
        symptom_values = selective_history_payload.get("associatedSymptoms")
        if isinstance(symptom_values, list) and symptom_values:
            symptom_text = ", ".join([str(x).strip() for x in symptom_values if str(x).strip()])
            if symptom_text:
                return f"It started about {onset_text}, with symptoms like {symptom_text}."
        return f"It started about {onset_text}."

    if field_name == "associatedSymptoms" and isinstance(field_value, list):
        symptoms_text = ", ".join([str(x).strip() for x in field_value if str(x).strip()])
        if symptoms_text:
            return f"My symptoms include {symptoms_text}."
        return "My symptoms are not clearly listed."

    if field_name == "medications":
        meds_text = _clean_fact(field_value)
        return f"I take {meds_text}."

    if field_name == "priorHistory":
        history_text = _clean_fact(field_value)
        return f"I have a history of {history_text}."

    if field_name == "familyHistory":
        family_text = _clean_fact(field_value)
        return f"In my family, {family_text}."

    if field_name == "rhythmDescription":
        rhythm_text = _clean_fact(field_value)
        return f"It feels like {rhythm_text}."

    label = str(field_name).replace("_", " ").lower()
    return f"About {label}, {_clean_fact(field_value)}."


def _social_history_nlp_response(social_key, social_value):
    value_text = _format_history_value(social_value).strip().rstrip(".")
    normalized = _normalize_text(value_text)

    if social_key == "smoking":
        if any(token in normalized for token in ["non smoker", "non-smoker", "never smoked", "never smoke", "do not smoke", "does not smoke"]):
            return "I don't smoke."
        if any(token in normalized for token in ["smoker", "smokes", "smoking", "cigarette", "tobacco"]):
            return f"I do smoke: {value_text}."
        return f"About smoking: {value_text}."

    if social_key == "caffeine":
        return f"For caffeine, {value_text}."
    if social_key == "alcohol":
        return f"For alcohol, {value_text}."
    if social_key == "drugUse":
        return f"For drug use, {value_text}."
    if social_key == "livingSituation":
        return f"I live as follows: {value_text}."

    return value_text if value_text.endswith((".", "!", "?")) else f"{value_text}."


def _social_history_not_specified_response(social_key):
    if social_key == "smoking":
        return "My smoking history is not specified."
    if social_key == "alcohol":
        return "My alcohol history is not specified."
    if social_key == "caffeine":
        return "My caffeine intake is not specified."
    if social_key == "drugUse":
        return "My drug-use history is not specified."
    if social_key == "livingSituation":
        return "My living situation is not specified."
    return "That part of my social history is not specified."


def _is_social_history_payload(payload):
    return isinstance(payload, dict) and isinstance(payload.get("socialHistory"), dict)


def _revealed_fields_from_payload(selective_history_payload):
    fields = []
    if not isinstance(selective_history_payload, dict):
        return fields

    fields.extend(selective_history_payload.keys())

    if isinstance(selective_history_payload.get("redFlags"), dict):
        fields.extend([f"redFlags.{k}" for k in selective_history_payload["redFlags"].keys()])

    if isinstance(selective_history_payload.get("socialHistory"), dict):
        fields.extend([f"socialHistory.{k}" for k in selective_history_payload["socialHistory"].keys()])

    return fields


def countercheck_history_prompt(history, prompt_text):
    payload = _select_history_payload_for_prompt(history, prompt_text)
    revealed_fields = _revealed_fields_from_payload(payload) if payload else []
    deterministic_answer = _deterministic_history_response(payload) if payload else "Could you clarify which part of my history you want to ask about?"
    return {
        "prompt": str(prompt_text or ""),
        "selected_payload": payload,
        "revealed_history_fields": revealed_fields,
        "deterministic_answer": deterministic_answer
    }


def countercheck_history_prompts(history, prompt_list):
    prompts = prompt_list if isinstance(prompt_list, list) else []
    return [countercheck_history_prompt(history, prompt) for prompt in prompts]


def resolve_vital_value(case_item, workflow_state, vital_key, extract_case_sections_fn):
    _, _, _, _, seeded_vitals = extract_case_sections_fn(case_item)
    key = _normalize_text(vital_key)

    if key in seeded_vitals:
        return seeded_vitals.get(key), False

    return "Not specified", False


def _detect_requested_vital_key(prompt_text):
    normalized_prompt = _normalize_text(prompt_text)
    for vital_key, aliases in VITAL_QUERY_ALIASES.items():
        if any(alias in normalized_prompt for alias in aliases):
            return vital_key
    return None


def _update_keywords_tracked(prompt_text, workflow_state):
    text = str(prompt_text or "").lower()
    if any(k in text for k in ["rest", "relieve", "better when rest"]):
        workflow_state["keywords_tracked"]["rest"] = True
    if any(k in text for k in ["exertion", "exercise", "walking", "activity", "climbing"]):
        workflow_state["keywords_tracked"]["exertion"] = True
    if any(k in text for k in ["smoke", "smoker", "smoking", "cigarette", "tobacco"]):
        workflow_state["keywords_tracked"]["smoking"] = True


def render_exam_results_card(case_item, workflow_state, extract_case_sections_fn):
    _, physical_exam, _, _, vitals = extract_case_sections_fn(case_item)
    findings = physical_exam.get("findings")
    generated_vitals = workflow_state.get("generated_vitals", {})

    lines = ["### Physical Exam Results", "**Vitals:**"]
    visible_items = []
    if isinstance(vitals, dict):
        visible_items.extend(list(vitals.items()))
    if isinstance(generated_vitals, dict) and generated_vitals:
        visible_items.extend(list(generated_vitals.items()))

    if visible_items:
        for key, value in visible_items:
            lines.append(f"- {str(key).replace('_', ' ').title()}: {value}")
    else:
        lines.append("- No vitals unlocked yet")

    lines.append("**General findings:**")
    if isinstance(findings, list) and findings:
        lines.extend([f"- {x}" for x in findings])
    elif isinstance(findings, dict) and findings:
        lines.extend([f"- {k}: {v}" for k, v in findings.items()])
    else:
        lines.append("- Not specified")
    return "\n".join(lines)


def build_case_scoped_reply(case_item, prompt, workflow_state, case_chat_key, extract_case_sections_fn, order_investigations_fn):
    history, physical_exam, investigations, _, vitals = extract_case_sections_fn(case_item)
    prompt_text = str(prompt or "").strip().lower()
    _update_keywords_tracked(prompt_text, workflow_state)
    matched_history_fields = _matched_history_fields(history, prompt)
    case_keywords = _case_keyword_set(case_item, history, physical_exam, investigations)

    if not workflow_state.get("chief_complaint_shared", False) and _should_start_with_intro(prompt):
        workflow_state["chief_complaint_shared"] = True
        workflow_state["phase"] = "history"
        return _intro_chief_complaint(case_item)

    if any(keyword in prompt_text for keyword in ["diagnosis", "what is it", "what do i have", "hidden diagnosis"]):
        return "I don't know, Doctor, what do you think it is?"

    if prompt_text.startswith("/examine") or "examine" in prompt_text:
        workflow_state["phase"] = "exam"
        workflow_state["exam_unlocked"] = True
        return "Okay, what would you like to check?"

    if ("blood pressure" in prompt_text or "check bp" in prompt_text or re.search(r"\bbp\b", prompt_text)) and _is_exam_intent(prompt_text):
        workflow_state["phase"] = "exam"
        workflow_state["exam_unlocked"] = True
        if "bp" not in workflow_state["revealed_vitals"]:
            workflow_state["revealed_vitals"].append("bp")
        return f"Sure. You can check it under Physical Exam tab. Blood pressure: {vitals.get('bp', 'not specified')}."

    if "ecg" in prompt_text or "electrocardiogram" in prompt_text:
        if not _has_investigation_order_intent(prompt_text):
            return "Please order ECG explicitly if you want me to proceed."
        workflow_state["phase"] = "investigations"
        order_investigations_fn(case_item, ["ECG"], workflow_state)
        if "ECG" not in workflow_state["revealed_investigations"]:
            workflow_state["revealed_investigations"].append("ECG")
        return "Noted. ECG has been ordered. Please check the Investigations tab for the result."

    if "troponin" in prompt_text or "labs" in prompt_text or "lab" in prompt_text:
        if not _has_investigation_order_intent(prompt_text):
            return "Please order the lab test explicitly if you want me to proceed."
        workflow_state["phase"] = "investigations"
        order_investigations_fn(case_item, ["Troponin"], workflow_state)
        if "Troponin" not in workflow_state["revealed_investigations"]:
            workflow_state["revealed_investigations"].append("Troponin")
        return "Noted. Troponin has been ordered. Please check the Investigations tab for the result."

    if any(keyword in prompt_text for keyword in OSCE_PATIENT_BLOCKED_TOPICS):
        return "irrelevant"

    if _is_symptom_query(prompt_text):
        workflow_state["phase"] = "history"
        return _symptom_response(prompt_text, history, case_item)

    detected_social_key = _detect_social_history_key(prompt_text)
    if detected_social_key:
        workflow_state["phase"] = "history"
        social_history = _get_history_social_history(history)
        social_value = _lookup_dict_subvalue(social_history, detected_social_key, None)
        workflow_state["revealed_history_fields"] = [f"socialHistory.{detected_social_key}"]
        if social_value is None:
            return _social_history_not_specified_response(detected_social_key)
        return _social_history_nlp_response(detected_social_key, social_value)

    keyword_payload = _best_keyword_history_payload(history, prompt)
    keyword_payload = _expand_onset_payload_with_symptoms(keyword_payload, history, case_item)
    if keyword_payload:
        workflow_state["phase"] = "history"
        workflow_state["revealed_history_fields"] = _revealed_fields_from_payload(keyword_payload)

        gatekeeper_prompt = _build_information_gatekeeper_prompt(case_item)
        try:
            llm_answer = _generate_history_answer_with_nvidia(gatekeeper_prompt, keyword_payload, prompt)
            facts = _collect_fact_strings(keyword_payload)
            if llm_answer and _is_social_history_payload(keyword_payload):
                return llm_answer
            if llm_answer and _answer_preserves_facts(llm_answer, facts):
                return llm_answer
        except Exception:
            pass

        return _deterministic_history_response(keyword_payload)

    if not _prompt_is_case_relevant(prompt_text, history, case_keywords):
        return "irrelevant"

    if matched_history_fields or any(keyword in prompt_text for keyword in OSCE_PATIENT_HISTORY_KEYWORDS):
        workflow_state["phase"] = "history"
        selective_history_payload = _select_history_payload_for_prompt(history, prompt)
        selective_history_payload = _expand_onset_payload_with_symptoms(selective_history_payload, history, case_item)
        if selective_history_payload:
            workflow_state["revealed_history_fields"] = _revealed_fields_from_payload(selective_history_payload)

        gatekeeper_prompt = _build_information_gatekeeper_prompt(case_item)

        try:
            llm_answer = _generate_history_answer_with_nvidia(gatekeeper_prompt, selective_history_payload, prompt)
            facts = _collect_fact_strings(selective_history_payload)
            if llm_answer and _is_social_history_payload(selective_history_payload):
                return llm_answer
            if llm_answer and _answer_preserves_facts(llm_answer, facts):
                return llm_answer
        except Exception:
            pass

        if selective_history_payload:
            return _deterministic_history_response(selective_history_payload)
        return "irrelevant"

    red_flag_key = _detect_red_flag_key(prompt_text)
    if red_flag_key:
        workflow_state["phase"] = "history"
        red_flag_value = _resolve_red_flag_value(history, red_flag_key)
        workflow_state["revealed_history_fields"] = [f"redFlags.{red_flag_key}"]
        return f"For {_humanize_key(red_flag_key)}: {_format_history_value(red_flag_value)}."

    social_history_key = _detect_social_history_key(prompt_text)
    if social_history_key:
        workflow_state["phase"] = "history"
        social_history = _get_history_social_history(history)
        social_value = _lookup_dict_subvalue(social_history, social_history_key, "Not specified")
        workflow_state["revealed_history_fields"] = [f"socialHistory.{social_history_key}"]
        if str(social_value).strip().lower() == "not specified":
            return _social_history_not_specified_response(social_history_key)
        return _social_history_nlp_response(social_history_key, social_value)

    if any(keyword in prompt_text for keyword in OSCE_PATIENT_EXAM_KEYWORDS):
        if not workflow_state.get("exam_unlocked") and not _is_exam_intent(prompt_text):
            return "I am not sure about exam findings yet. You can examine me first."
        workflow_state["exam_unlocked"] = True
        requested_vital = _detect_requested_vital_key(prompt_text)
        if requested_vital:
            if requested_vital not in workflow_state["revealed_vitals"]:
                workflow_state["revealed_vitals"].append(requested_vital)
            value, _ = resolve_vital_value(case_item, workflow_state, requested_vital, extract_case_sections_fn)
            label = requested_vital.upper()
            return f"My {label} is {value}."

        combined_vitals = {}
        if isinstance(vitals, dict):
            combined_vitals.update(vitals)
        if isinstance(workflow_state.get("generated_vitals"), dict):
            combined_vitals.update(workflow_state.get("generated_vitals"))
        if not combined_vitals:
            return "Physical exam vitals are not specified in this case."
        vitals_text = ", ".join([f"{str(k).upper()} {v}" for k, v in combined_vitals.items()])
        return f"On exam, my vitals are: {vitals_text}."

    return "irrelevant"
