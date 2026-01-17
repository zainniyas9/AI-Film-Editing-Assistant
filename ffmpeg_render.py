import shutil
import subprocess


def _has_audio(input_path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        input_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return bool(result.stdout.strip())


def render_video(input_path, segments, output_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH.")
    if not segments:
        raise ValueError("No segments to render.")

    has_audio = _has_audio(input_path)
    filter_parts = []
    concat_inputs = []

    for idx, (start, end) in enumerate(segments):
        v_label = f"v{idx}"
        filter_parts.append(
            f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[{v_label}]"
        )
        concat_inputs.append(f"[{v_label}]")
        if has_audio:
            a_label = f"a{idx}"
            filter_parts.append(
                f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[{a_label}]"
            )
            concat_inputs.append(f"[{a_label}]")

    if has_audio:
        concat_filter = (
            "".join(concat_inputs)
            + f"concat=n={len(segments)}:v=1:a=1[v][a]"
        )
        filter_parts.append(concat_filter)
        command = [
            ffmpeg,
            "-y",
            "-i",
            input_path,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-movflags",
            "+faststart",
            output_path,
        ]
    else:
        concat_filter = (
            "".join(concat_inputs)
            + f"concat=n={len(segments)}:v=1:a=0[v]"
        )
        filter_parts.append(concat_filter)
        command = [
            ffmpeg,
            "-y",
            "-i",
            input_path,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[v]",
            "-movflags",
            "+faststart",
            output_path,
        ]

    subprocess.run(command, check=True)
