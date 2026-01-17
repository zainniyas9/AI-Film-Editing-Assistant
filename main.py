import argparse
import csv
import json
import os
import sys

from cutter import compute_keep_segments
from decider import decide_gaps
from ffmpeg_render import render_video
from gap_detector import detect_gaps
from gemini_client import GeminiClient
from transcript_parser import parse_transcript


def write_cut_plan(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def write_keep_csv(path, segments):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["start_sec", "end_sec", "duration_sec"])
        for start, end in segments:
            writer.writerow([f"{start:.3f}", f"{end:.3f}", f"{(end - start):.3f}"])


def build_arg_parser():
    parser = argparse.ArgumentParser(description="AI-powered silence cutter")
    parser.add_argument("--video", required=True, help="Input MP4 video file")
    parser.add_argument("--transcript", required=True, help="Transcript file (SRT/VTT)")
    parser.add_argument("--outdir", default="outputs", help="Output directory")
    parser.add_argument("--min-gap", type=float, default=0.8, help="Min gap to consider")
    parser.add_argument("--context", type=int, default=2, help="Captions before/after")
    parser.add_argument("--batch-size", type=int, default=10, help="Gemini batch size")
    parser.add_argument(
        "--min-keep", type=float, default=0.25, help="Minimum keep segment length"
    )
    parser.add_argument(
        "--render",
        dest="render",
        action="store_true",
        help="Render edited video with ffmpeg (default)",
    )
    parser.add_argument(
        "--no-render",
        dest="render",
        action="store_false",
        help="Skip video rendering",
    )
    parser.set_defaults(render=True)
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"Video not found: {args.video}", file=sys.stderr)
        return 1
    if not os.path.isfile(args.transcript):
        print(f"Transcript not found: {args.transcript}", file=sys.stderr)
        return 1

    os.makedirs(args.outdir, exist_ok=True)

    captions = parse_transcript(args.transcript)
    candidates = detect_gaps(captions, min_gap=args.min_gap, context=args.context)

    decisions = []
    if candidates:
        client = GeminiClient()
        decisions = decide_gaps(
            candidates, client, batch_size=args.batch_size, max_retries=2
        )

    decisions_by_id = {item["id"]: item for item in decisions}
    for cand in candidates:
        decision = decisions_by_id.get(cand["id"], {"decision": "KEEP", "reason": ""})
        cand["decision"] = decision["decision"]
        cand["reason"] = decision.get("reason", "")

    keep_segments, total_duration = compute_keep_segments(
        captions, candidates, decisions, min_keep=args.min_keep
    )

    estimated_duration = sum(end - start for start, end in keep_segments)

    cut_plan = {
        "video": args.video,
        "transcript": args.transcript,
        "min_gap": args.min_gap,
        "context": args.context,
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

    cut_plan_path = os.path.join(args.outdir, "cut_plan.json")
    keep_csv_path = os.path.join(args.outdir, "keep_segments.csv")
    write_cut_plan(cut_plan_path, cut_plan)
    write_keep_csv(keep_csv_path, keep_segments)

    edited_path = os.path.join(args.outdir, "edited.mp4")
    rendered = False
    if args.render and keep_segments:
        try:
            render_video(args.video, keep_segments, edited_path)
            rendered = True
        except Exception as exc:
            print(f"Render skipped: {exc}", file=sys.stderr)

    num_cut = sum(1 for c in candidates if c.get("decision") == "CUT")
    num_keep = sum(1 for c in candidates if c.get("decision") == "KEEP")

    print(f"Gaps found: {len(candidates)}")
    print(f"Decisions: CUT={num_cut} KEEP={num_keep}")
    print(f"Original duration (from transcript): {total_duration:.2f}s")
    print(f"Estimated edited duration: {estimated_duration:.2f}s")
    if rendered:
        print(f"Edited video: {edited_path}")
    else:
        print("Edited video: not rendered")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
