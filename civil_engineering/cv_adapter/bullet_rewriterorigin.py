# # # civil_engineering/bullet_rewriter.py

# # def rewrite_bullets(bullets, profile, job, intelligence):
# #     """
# #     Rewrite CV bullets using deterministic rules.
# #     No hallucination. No new skills. No experience inflation.
# #     """

# #     rewritten = []

# #     for bullet in bullets:
# #         original = bullet
# #         text = bullet

# #         # -------------------------------
# #         # RULE GROUP 1 — SENIORITY SOFTENING
# #         # -------------------------------
# #         if intelligence.get("seniority") == "overqualified":
# #             text = soften_seniority(text)

# #         # -------------------------------
# #         # RULE GROUP 2 — SAFETY AWARENESS
# #         # -------------------------------
# #         if "high_safety_environment" in intelligence.get("risk_flags", []):
# #             text = add_safety_context(text)

# #         # -------------------------------
# #         # RULE GROUP 3 — PROJECT ALIGNMENT
# #         # -------------------------------
# #         text = align_project_type(text, job.project_types)

# #         # -------------------------------
# #         # RULE GROUP 4 — VERB NORMALIZATION
# #         # -------------------------------
# #         text = normalize_verbs(text)

# #         # -------------------------------
# #         # RULE GROUP 5 — SCOPE CLARITY
# #         # -------------------------------
# #         text = clarify_scope(text)

# #         rewritten.append(text)

# #     return rewritten


# # # =====================================================
# # # Helper functions (each handles ONE responsibility)
# # # =====================================================

# # def soften_seniority(text):
# #     replacements = {
# #         "led": "supervised",
# #         "managed": "coordinated",
# #         "headed": "oversaw",
# #         "commanded": "supervised",
# #         "spearheaded": "coordinated"
# #     }

# #     for k, v in replacements.items():
# #         text = text.replace(k, v).replace(k.capitalize(), v)

# #     return text


# # def add_safety_context(text):
# #     safety_phrases = [
# #         "ensuring compliance with safety procedures",
# #         "in line with approved method statements"
# #     ]

# #     # Only add if safety not already implied
# #     if "safety" not in text.lower():
# #         text = f"{text}, ensuring compliance with safety procedures"

# #     return text


# # def align_project_type(text, project_types):
# #     for project in project_types:
# #         if project.lower() in text.lower():
# #             return text

# #     if project_types:
# #         return f"{text} on {project_types[0].lower()} projects"

# #     return text


# # def normalize_verbs(text):
# #     verb_map = {
# #         "assisted": "supported",
# #         "single-handedly": "personally",
# #         "executed": "carried out"
# #     }

# #     for k, v in verb_map.items():
# #         text = text.replace(k, v).replace(k.capitalize(), v)

# #     return text


# # def clarify_scope(text):
# #     vague_phrases = ["responsible for", "involved in"]

# #     for phrase in vague_phrases:
# #         if phrase in text.lower():
# #             return text + " as part of assigned site responsibilities"

# #     return text



# # civil_engineering/cv_adapter/bullet_rewriter.py

# # --- Phrase libraries (controlled, deterministic) ---

# SAFETY_PHRASES = [
#     "ensuring compliance with site safety procedures",
#     "in accordance with approved safety standards",
#     "under established site safety controls",
# ]

# VERB_NORMALIZATION = {
#     "responsible for supervising": "supervised",
#     "supported with": "prepared",
#     "assisted with": "supported",
#     "led": "coordinated",
#     "spearheaded": "coordinated",
# }


# def normalize_verb(text: str) -> str:
#     text_lower = text.lower()
#     for phrase, replacement in VERB_NORMALIZATION.items():
#         if phrase in text_lower:
#             return text_lower.replace(phrase, replacement)
#     return text_lower


# def select_safety_phrase(index: int) -> str:
#     """Deterministic rotation of safety phrases"""
#     return SAFETY_PHRASES[index % len(SAFETY_PHRASES)]


# def polish_sentence(text: str) -> str:
#     text = text.strip()
#     return text[0].upper() + text[1:]


# def rewrite_bullets(bullets, profile, job, intelligence):
#     rewritten = []

