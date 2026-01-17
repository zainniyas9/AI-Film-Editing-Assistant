# AI Silence Cutter

Simple CLI tool that detects transcript gaps, asks Gemini whether to CUT or KEEP them, then produces a cut plan (JSON + CSV) and optionally renders an edited video with ffmpeg.

## Setup

1) Install dependencies:

```bash
pip install -r requirements.txt
```

2) Add your Gemini API key:

- Option A: set environment variable `GEMINI_API_KEY`
- Option B: edit `api_key.py` and paste your key

3) Run the CLI:

```bash
python main.py --video input.mp4 --transcript transcript.srt --outdir outputs --min-gap 0.8 --context 2
```

## Optional web UI

1) Install dependencies (includes Flask):

```bash
pip install -r requirements.txt
```

2) Start the web app:

```bash
python web_app.py
```

3) Open `http://127.0.0.1:5000` and upload a video + transcript.

## Outputs

- `outputs/cut_plan.json` full details and decisions
- `outputs/keep_segments.csv` keep segments list
- `outputs/edited.mp4` (if ffmpeg is available and rendering is enabled)

## Notes

- Supported transcripts: SRT, VTT, or simple `start end text` lines.
- Gemini model: `gemini-3-flash-preview` via `google-genai`.
- ffmpeg is optional but recommended for rendering.
