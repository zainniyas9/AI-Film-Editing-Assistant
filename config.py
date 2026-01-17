import os


def load_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key

    try:
        import api_key
    except Exception:
        api_key = None

    if api_key is not None:
        key = getattr(api_key, "GEMINI_API_KEY", "").strip()

    if not key or key == "paste_here":
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Set the GEMINI_API_KEY environment variable "
            "or edit api_key.py and paste your key."
        )

    return key
