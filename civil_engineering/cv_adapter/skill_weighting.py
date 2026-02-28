# civil_engineering/cv_adapter/skill_weighting.py

# def weight_skills(profile, job, intelligence):
#     """
#     Determine which skills and experiences should be emphasized,
#     neutral, or downplayed for a specific job.

#     Returns a dict with weights.
#     """
#     return {
#         "emphasize": [],
#         "neutral": [],
#         "downplay": []
#     }


# civil_engineering/cv_adapter/skill_weighting.py

def weight_skills(skills, intelligence):
    emphasized = intelligence.get("emphasize", [])
    downplayed = intelligence.get("downplay", [])

    emphasized_skills = []
    neutral_skills = []
    downplayed_skills = []

    for skill in skills:
        skill_lower = skill.lower()

        if any(key in skill_lower for key in emphasized):
            emphasized_skills.append(skill)
        elif any(key in skill_lower for key in downplayed):
            downplayed_skills.append(skill)
        else:
            neutral_skills.append(skill)

    # Final ordered skill list
    return emphasized_skills + neutral_skills + downplayed_skills