#     for i, bullet in enumerate(bullets):
#         # 1. CLEAN INPUT (remove existing dashes)
#         clean_bullet = bullet.lstrip("- ").strip()

#         # 2. NORMALIZE VERBS
#         text = normalize_verb(clean_bullet)

#         # 3. PROJECT ALIGNMENT
#         project = None
#         if hasattr(job, "project_types") and job.project_types:
#             project = job.project_types[0].lower()
#         elif isinstance(job, dict) and job.get("project_types"):
#             project = job["project_types"][0].lower()

#         # 4. SAFETY (deterministic)
#         safety_phrase = select_safety_phrase(i)

#         # 5. BUILD BULLET
#         if project:
#             rewritten_bullet = f"{text}, {safety_phrase} on {project} projects"
#         else:
#             rewritten_bullet = f"{text}, {safety_phrase}"

#         # 6. POLISH + SINGLE DASH
#         rewritten.append(f"- {polish_sentence(rewritten_bullet)}")
        

#     return rewritten


# civil_engineering/guardrails/confidence_decay.py
#
# ── WHAT THIS FILE DOES ──────────────────────────────────────────────────────
# Reduces confidence when the candidate has already applied to similar roles.
# The logic: if you've applied to 3 "Site Engineer" jobs today and they're
# not responding, keep sending more is likely a bad strategy.
#
# ── BUG FIXED: KeyError on job["confidence"] ─────────────────────────────────
# ORIGINAL CODE:
#
#   def apply_confidence_decay(job, previous_applications):
#       base_confidence = job["confidence"]   ← CRASH
#
# WHERE IS THIS CALLED FROM?
# guardrail_engine.py calls it like this:
#
#   adjusted_confidence = apply_confidence_decay(job_summary, applications)
#
# And job_summary is passed in as the raw job dict loaded from disk:
#   with open(job_file) as f:
#       job = json.load(f)
#
# A raw job JSON looks like:
#   {"title": "Site Engineer", "years_required": 3, "project_types": [...]}
#
# There is NO "confidence" key in a raw job file.
# Confidence is computed LATER by calculate_confidence().
# So job["confidence"] raises KeyError every single time.
#
# FIX:
# The function should receive the CONFIDENCE VALUE as a direct argument,
# not try to extract it from the job dict.
# This separates concerns: the caller is responsible for computing confidence,
# this function is responsible for applying decay to it.
#
# ── SENIOR DEV CONCEPT: "Don't reach into objects for what you need" ─────────
# If a function needs a specific VALUE, pass that value directly.
# Don't make the function dig into an object to find it.
#
# BAD:  apply_confidence_decay(job, ...)  ← function assumes job has "confidence"
# GOOD: apply_confidence_decay(confidence, job_title, ...)  ← explicit


def apply_confidence_decay(
    base_confidence: float,
    job_title: str | None,
    previous_applications: list[dict],
) -> float:
    """
    Apply decay to a confidence score based on how many similar roles
    have already been applied to in the current session.

    The more repeat applications to the same title, the lower the adjusted
    confidence — signalling diminishing returns on the same strategy.

    Args:
        base_confidence:        The raw confidence score (0–100)
        job_title:              Title of the current job (used for repeat detection)
        previous_applications:  List of application dicts from the tracker

    Returns:
        Adjusted confidence score (float, clamped to 0 minimum)

    Decay schedule:
        0 repeats → no decay        (fresh title, full confidence)
        1 repeat  → -5 points       (tried once, minor reduction)
        2 repeats → -12 points      (tried twice, notable reduction)
        3+ repeats → 0 (hard block) (saturated, stop applying to this title)
    """
    if not job_title:
        # No title to compare against — can't detect repeats, return as-is
        return base_confidence

    # Count how many previous applications had the same job title
    repeats = sum(
        1 for app in previous_applications
        if app.get("job_title") == job_title
    )

    if repeats == 0:
        return base_confidence
    elif repeats == 1:
        return max(0.0, base_confidence - 5)
    elif repeats == 2:
        return max(0.0, base_confidence - 12)
    else:
        # 3+ repeats: hard block — return 0 to trigger the guardrail
        return 0.0