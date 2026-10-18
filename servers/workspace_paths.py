"""Path validation for the workspace source and generated audio boundaries."""

import os
import re

SOURCE_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac"}


def resolve_source_song(project_root: str, audio_path: str) -> str:
    source_root = os.path.realpath(os.path.join(project_root, "workspace", "source_songs"))
    resolved = os.path.realpath(audio_path)
    try:
        inside_source = os.path.commonpath([source_root, resolved]) == source_root
    except ValueError:
        inside_source = False
    if not inside_source or not os.path.isfile(resolved) or os.path.splitext(resolved)[1].lower() not in SOURCE_AUDIO_EXTENSIONS:
        raise ValueError("Audio input must be a .wav, .mp3, or .flac file inside workspace/source_songs/.")
    return resolved


def project_stems_dir(project_root: str, project_name: str, fallback_stem: str = "untitled") -> str:
    raw_name = str(project_name or fallback_stem)
    safe_name = re.sub(r"[^\w-]+", "_", raw_name, flags=re.UNICODE).strip("_-") or fallback_stem
    return os.path.join(project_root, "workspace", "input_stems", safe_name)
