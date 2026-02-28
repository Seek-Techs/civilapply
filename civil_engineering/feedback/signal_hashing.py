# civil_engineering/feedback/signal_hashing.py

def hash_signal_bucket(signals: dict) -> str:
    """
    Convert normalized signals into a stable bucket key.
    """
    parts = []
    for key in sorted(signals.keys()):
        values = ",".join(sorted(signals[key]))
        parts.append(f"{key}:{values}")
    return "|".join(parts)
