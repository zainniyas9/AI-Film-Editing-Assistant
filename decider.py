import json
import re
import time


def _format_context(items):
    lines = []
    for item in items:
        start = f"{item['start_sec']:.3f}"
        end = f"{item['end_sec']:.3f}"
        text = item["text"].replace("\n", " ").strip()
        lines.append(f"{start}-{end} {text}")
    return lines


def _build_prompt(candidates):
    lines = []
    lines.append(
        "Decide whether to CUT or KEEP each pause in a lecture video. "
        "Keep pauses that add meaning (emphasis, transition, reflection). "
        "Cut filler silence."
    )
    lines.append(
        'Respond with JSON only: [{"id":"...","decision":"CUT|KEEP","reason":"short"}]'
    )
    lines.append("Candidates:")
    for cand in candidates:
        lines.append(f"ID: {cand['id']}")
        lines.append(
            f"gap_start: {cand['gap_start']:.3f}, gap_end: {cand['gap_end']:.3f}, "
            f"gap_duration: {cand['gap_duration']:.3f}"
        )
        before_lines = _format_context(cand["context_before"])
        after_lines = _format_context(cand["context_after"])
        lines.append("context_before:")
        lines.extend(before_lines or ["(none)"])
        lines.append("context_after:")
        lines.extend(after_lines or ["(none)"])
    return "\n".join(lines)


def _extract_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _validate_response(payload, expected_ids):
    if not isinstance(payload, list):
        return None
    by_id = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        gap_id = item.get("id")
        decision = item.get("decision")
        reason = item.get("reason", "")
        if gap_id in expected_ids and decision in ("CUT", "KEEP"):
            by_id[gap_id] = {"id": gap_id, "decision": decision, "reason": str(reason)}
    if set(by_id.keys()) != set(expected_ids):
        return None
    return list(by_id.values())


def decide_gaps(candidates, client, batch_size=10, max_retries=2):
    results = []
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        expected_ids = [item["id"] for item in batch]
        prompt = _build_prompt(batch)
        attempt = 0
        batch_result = None
        while attempt <= max_retries:
            response_text = client.generate_text(prompt)
            payload = _extract_json(response_text)
            batch_result = _validate_response(payload, expected_ids)
            if batch_result is not None:
                break
            attempt += 1
            time.sleep(0.5)
        if batch_result is None:
            raise RuntimeError("Gemini returned invalid JSON after retries.")
        results.extend(batch_result)
    return results
