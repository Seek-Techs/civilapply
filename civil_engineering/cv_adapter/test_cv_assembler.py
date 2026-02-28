# civil_engineering/cv_adapter/test_cv_assembler.py

def test_cv_assembly():
    summary = "Experienced Site Engineer with 11 years of experience."
    bullets = [
        "- Supervised workers on buildings projects",
        "- Coordinated site activities safely"
    ]

    from cv_adapter.cv_assembler import assemble_cv

    cv = assemble_cv(summary, bullets)

    assert "PROFESSIONAL SUMMARY" in cv
    assert "KEY EXPERIENCE" in cv
    assert bullets[0] in cv
