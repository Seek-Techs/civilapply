# PROJECT_SIGNAL_MAP = {
#     "project monitoring": ["infrastructure"],
#     "contractor": ["infrastructure"],
#     "invoice": ["infrastructure"],
#     "qa/qc": ["industrial"],
#     "structural": ["buildings", "industrial"]
# }

# SKILL_SIGNAL_MAP = {
#     "excel": ["cost tracking"],
#     "power bi": ["reporting"],
#     "python": ["automation"],
#     "site supervision": ["construction management"]
# }



# Maps raw text → normalized project types
PROJECT_SIGNAL_MAP = {
    "road": ["infrastructure"],
    "bridge": ["infrastructure"],
    "highway": ["infrastructure"],
    "rail": ["infrastructure"],
    "refinery": ["refinery"],
    "plant": ["industrial"],
    "factory": ["industrial"],
    "building": ["buildings"],
    "residential": ["buildings"],
    "commercial": ["buildings"]
}


# Maps raw text → normalized skills
SKILL_SIGNAL_MAP = {
    "site supervision": ["site_supervision"],
    "supervision": ["site_supervision"],
    "quantity survey": ["quantity_verification"],
    "measurement": ["quantity_verification"],
    "excel": ["excel"],
    "power bi": ["power_bi"],
    "python": ["python"],
    "hse": ["hse"],
    "qa/qc": ["qa_qc"]
}


# Maps normalized project types → risk flags
RISK_SIGNAL_MAP = {
    "refinery": "high_safety_environment",
    "industrial": "high_safety_environment",
    "oil": "high_safety_environment",
    "gas": "high_safety_environment"
}
