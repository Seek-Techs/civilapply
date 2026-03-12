# civil_engineering/cv_tailor.py
#
# ── SUPPORTED AI PROVIDERS (tried in this order) ─────────────────────────────
#
#  1. Ollama  — OFFLINE, FREE, runs on your PC, no internet needed
#               Install: ollama.com → then: ollama pull llama3.2:3b
#               No .env key needed — just having Ollama running is enough
#
#  2. Cohere  — FREE cloud API, works in Nigeria, no credit card
#               Sign up: dashboard.cohere.com
#               Add to .env:  COHERE_API_KEY=your_key_here
#
#  3. Groq    — FREE cloud API (blocked by Cloudflare in some Nigerian networks)
#               Add to .env:  GROQ_API_KEY=gsk_your_key_here
#
#  4. Anthropic — Paid Claude API
#               Add to .env:  ANTHROPIC_API_KEY=sk-ant-...
#
#  5. Rule-based — Always works, no internet, no AI, template-based output
#
# ── SENIOR DEV CONCEPT: "Provider chain" ─────────────────────────────────────
# Each provider is tried in order. If one fails for any reason
# (network blocked, API key wrong, model unavailable), we silently
# try the next one. The user always gets output — the quality just varies.
# This is called a "fallback chain" — production systems always have one.

import json
import os
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


# ── Prompt (same regardless of provider) ─────────────────────────────────────
# WHY THE SAME PROMPT FOR ALL?
# The prompt is the WHAT (what we want).
# The provider is the WHO (who we ask).
# Keeping them separate means we can swap providers without rewriting prompts.

SYSTEM_PROMPT = """You are a senior technical recruiter writing a CV summary for a civil engineer.

STRICT RULES — violating any of these makes the output unusable:
1. Use ONLY facts explicitly stated in CANDIDATE FACTS — do not infer, embellish, or generalise
2. NEVER say "large-scale", "several projects", "proven track record of delivery" unless the CV says so
3. The candidate's actual experience is: monitoring compliance, reinforcement inspection, drawing review
4. Mirror terminology from the job description where it matches the CV facts
5. Keep under 100 words
6. Start with title and years (e.g. "Civil Engineer with 11 years...")
7. Do NOT use the candidate's name
8. Return ONLY valid JSON — no markdown, no extra text"""

USER_PROMPT_TEMPLATE = """Tailor this CV summary for the job below.

CANDIDATE FACTS (do not change these):
- Name: {name}
- Title: {title}
- Experience: {total_years} years
- Project Types: {all_projects}
- Skills: {skills}
- Matching projects: {overlap}

JOB:
- Title: {job_title}
- Years Required: {years_required}
- Project Types: {job_projects}
- Required Skills: {job_skills}

Return EXACTLY this JSON and nothing else:
{{
  "summary": "professional CV summary under 100 words. Start with title+years (e.g. Civil Engineer with 11 years...). No name. No first person.",
  "key_skills": ["skill1", "skill2", "skill3"],
  "rationale": "one sentence on the main adaptation",
  "ats_keywords": ["keyword1", "keyword2"]
}}"""

# Groq models to try in order (handles model renames/deprecations)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]


# ── Shared utilities ──────────────────────────────────────────────────────────

def _build_prompt(cv: dict, job: dict, intelligence: dict) -> str:
    """Fill the prompt template with real CV and job data."""
    profile      = cv.get("profile", {})
    cv_projects  = cv.get("project_types", [])
    job_projects = [str(p) for p in job.get("project_types", [])]
    job_skills   = job.get("skills", [])
    overlap      = intelligence.get("project_alignment", {}).get("direct_overlap", [])

    return USER_PROMPT_TEMPLATE.format(
        name           = profile.get("name", "Candidate"),
        title          = profile.get("title", "Civil Engineer"),
        total_years    = profile.get("experience_years", "N/A"),
        all_projects   = ", ".join(str(p) for p in cv_projects) or "Civil Engineering",
        skills         = ", ".join(cv.get("skills", [])[:6]),
        overlap        = ", ".join(str(o) for o in overlap) or "Civil Engineering",
        job_title      = job.get("title", "Not specified"),
        years_required = job.get("years_required", "Not specified"),
        job_projects   = ", ".join(job_projects) or "Not specified",
        job_skills     = ", ".join(job_skills[:5]) or "Not specified",
    )


