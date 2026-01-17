def compute_keep_segments(captions, candidates, decisions, merge_gap=0.1, min_keep=0.25):
    if captions:
        total_duration = max(item["end_sec"] for item in captions)
    else:
        total_duration = 0.0

    decision_map = {item["id"]: item for item in decisions}
    segments = []
    cursor = 0.0

    for cand in candidates:
        decision = decision_map.get(cand["id"], {}).get("decision", "KEEP")
        if decision == "CUT":
            if cand["gap_start"] > cursor:
                segments.append([cursor, cand["gap_start"]])
            cursor = max(cursor, cand["gap_end"])

    if total_duration > cursor:
        segments.append([cursor, total_duration])

    segments = _merge_by_gap(segments, merge_gap)
    segments = _enforce_min_length(segments, min_keep)

    return segments, total_duration


def _merge_by_gap(segments, gap_threshold):
    if not segments:
        return []
    merged = [segments[0][:]]
    for start, end in segments[1:]:
        if start - merged[-1][1] <= gap_threshold:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _enforce_min_length(segments, min_len):
    if not segments:
        return []
    i = 0
    while i < len(segments):
        start, end = segments[i]
        if end - start >= min_len or len(segments) == 1:
            i += 1
            continue
        if i == 0 and len(segments) > 1:
            segments[1][0] = start
            segments.pop(0)
            continue
        if i > 0:
            segments[i - 1][1] = end
            segments.pop(i)
            continue
        i += 1
    return segments
