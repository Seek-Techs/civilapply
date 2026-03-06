# # PROJECT_SIGNAL_MAP = {
# #     "project monitoring": ["infrastructure"],
# #     "contractor": ["infrastructure"],
# #     "invoice": ["infrastructure"],
# #     "qa/qc": ["industrial"],
# #     "structural": ["buildings", "industrial"]
# # }

# # SKILL_SIGNAL_MAP = {
# #     "excel": ["cost tracking"],
# #     "power bi": ["reporting"],
# #     "python": ["automation"],
# #     "site supervision": ["construction management"]
# # }



# # Maps raw text → normalized project types
# PROJECT_SIGNAL_MAP = {
#     "road": ["infrastructure"],
#     "bridge": ["infrastructure"],
#     "highway": ["infrastructure"],
#     "rail": ["infrastructure"],
#     "refinery": ["refinery"],
#     "plant": ["industrial"],
#     "factory": ["industrial"],
#     "building": ["buildings"],
#     "residential": ["buildings"],
#     "commercial": ["buildings"]
# }


# # Maps raw text → normalized skills
# SKILL_SIGNAL_MAP = {
#     "site supervision": ["site_supervision"],
#     "supervision": ["site_supervision"],
#     "quantity survey": ["quantity_verification"],
#     "measurement": ["quantity_verification"],
#     "excel": ["excel"],
#     "power bi": ["power_bi"],
#     "python": ["python"],
#     "hse": ["hse"],
#     "qa/qc": ["qa_qc"]
# }


# # Maps normalized project types → risk flags
# RISK_SIGNAL_MAP = {
#     "refinery": "high_safety_environment",
#     "industrial": "high_safety_environment",
#     "oil": "high_safety_environment",
#     "gas": "high_safety_environment"
# }


# civil_engineering/normalization/signal_maps.py
#
# ── WHAT THIS FILE DOES ──────────────────────────────────────────────────────
# These three dictionaries are the "translation layer" between raw text
# (CV bullets, job descriptions) and the standardised terms the rest of
# the system uses for matching.
#
# HOW IT WORKS:
# normalize_cv() scans every word in the CV experience bullets.
# If it finds a key from these maps, it adds the mapped values to the CV.
#
# EXAMPLE:
#   CV bullet: "Supervised concrete works on site"
#   "concrete" is a key in PROJECT_SIGNAL_MAP → adds "buildings" and "infrastructure"
#   "site" is a key in SKILL_SIGNAL_MAP → adds "site_supervision"
#
# ── BUG FIXED: Missing keywords meant CV always had empty project_types ───────
# The original map had: "road", "bridge", "highway", "rail", "building" etc.
# But the actual CV bullets use words like: "concrete", "structural", "monitoring"
# None of those were in the map, so project_types was always empty.
# Empty project_types → no overlap with any job → confidence score of 15 → rejected.
#
# FIX: Added the keywords that actually appear in civil engineering CVs.


# Maps a keyword found in CV text → list of project type labels it implies
PROJECT_SIGNAL_MAP = {
    # ── Original keywords ──────────────────────────────────────────────────
    "road":        ["infrastructure"],
    "bridge":      ["infrastructure"],
    "highway":     ["infrastructure"],
    "rail":        ["infrastructure"],
    "refinery":    ["refinery"],
    "plant":       ["industrial"],
    "factory":     ["industrial"],
    "building":    ["buildings"],
    "residential": ["buildings"],
    "commercial":  ["buildings"],

    # ── Added: keywords that actually appear in civil engineering CVs ───────
    # "concrete" and "structural" are core infrastructure/buildings activities
    "concrete":    ["infrastructure", "buildings"],
    "structural":  ["infrastructure", "buildings"],
    # "monitoring" in a civil context = project monitoring on infrastructure
    "monitoring":  ["infrastructure"],
    # "site" on its own implies general civil/infrastructure work
    "site":        ["infrastructure"],
    # "drainage", "pipe", "sewer" = water/drainage infrastructure
    "drainage":    ["infrastructure"],
    "pipe":        ["infrastructure"],
    "sewer":       ["infrastructure"],
    # "foundation" = buildings
    "foundation":  ["buildings"],
}


# Maps a keyword found in CV text → list of skill labels it implies
SKILL_SIGNAL_MAP = {
    "site supervision":  ["site_supervision"],
    "supervision":       ["site_supervision"],
    "quantity survey":   ["quantity_verification"],
    "measurement":       ["quantity_verification"],
    "excel":             ["excel"],
    "power bi":          ["power_bi"],
    "python":            ["python"],
    "hse":               ["hse"],
    "qa/qc":             ["qa_qc"],
    # Added: common variations
    "qa":                ["qa_qc"],
    "qc":                ["qa_qc"],
    "autocad":           ["autocad"],
    "invoice":           ["quantity_verification"],
    "compliance":        ["hse"],
}


# Maps a normalised project type → risk flag it implies
RISK_SIGNAL_MAP = {
    "refinery":   "high_safety_environment",
    "industrial": "high_safety_environment",
    "oil":        "high_safety_environment",
    "gas":        "high_safety_environment",
}