def _parse_response(raw_text: str) -> dict:
    """
    Safely extract JSON from AI response text.

    WHY SO CAREFUL?
    Even with clear instructions, AI models sometimes wrap their response
    in markdown fences (```json ... ```) or add explanation text before
    the JSON object. We handle all these cases defensively.
    """
    text = raw_text.strip()

    # Strip markdown fences if present
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    # Find the JSON object — from first { to last }
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]

    result = json.loads(text)

    # Validate required keys exist
    required = {"summary", "key_skills", "rationale", "ats_keywords"}
    missing  = required - set(result.keys())
    if missing:
        raise ValueError(f"Response missing keys: {missing}")

    return result


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    """
    Make a POST request with JSON body.

    WHY urllib INSTEAD OF requests?
    urllib is built into Python — zero installation.
    requests is friendlier but needs: pip install requests
    For simple API calls, urllib works perfectly.
    """
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Provider 1: Ollama (offline) ──────────────────────────────────────────────

def _call_ollama(prompt: str) -> dict:
    """
    Call a locally running Ollama model.

    HOW OLLAMA WORKS:
    When you install Ollama and run a model, it starts a local web server
    at http://localhost:11434. Your code talks to that server — no internet
    needed. The model runs entirely on your CPU/GPU.

    This is identical to calling a cloud API, except the "server" is
    running on your own machine.

    WHY localhost:11434?
    That's the port Ollama always uses by default. localhost means
    "this machine" — not the internet.

    Models to use (in order of quality vs speed):
        llama3.2:3b   — fast, good for 8GB RAM (download: ~2GB)
        llama3.1:8b   — better quality, needs 16GB RAM (download: ~5GB)
    """
    # Check which models are downloaded
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data   = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
    except Exception:
        raise ConnectionError(
            "Ollama is not running. "
            "Start it by opening a terminal and running: ollama serve"
        )

    if not models:
        raise ValueError(
            "Ollama is running but no models are downloaded. "
            "Run: ollama pull llama3.2:3b"
        )

    # Pick the best available model
    preferred = ["llama3.1:8b", "llama3.2:3b", "llama3:8b", "llama2:7b"]
    model = next((m for m in preferred if m in models), models[0])
    logger.info("Ollama: using model %s", model)

    # Full prompt combining system + user (Ollama handles both)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

    response = _post_json(
        "http://localhost:11434/api/generate",
        payload={
            "model":  model,
            "prompt": full_prompt,
            "stream": False,        # get full response at once, not token by token
            "options": {"temperature": 0.3},
        },
        headers={"Content-Type": "application/json"},
    )

    raw_text = response.get("response", "")
    result   = _parse_response(raw_text)
    result["model_used"] = model
    return result


# ── Provider 2: Cohere (free cloud) ──────────────────────────────────────────

def _call_cohere(prompt: str, api_key: str, retries: int = 2) -> dict:
    """
    Call the Cohere API with automatic retry on timeout.

    WHY RETRY?
    Network timeouts are common on Nigerian ISPs — a request that times out
    once will usually succeed on the second attempt. Retrying automatically
    means one bad second doesn't fall through to rule-based output.

    retries=2 means: 1 initial attempt + 2 retries = 3 tries total.
    """
    import time

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = _post_json(
                "https://api.cohere.com/v2/chat",
                payload={
                    "model": "command-r-plus-08-2024",
                    "messages": [
                        {"role": "system",  "content": SYSTEM_PROMPT},
                        {"role": "user",    "content": prompt},
                    ],
                    "max_tokens":  600,
                    "temperature": 0.3,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                },
            )

            raw_text = (
                response
                .get("message", {})
                .get("content", [{}])[0]
                .get("text", "")
            )

            if not raw_text:
                raise ValueError(f"Empty response from Cohere: {response}")

            return _parse_response(raw_text)

        except Exception as e:
            last_error = e
            if attempt < retries:
                wait = 2 * (attempt + 1)   # 2s, then 4s
                logger.warning("Cohere attempt %d failed (%s) — retrying in %ds",
                               attempt + 1, type(e).__name__, wait)
                time.sleep(wait)

    raise last_error


# ── Provider 3: Groq (free cloud, may be blocked) ────────────────────────────

def _call_groq(prompt: str, api_key: str) -> dict:
    """Call Groq API, trying multiple models."""
    last_error = None

    for model in GROQ_MODELS:
        try:
            response = _post_json(
                "https://api.groq.com/openai/v1/chat/completions",
                payload={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens":  600,
                    "temperature": 0.3,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                },
            )
            raw_text = response["choices"][0]["message"]["content"]
            result   = _parse_response(raw_text)
            result["model_used"] = model
            return result

        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ValueError("Invalid Groq API key") from e
            last_error = f"{model}: HTTP {e.code}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    raise RuntimeError(f"All Groq models failed. Last: {last_error}")


