from civil_engineering.scoring.constants import (
    AUTO_APPLY_THRESHOLD,
    STRATEGIC_REVIEW_THRESHOLD,
)

def rank_job(confidence: int):
    """
    Converts confidence score into rank + recommended action.
    """

    if confidence >= AUTO_APPLY_THRESHOLD:
        return {
            "rank": "strong_fit",
            "action": "apply_confidently",
            "requires_human_review": False
        }

    if confidence >= STRATEGIC_REVIEW_THRESHOLD:
        return {
            "rank": "strategic_fit",
            "action": "apply_only_if_strategic",
            "requires_human_review": True
        }

    return {
        "rank": "rejected",
        "action": "do_not_apply",
        "requires_human_review": False
    }