# civil_engineering/cv_adapter/bullet_rewriter.py
#
# ── WHAT THIS FILE DOES ──────────────────────────────────────────────────────
# Takes raw CV bullets and rewrites them to better match a specific job.
# Uses deterministic rules only — NO hallucination, NO new skills invented.
#
# ── BUG FIXED: Unconditional safety phrase appended to every bullet ───────────
# ORIGINAL CODE appended a safety phrase to EVERY bullet regardless of context:
#
#   if project:
#       rewritten_bullet = f"{text}, {safety_phrase} on {project} projects"
#   else:
#       rewritten_bullet = f"{text}, {safety_phrase}"
#
# This produced absurd output like:
#   "Reviewed and certified contractor invoices,
#    ensuring compliance with site safety procedures on infrastructure projects"
#
# WHY IS THIS WRONG?
# Safety context only makes sense for bullets about PHYSICAL site activities:
# supervision, inspections, HSE, concrete works, etc.
# It's meaningless — and sounds bizarre — appended to admin/financial bullets.
#
# FIX: Add a _is_site_activity() check. Only append safety context when the
# bullet is about an activity that would realistically involve site safety.
#
# ── SENIOR DEV CONCEPT: "Guard clauses" ──────────────────────────────────────
# Instead of wrapping logic in if/else blocks, we return early when conditions
# aren't met. This keeps the "happy path" flat and readable.
#
# INSTEAD OF:
#   if is_site_activity:
#       do_thing()
#   else:
#       pass  # nothing
#
# USE:
#   if not is_site_activity:
#       return text        ← guard clause: bail early
#   do_thing()

# ── Constants at module level ─────────────────────────────────────────────────
# WHY MODULE LEVEL?
# Constants should never live inside functions. If they're inside a function,
# they get re-created on every function call (wasteful) and can't be changed
# from outside without editing the function itself.

SAFETY_PHRASES = [
    "in line with approved site safety procedures",
    "under established HSE controls",
    "ensuring compliance with site safety standards",
]

# Keywords that suggest a bullet describes a PHYSICAL site activity
# (where safety context is genuinely relevant)
#
# DESIGN DECISION: "contractor" was removed even though it sounds site-related.
# It also appears in admin sentences like "certified contractor invoices" —
# where adding safety context would be grammatically wrong and misleading.
# Keywords here should indicate PHYSICAL ACTIONS, not just nouns that happen
# to appear in construction contexts.
SITE_ACTIVITY_KEYWORDS = {
    "supervision", "supervise", "supervised",
    "inspection", "inspect", "inspected",
    "concrete", "structural", "construction",
    "hse", "safety", "compliance",
    "site works", "site activities",          # two-word phrases to avoid false matches
    "installation", "installed", "erection",
    "piling", "excavation", "formwork",
    "monitoring works", "structural works",   # specific compound forms from this CV
}

# Verbs to normalise (tone softening for overqualified candidates)
# e.g. "led" sounds too senior for a junior/mid role → "coordinated"
VERB_NORMALISATION = {
    "responsible for supervising": "supervised",
    "supported with":              "supported",
    "assisted with":               "supported",
    "led":                         "coordinated",
    "spearheaded":                 "coordinated",
    "commanded":                   "directed",
}


# ── Private helpers ───────────────────────────────────────────────────────────

def _clean_bullet(text: str) -> str:
    """Remove leading dashes, hyphens, and whitespace."""
    return text.lstrip("- ").strip()


def _normalise_verbs(text: str) -> str:
    """
    Replace overly strong verbs with more measured alternatives.
    Only used when the candidate is classified as overqualified —
    so the tone matches what the employer expects for the role.
    """
    text_lower = text.lower()
    for phrase, replacement in VERB_NORMALISATION.items():
        if phrase in text_lower:
            # Replace in the lowercased version, then re-capitalise
            return text_lower.replace(phrase, replacement)
    return text_lower


