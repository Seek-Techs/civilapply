# civil_engineering/cover_letter/cover_letter_builder.py

def build_cover_letter(profile, job, decision, cv_summary):
    """
    Build a conservative, decision-aware cover letter.
    """

    lines = []

    lines.append("Dear Hiring Manager,")
    lines.append("")

    # Opening — role aligned, non-aggressive
    lines.append(
        f"I am writing to apply for the {job.title} position."
    )

    # Fit framing
    if decision.get("seniority") == "overqualified":
        lines.append(
            "My background allows me to contribute immediately in a hands-on capacity, "
            "supporting site delivery and compliance requirements."
        )
    else:
        lines.append(
            "My experience aligns well with the requirements of the role."
        )

    # Core experience
    lines.append(
        cv_summary.strip()
    )

    # Closing — low pressure
    lines.append(
        "I would welcome the opportunity to contribute to your project team."
    )
    lines.append("")
    lines.append("Yours sincerely,")

    return "\n".join(lines)
