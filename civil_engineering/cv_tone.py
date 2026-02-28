def determine_cv_tone(seniority):
    if seniority == "overqualified":
        return "focused, non-threatening, hands-on"
    elif seniority == "senior":
        return "leadership, delivery, accountability"
    elif seniority == "mid":
        return "execution, coordination, problem-solving"
    elif seniority == "junior":
        return "learning, support, technical growth"
    else:
        return "professional and clear"