def _is_site_activity(text: str) -> bool:
    """
    Return True if the bullet describes a physical site/construction activity.

    This is a HEURISTIC (educated guess based on keywords), not perfect.
    But it's far better than blindly appending safety context to every bullet.

    Example:
        "Verified contractor-executed structural works"  → True (site activity)
        "Reviewed and certified contractor invoices"     → False (admin activity)
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in SITE_ACTIVITY_KEYWORDS)


def _select_safety_phrase(index: int) -> str:
    """
    Pick a safety phrase by rotating through the list.
    Using modulo (%) ensures we cycle: index 0→phrase 0, 1→phrase 1, 2→phrase 0 again.

    WHY ROTATE instead of always using phrase 0?
    Variety. A CV with three identical safety phrases looks like a template.
    Rotating them looks more natural.
    """
    return SAFETY_PHRASES[index % len(SAFETY_PHRASES)]


def _polish(text: str) -> str:
    """Ensure the sentence starts with a capital letter."""
    text = text.strip()
    if not text:
        return text
    return text[0].upper() + text[1:]


# ── Public function ───────────────────────────────────────────────────────────

def rewrite_bullets(
    bullets: list[str],
    profile: dict,
    job,            # ParsedJob object or dict
    intelligence: dict,
) -> list[str]:
    """
    Rewrite a list of CV bullets to better align with a specific job.

    Rules applied (in order):
    1. Clean input (strip leading dashes)
    2. Normalise verbs (only if overqualified)
    3. Append safety context (only if it's a site activity AND high-safety job)
    4. Append project alignment (always, to connect experience to the job)
    5. Polish capitalisation

    Args:
        bullets:      Raw bullet strings from the CV
        profile:      Candidate profile dict (for name, title etc.)
        job:          Job object — can be dict or ParsedJob (we handle both)
        intelligence: Intelligence dict from build_intelligence()

    Returns:
        List of rewritten bullet strings, each prefixed with "- "
    """
    seniority   = intelligence.get("seniority", "matched")
    risk_flags  = intelligence.get("risk_flags", [])
    is_high_risk = "high_safety_environment" in risk_flags

    # Safely extract the first project type regardless of whether job is a dict or object
    # WHY handle both? The original code used hasattr() checks — fragile.
    # Better: try attribute access, fall back to dict access.
    project_label = None
    try:
        if hasattr(job, "project_types") and job.project_types:
            raw_pt = job.project_types[0]
            # Handle enum values (e.g. ProjectType.INFRASTRUCTURE) or plain strings
            project_label = raw_pt.value if hasattr(raw_pt, "value") else str(raw_pt).lower()
        elif isinstance(job, dict) and job.get("project_types"):
            project_label = str(job["project_types"][0]).lower()
    except (IndexError, AttributeError):
        project_label = None

    rewritten = []
    for i, bullet in enumerate(bullets):

        # ── Step 1: Clean ──────────────────────────────────────────────────
        text = _clean_bullet(bullet)

        # ── Step 2: Verb normalisation (overqualified only) ────────────────
        # We only soften verbs when the candidate is clearly senior for the role.
        # For a matched or underqualified candidate, keep their strongest verbs.
        if seniority in ("overqualified", "tolerated_overqualified"):
            text = _normalise_verbs(text)
        else:
            text = text.lower()

        # ── Step 3: Safety context (site activities in high-risk jobs only) ──
        # FIXED: Was unconditional. Now gated on both conditions.
        if is_high_risk and _is_site_activity(text):
            safety = _select_safety_phrase(i)
            text = f"{text}, {safety}"

        # ── Step 4: Project alignment ──────────────────────────────────────
        # Only append if the project type isn't already mentioned in the bullet.
        # Avoids: "...on infrastructure projects on infrastructure projects"
        if project_label and project_label not in text.lower():
            text = f"{text} on {project_label} projects"

        # ── Step 5: Polish ─────────────────────────────────────────────────
        rewritten.append(f"- {_polish(text)}")

    return rewritten
