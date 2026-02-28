# # civil_engineering/bullet_rewriter.py

# def rewrite_bullets(bullets, profile, job, intelligence):
#     """
#     Rewrite CV bullets using deterministic rules.
#     No hallucination. No new skills. No experience inflation.
#     """

#     rewritten = []

#     for bullet in bullets:
#         original = bullet
#         text = bullet

#         # -------------------------------
#         # RULE GROUP 1 — SENIORITY SOFTENING
#         # -------------------------------
#         if intelligence.get("seniority") == "overqualified":
#             text = soften_seniority(text)

#         # -------------------------------
#         # RULE GROUP 2 — SAFETY AWARENESS
#         # -------------------------------
#         if "high_safety_environment" in intelligence.get("risk_flags", []):
#             text = add_safety_context(text)

#         # -------------------------------
#         # RULE GROUP 3 — PROJECT ALIGNMENT
#         # -------------------------------
#         text = align_project_type(text, job.project_types)

#         # -------------------------------
#         # RULE GROUP 4 — VERB NORMALIZATION
#         # -------------------------------
#         text = normalize_verbs(text)

#         # -------------------------------
#         # RULE GROUP 5 — SCOPE CLARITY
#         # -------------------------------
#         text = clarify_scope(text)

#         rewritten.append(text)

#     return rewritten


# # =====================================================
# # Helper functions (each handles ONE responsibility)
# # =====================================================

# def soften_seniority(text):
#     replacements = {
#         "led": "supervised",
#         "managed": "coordinated",
#         "headed": "oversaw",
#         "commanded": "supervised",
#         "spearheaded": "coordinated"
#     }

#     for k, v in replacements.items():
#         text = text.replace(k, v).replace(k.capitalize(), v)

#     return text


# def add_safety_context(text):
#     safety_phrases = [
#         "ensuring compliance with safety procedures",
#         "in line with approved method statements"
#     ]

#     # Only add if safety not already implied
#     if "safety" not in text.lower():
#         text = f"{text}, ensuring compliance with safety procedures"

#     return text


# def align_project_type(text, project_types):
#     for project in project_types:
#         if project.lower() in text.lower():
#             return text

#     if project_types:
#         return f"{text} on {project_types[0].lower()} projects"

#     return text


# def normalize_verbs(text):
#     verb_map = {
#         "assisted": "supported",
#         "single-handedly": "personally",
#         "executed": "carried out"
#     }

#     for k, v in verb_map.items():
#         text = text.replace(k, v).replace(k.capitalize(), v)

#     return text


# def clarify_scope(text):
#     vague_phrases = ["responsible for", "involved in"]

#     for phrase in vague_phrases:
#         if phrase in text.lower():
#             return text + " as part of assigned site responsibilities"

#     return text



# civil_engineering/cv_adapter/bullet_rewriter.py

# --- Phrase libraries (controlled, deterministic) ---

SAFETY_PHRASES = [
    "ensuring compliance with site safety procedures",
    "in accordance with approved safety standards",
    "under established site safety controls",
]

VERB_NORMALIZATION = {
    "responsible for supervising": "supervised",
    "supported with": "prepared",
    "assisted with": "supported",
    "led": "coordinated",
    "spearheaded": "coordinated",
}


def normalize_verb(text: str) -> str:
    text_lower = text.lower()
    for phrase, replacement in VERB_NORMALIZATION.items():
        if phrase in text_lower:
            return text_lower.replace(phrase, replacement)
    return text_lower


def select_safety_phrase(index: int) -> str:
    """Deterministic rotation of safety phrases"""
    return SAFETY_PHRASES[index % len(SAFETY_PHRASES)]


def polish_sentence(text: str) -> str:
    text = text.strip()
    return text[0].upper() + text[1:]


def rewrite_bullets(bullets, profile, job, intelligence):
    rewritten = []

    for i, bullet in enumerate(bullets):
        # 1. CLEAN INPUT (remove existing dashes)
        clean_bullet = bullet.lstrip("- ").strip()

        # 2. NORMALIZE VERBS
        text = normalize_verb(clean_bullet)

        # 3. PROJECT ALIGNMENT
        project = None
        if hasattr(job, "project_types") and job.project_types:
            project = job.project_types[0].lower()
        elif isinstance(job, dict) and job.get("project_types"):
            project = job["project_types"][0].lower()

        # 4. SAFETY (deterministic)
        safety_phrase = select_safety_phrase(i)

        # 5. BUILD BULLET
        if project:
            rewritten_bullet = f"{text}, {safety_phrase} on {project} projects"
        else:
            rewritten_bullet = f"{text}, {safety_phrase}"

        # 6. POLISH + SINGLE DASH
        rewritten.append(f"- {polish_sentence(rewritten_bullet)}")
        

    return rewritten
