# civil_engineering/intelligence/test_decision_explainer.py

def test_decision_explanation():
    match_result = {
        "qualified": True,
        "score": 86.7
    }

    intelligence = {
        "emphasize": ["buildings"],
        "risk_flags": ["high_safety_environment"]
    }

    job = {
        "title": "Civil Engineer"
    }

    from intelligence.decision_explainer import explain_decision

    explanation = explain_decision(match_result, intelligence, job)

    assert len(explanation) >= 3
    assert "buildings" in " ".join(explanation).lower()
