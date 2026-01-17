import csv
import json
import os
import uuid

from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from cutter import compute_keep_segments
from decider import decide_gaps
from ffmpeg_render import render_video
from gap_detector import detect_gaps
from gemini_client import GeminiClient
from transcript_parser import parse_transcript


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
ALLOWED_TRANSCRIPT_EXTENSIONS = {".srt", ".vtt", ".txt"}

BASE_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs", "web")

app = Flask(__name__)


def _is_allowed(filename, allowed_extensions):
    _, ext = os.path.splitext(filename.lower())
    return ext in allowed_extensions


def _write_cut_plan(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def _write_keep_csv(path, segments):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["start_sec", "end_sec", "duration_sec"])
        for start, end in segments:
            writer.writerow([f"{start:.3f}", f"{end:.3f}", f"{(end - start):.3f}"])


def _process_job(video_path, transcript_path, outdir, min_gap, context, batch_size):
    captions = parse_transcript(transcript_path)
    candidates = detect_gaps(captions, min_gap=min_gap, context=context)

    decisions = []
    if candidates:
        client = GeminiClient()
        decisions = decide_gaps(candidates, client, batch_size=batch_size, max_retries=2)

    decisions_by_id = {item["id"]: item for item in decisions}
    for cand in candidates:
        decision = decisions_by_id.get(cand["id"], {"decision": "KEEP", "reason": ""})
        cand["decision"] = decision["decision"]
        cand["reason"] = decision.get("reason", "")

    keep_segments, total_duration = compute_keep_segments(captions, candidates, decisions)
    estimated_duration = sum(end - start for start, end in keep_segments)

    cut_plan = {
        "video": video_path,
        "transcript": transcript_path,
        "min_gap": min_gap,
        "context": context,
        "total_duration_sec": round(total_duration, 3),
        "estimated_edited_duration_sec": round(estimated_duration, 3),
        "candidates": candidates,
        "keep_segments": [
            {
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "duration_sec": round(end - start, 3),
            }
            for start, end in keep_segments
        ],
    }

    cut_plan_path = os.path.join(outdir, "cut_plan.json")
    keep_csv_path = os.path.join(outdir, "keep_segments.csv")
    _write_cut_plan(cut_plan_path, cut_plan)
    _write_keep_csv(keep_csv_path, keep_segments)

    edited_path = os.path.join(outdir, "edited.mp4")
    render_error = None
    if keep_segments:
        try:
            render_video(video_path, keep_segments, edited_path)
        except Exception as exc:
            render_error = str(exc)

    summary = {
        "gaps_found": len(candidates),
        "cut_count": sum(1 for c in candidates if c.get("decision") == "CUT"),
        "keep_count": sum(1 for c in candidates if c.get("decision") == "KEEP"),
        "total_duration_sec": round(total_duration, 2),
        "estimated_duration_sec": round(estimated_duration, 2),
        "render_error": render_error,
        "edited_exists": os.path.isfile(edited_path),
    }

    return summary


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    if "video" not in request.files or "transcript" not in request.files:
        return render_template(
            "index.html", error="Please upload both a video file and a transcript."
        )

    video = request.files["video"]
    transcript = request.files["transcript"]

    if not video.filename or not transcript.filename:
        return render_template(
            "index.html", error="Please select both files before submitting."
        )

    if not _is_allowed(video.filename, ALLOWED_VIDEO_EXTENSIONS):
        return render_template(
            "index.html", error="Unsupported video type. Use MP4/MOV/M4V."
        )

    if not _is_allowed(transcript.filename, ALLOWED_TRANSCRIPT_EXTENSIONS):
        return render_template(
            "index.html", error="Unsupported transcript type. Use SRT/VTT/TXT."
        )

    try:
        min_gap = float(request.form.get("min_gap", "0.8"))
        context = int(request.form.get("context", "2"))
        batch_size = int(request.form.get("batch_size", "10"))
    except ValueError:
        return render_template("index.html", error="Settings must be valid numbers.")

    job_id = uuid.uuid4().hex[:10]
    job_dir = os.path.join(BASE_OUTPUT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    safe_video = secure_filename(video.filename)
    safe_transcript = secure_filename(transcript.filename)
    video_path = os.path.join(job_dir, safe_video)
    transcript_path = os.path.join(job_dir, safe_transcript)

    video.save(video_path)
    transcript.save(transcript_path)

    try:
        summary = _process_job(
            video_path, transcript_path, job_dir, min_gap, context, batch_size
        )
    except Exception as exc:
        return render_template("index.html", error=str(exc))

    return render_template(
        "result.html",
        job_id=job_id,
        video_name=safe_video,
        transcript_name=safe_transcript,
        summary=summary,
    )


@app.route("/outputs/<job_id>/<filename>")
def outputs(job_id, filename):
    job_dir = os.path.join(BASE_OUTPUT_DIR, job_id)
    return send_from_directory(job_dir, filename)


if __name__ == "__main__":
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    app.run(host="127.0.0.1", port=5000, debug=False)
