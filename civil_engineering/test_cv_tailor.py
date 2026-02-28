# from cv_tailor import generate_cv_summary

# profile = {
#     "role": "Site Engineer",
#     "experience": 11,
#     "project_types": [
#         "Buildings",
#         "Sewage Treatment Plant",
#         "Industrial",
#         "Refinery"
#     ]
# }

# job = {
#     "title": "Site Engineer",
#     "years_required": 8,
#     "project_types": [
#         "Buildings",
#         "Industrial",
#         "Infrastructure"
#     ]
# }

# summary = generate_cv_summary(profile, job)

# print("Tailored CV Summary:")
# print(summary)


from civil_engineering.cv_tailor import generate_cv_facts, ai_rewrite_cv
from civil_engineering.site_engineer_profile import get_site_engineer_profile



profile = get_site_engineer_profile()

job = {
    "title": "Civil Engineer",
    "years_required": 3,
    "project_types": ["Buildings", "Infrastructure"]
}

facts = generate_cv_facts(profile, job)
prompt = ai_rewrite_cv(facts)

print("AI Prompt (Controlled):")
print(prompt)
