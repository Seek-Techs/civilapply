# civil_engineering/cover_letter/test_cover_letter_builder.py

def test_cover_letter_builder():
    profile = {"role": "Site Engineer"}
    job = type("Job", (), {"title": "Site Engineer"})()
    decision = {"seniority": "overqualified"}
    summary = "Experienced Site Engineer with 11 years of hands-on experience."

    from cover_letter.cover_letter_builder import build_cover_letter

    letter = build_cover_letter(profile, job, decision, summary)

    assert "Site Engineer position" in letter
    assert "hands-on capacity" in letter
