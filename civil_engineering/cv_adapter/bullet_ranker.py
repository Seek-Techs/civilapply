# cv_adapter/bullet_ranker.py

def score_bullet(bullet: str, intelligence: dict) -> int:
    bullet_lower = bullet.lower()

    for domain in intelligence.get("emphasize", []):
        if domain in bullet_lower:
            return 3

    for domain in intelligence.get("neutral", []):
        if domain in bullet_lower:
            return 2

    for domain in intelligence.get("downplay", []):
        if domain in bullet_lower:
            return 1

    return 0  # unknown / generic


def rank_bullets(bullets: list, intelligence: dict) -> list:
    """
    Sort bullets by relevance to the job.
    Higher score = higher priority.
    """

    scored = [(score_bullet(b, intelligence), b) for b in bullets]

    # Sort by score DESCENDING, preserve stability
    scored.sort(key=lambda x: x[0], reverse=True)

    return [b for _, b in scored]
