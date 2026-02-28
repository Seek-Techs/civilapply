# civil_engineering/cv_adapter/cv_assembler.py

def assemble_cv(summary, bullets):
    """
    Assemble final CV content from structured components.
    """

    cv = []

    # Summary section
    cv.append("PROFESSIONAL SUMMARY")
    cv.append(summary.strip())
    cv.append("")

    # Experience section
    cv.append("KEY EXPERIENCE")
    for bullet in bullets:
        cv.append(bullet)

    return "\n".join(cv)
