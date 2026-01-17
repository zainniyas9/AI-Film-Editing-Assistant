def detect_gaps(captions, min_gap=0.8, context=2):
    candidates = []
    if not captions:
        return candidates

    for i in range(len(captions) - 1):
        current = captions[i]
        next_cap = captions[i + 1]
        gap = next_cap["start_sec"] - current["end_sec"]
        if gap >= min_gap:
            before_start = max(0, i - context + 1)
            after_end = min(len(captions), i + 1 + context)
            context_before = captions[before_start : i + 1]
            context_after = captions[i + 1 : after_end]
            candidates.append(
                {
                    "id": f"gap_{i}",
                    "gap_start": current["end_sec"],
                    "gap_end": next_cap["start_sec"],
                    "gap_duration": gap,
                    "context_before": context_before,
                    "context_after": context_after,
                }
            )
    return candidates
