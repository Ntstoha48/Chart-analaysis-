"""Conservative signal gate. Similar observations are not proof of profitability."""

def approve_signal(result, previous_similar_count, min_confidence=0.82, min_similar=3):
    direction = str(result.get("direction", "NO SIGNAL")).upper()
    evidence = result.get("evidence", [])
    return bool(
        direction in ("CALL", "PUT")
        and result.get("actionable") is True
        and result.get("screenshot_quality") == "good"
        and float(result.get("confidence", 0)) >= min_confidence
        and isinstance(evidence, list) and len(evidence) >= 2
        and previous_similar_count >= min_similar
    )
