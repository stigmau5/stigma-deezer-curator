import re


def safe_filename(name: str) -> str:
    name = name.strip()
    name = name.replace("&", "and")
    name = re.sub(r"[ \-/]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")