# ── Provider 4: Anthropic ─────────────────────────────────────────────────────

def _call_anthropic(prompt: str, api_key: str) -> dict:
    """Call Anthropic Claude API."""
    response = _post_json(
        "https://api.anthropic.com/v1/messages",
        payload={
            "model":      "claude-sonnet-4-6",
            "max_tokens": 600,
            "system":     SYSTEM_PROMPT,
            "messages":   [{"role": "user", "content": prompt}],
        },
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        },
    )
    raw_text = response["content"][0]["text"]
    return _parse_response(raw_text)


# ── Rule-based fallback ───────────────────────────────────────────────────────

def generate_cv_summary(cv: dict, job: dict) -> str:
    """
    Template-based CV summary — no AI, no internet, always works.
    Used when all AI providers fail or are unavailable.
    """
    profile      = cv.get("profile", {})
    cv_projects  = {str(p).lower() for p in cv.get("project_types", [])}
    job_projects = {str(p).lower() for p in job.get("project_types", [])}
    overlap      = sorted(cv_projects & job_projects)

    projects_text = ", ".join(p.title() for p in overlap) if overlap else "civil engineering"
    skills        = cv.get("skills", [])
    skills_clause = f" Technical skills include {', '.join(skills[:3])}." if skills else ""

    return (
        f"{profile.get('title', 'Civil Engineer')} with "
        f"{profile.get('experience_years', 0)}+ years delivering "
        f"{projects_text} projects. Proven track record in site supervision, "
        f"QA/QC compliance, and stakeholder coordination across construction "
        f"and infrastructure environments.{skills_clause}"
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def ai_rewrite_cv(cv: dict, job: dict, intelligence: dict,
                  api_key: str = "", model: str = "") -> dict:
    """
    Try every AI provider in order. Return the first one that works.

    Provider order:
      1. Ollama  — offline, no key needed, checked first
      2. Cohere  — free cloud, COHERE_API_KEY in .env
      3. Groq    — free cloud, GROQ_API_KEY in .env
      4. Anthropic — paid, ANTHROPIC_API_KEY in .env
      5. Rule-based — always works

    To add a new provider in future: add a _call_newprovider() function
    above, then add one try/except block here. Nothing else changes.
    """
    prompt = _build_prompt(cv, job, intelligence)

    # ── 1. Cohere (free cloud) — checked first for speed ─────────────────────
    cohere_key = os.environ.get("COHERE_API_KEY", "").strip()
    if cohere_key:
        try:
            result = _call_cohere(prompt, cohere_key)
            result["provider"] = "cohere"
            logger.info("CV tailored via Cohere")
            return result
        except Exception as e:
            logger.warning("Cohere failed: %s", e)

    # ── 2. Groq (free cloud) ─────────────────────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            result = _call_groq(prompt, groq_key)
            result["provider"] = "groq"
            logger.info("CV tailored via Groq")
            return result
        except Exception as e:
            logger.warning("Groq failed: %s", e)

    # ── 3. Ollama (offline, last resort — only if cloud fails) ───────────────
    if not os.environ.get("SKIP_OLLAMA"):
        try:
            result = _call_ollama(prompt)
            result["provider"] = "ollama (offline)"
            logger.info("CV tailored via Ollama")
            return result
        except ConnectionError:
            pass  # Ollama not running — silently skip
        except Exception as e:
            logger.warning("Ollama failed: %s", e)

    # ── 4. Anthropic (paid) ───────────────────────────────────────────────────
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", api_key).strip()
    if anthropic_key:
        try:
            result = _call_anthropic(prompt, anthropic_key)
            result["provider"] = "anthropic"
            logger.info("CV tailored via Anthropic")
            return result
        except Exception as e:
            logger.warning("Anthropic failed: %s", e)

    # ── 5. Rule-based (always works) ─────────────────────────────────────────
    logger.info("All AI providers unavailable — using rule-based summary")
    return {
        "summary":      generate_cv_summary(cv, job),
        "key_skills":   cv.get("skills", [])[:3],
        "rationale":    "Rule-based output. For AI writing: install Ollama (ollama.com) or add COHERE_API_KEY to .env",
        "ats_keywords": [],
        "provider":     "rule-based",
    }
