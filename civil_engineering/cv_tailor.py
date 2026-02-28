# # civil_engineering/cv_tailor.py

# def generate_cv_summary(profile, job):
#     relevant_projects = set(profile["project_types"]).intersection(
#         set(job["project_types"])
#     )

#     summary = f"""
# Experienced Site Engineer with over {profile['experience']} years of hands-on experience
# delivering {', '.join(relevant_projects)} projects.

# Proven ability to supervise site activities, coordinate subcontractors, enforce HSE standards,
# and ensure compliance with drawings, specifications, and project schedules.

# Previously involved in large-scale construction works including industrial and infrastructure-related projects.
# """

#     return summary.strip()




def generate_cv_facts(profile, job):
    facts = {
        "role": profile["role"],
        "experience": profile["experience"],
        "projects": list(set(profile["project_types"]) & set(job["project_types"])),
        "all_projects": profile["project_types"]
    }
    return facts

def ai_rewrite_cv(facts):
    prompt = f"""
You are rewriting a CV summary for a civil engineering professional.

STRICT RULES:
- Do NOT add skills, experience, or projects not listed
- Do NOT change years of experience
- Do NOT invent certifications

FACTS (must be respected):
Role: {facts['role']}
Experience: {facts['experience']} years
Key Project Types: {', '.join(facts['projects']) or 'General Civil Works'}
Other Experience: {', '.join(facts['all_projects'])}

Rewrite a professional CV summary (max 120 words).
"""

    # Placeholder — AI integration comes later
    return prompt

