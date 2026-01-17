import re


TIME_LINE_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[.,]\d{3})"
)


def parse_timestamp(ts):
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid timestamp: {ts}")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def parse_time_token(token):
    token = token.strip()
    if ":" in token:
        return parse_timestamp(token)
    return float(token)


def detect_format(lines):
    for line in lines:
        if line.strip().upper() == "WEBVTT":
            return "vtt"
    for line in lines:
        if TIME_LINE_RE.search(line):
            return "srt_vtt"
    return "plain"


def parse_srt_vtt(lines):
    entries = []
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.isdigit() and i + 1 < total and "-->" in lines[i + 1]:
            i += 1
            line = lines[i].strip()
        match = TIME_LINE_RE.match(line)
        if match:
            start = parse_timestamp(match.group("start"))
            end = parse_timestamp(match.group("end"))
            i += 1
            text_lines = []
            while i < total and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            text = " ".join(text_lines).strip()
            entries.append({"start_sec": start, "end_sec": end, "text": text})
        else:
            i += 1
    return entries


def parse_plain(lines):
    entries = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        try:
            start = parse_time_token(parts[0])
            end = parse_time_token(parts[1])
        except ValueError:
            continue
        text = " ".join(parts[2:]).strip()
        entries.append({"start_sec": start, "end_sec": end, "text": text})
    return entries


def parse_transcript(path):
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()

    lines = content.splitlines()
    fmt = detect_format(lines)

    if fmt in ("vtt", "srt_vtt"):
        entries = parse_srt_vtt(lines)
    else:
        entries = parse_plain(lines)

    entries.sort(key=lambda item: (item["start_sec"], item["end_sec"]))
    return entries
