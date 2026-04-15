from pathlib import Path


def _read_version() -> str:
    version_file = Path(__file__).with_name("VERSION")
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except Exception:
        return "0.0.0"


APP_VERSION = _read_version()
