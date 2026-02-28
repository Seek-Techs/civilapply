# SITE_ENGINEER_PROFILE = {
#     "role": "Site Engineer",
#     "years_experience": 11,
#     "core_experience": [
#         "Buildings",
#         "Sewage Treatment Plant",
#         "Industrial",
#         "Refinery"
#     ],
#     "site_works": [
#         "Concrete works",
#         "Reinforcement fixing",
#         "Formwork installation",
#         "Site supervision",
#         "Setting out",
#         "Structural works"
#     ],
#     "quality_control": [
#         "Material inspection",
#         "ITP implementation",
#         "QA/QC coordination",
#         "Inspection with consultants",
#         "Non-conformance reporting"
#     ],
#     "tools": [
#         "AutoCAD",
#         "Excel"
#     ],
#     "responsibilities": [
#         "Supervision of subcontractors",
#         "Coordination with foremen",
#         "Daily site reporting",
#         "Progress tracking",
#         "Health and safety compliance"
#     ]
# }

# if __name__ == "__main__":
#     print("Role:", SITE_ENGINEER_PROFILE["role"])
#     print("Experience:", SITE_ENGINEER_PROFILE["years_experience"], "years")
#     print("Project types:", ", ".join(SITE_ENGINEER_PROFILE["core_experience"]))

def get_site_engineer_profile():
    return {
        "role": "Site Engineer",
        "experience": 11,
        "project_types": [
            "Buildings",
            "Sewage Treatment Plant",
            "Industrial",
            "Refinery"
        ],
        "skills": [
            "Material inspection",
            "ITP implementation",
            "QA/QC coordination",
            "Inspection with consultants",
            "Non-conformance reporting"
        ],
        "tools": [
            "AutoCAD",
            "Excel"
        ],
        "responsibilities": [
            "Supervision of subcontractors",
            "Coordination with foremen",
            "Daily site reporting",
            "Progress tracking",
            "Health and safety compliance"
        ]
    }
# later delete the below code
if __name__ == "__main__":
    profile = get_site_engineer_profile()
    print("Role:", profile["role"])
    print("Experience:", profile["experience"], "years")
    print("Project types:", ", ".join(profile["project_types"]))