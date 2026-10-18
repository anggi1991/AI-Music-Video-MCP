"""Beat-accurate video cutter, optical flow visual BPM estimator, and speed-ramper.

Supports Rock/Metal band, Multi-Guitar, Bowed Strings, Orchestral instruments, and Multi-Vocalists.
"""

import os
import re
from typing import List, Dict, Any, Optional
import cv2
import numpy as np


def estimate_video_motion_bpm(video_path: str, default_bpm: float = 120.0) -> Dict[str, Any]:
    """Inspect video properties (duration, fps, resolution) and estimate native motion BPM using optical flow."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "duration_sec": 4.0,
            "fps": 30.0,
            "width": 1920,
            "height": 1080,
            "estimated_bpm": default_bpm,
            "motion_energy": 0.0,
        }

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_sec = total_frames / fps if fps > 0 else 4.0

    max_samples = min(60, total_frames)
    step = max(1, total_frames // max_samples) if max_samples > 0 else 1

    prev_gray = None
    motion_energies = []

    for f_idx in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        small = cv2.resize(frame, (160, 90))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 0.5, 2, 10, 2, 5, 1.1, 0
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            energy = float(np.mean(mag))
            motion_energies.append(energy)

        prev_gray = gray
        if len(motion_energies) >= 30:
            break

    cap.release()

    mean_motion = float(np.mean(motion_energies)) if motion_energies else 1.0

    estimated_bpm = default_bpm
    if len(motion_energies) >= 10:
        energies_norm = np.array(motion_energies) - np.mean(motion_energies)
        autocorr = np.correlate(energies_norm, energies_norm, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]
        if len(autocorr) > 4:
            peak_lag = int(np.argmax(autocorr[2:15])) + 2
            est_period_sec = (peak_lag * step) / fps
            if 0.25 <= est_period_sec <= 1.5:
                estimated_bpm = round(60.0 / est_period_sec, 1)

    estimated_bpm = float(np.clip(estimated_bpm, 70.0, 200.0))

    return {
        "duration_sec": round(duration_sec, 3),
        "fps": round(fps, 2),
        "width": width,
        "height": height,
        "estimated_bpm": estimated_bpm,
        "motion_energy": round(mean_motion, 3),
    }


def classify_footage_file(filename: str) -> Dict[str, str]:
    """Parse filename tags to classify instrument and playing state."""
    name = filename.lower()
    instrument = "broll"
    playing_state = "idle"

    # 1. Vocals
    if "vocal_lead" in name or "lead_singer" in name or "lead_vocal" in name:
        instrument = "vocal_lead"
        if "scream" in name or "growl" in name:
            playing_state = "vocal_aggressive_scream"
        elif "rap" in name:
            playing_state = "vocal_rap_flow"
        elif "whisper" in name:
            playing_state = "vocal_spoken_whisper"
        else:
            playing_state = "vocal_clean_melodic"

    elif "vocal_co_lead" in name or "co_lead" in name or "screamer" in name or "second_singer" in name:
        instrument = "vocal_co_lead"
        if "clean" in name:
            playing_state = "vocal_clean_melodic"
        else:
            playing_state = "vocal_aggressive_scream"

    elif "vocal_backing" in name or "backing_vocal" in name or "harmony_vocal" in name:
        instrument = "vocal_backing"
        if "shout" in name or "gang" in name:
            playing_state = "vocal_gang_shout"
        else:
            playing_state = "vocal_backing_harmony"

    elif "vocal" in name or "singer" in name:
        instrument = "vocals"
        playing_state = "vocal_clean_melodic"

    # 2. Guitars
    elif "guitar" in name:
        if "rhythm" in name:
            instrument = "guitar_rhythm"
            playing_state = "palm_mute_chug"
        elif "lead" in name or "solo" in name or "melody" in name:
            instrument = "guitar_lead"
            playing_state = "lead_melody"
        elif "additional" in name or "ambient" in name or "clean" in name or "shimmer" in name:
            instrument = "guitar_additional"
            playing_state = "sustained_pad"
        elif "chug" in name or "mute" in name:
            instrument = "guitar"
            playing_state = "palm_mute_chug"
        elif "power" in name or "chord" in name:
            instrument = "guitar"
            playing_state = "wide_power_chord"
        elif "arpeggio" in name:
            instrument = "guitar"
            playing_state = "arpeggio_fast"
        else:
            instrument = "guitar"
            playing_state = "palm_mute_chug"

    # 3. Bowed Strings & Orchestra
    elif "violin" in name:
        instrument = "violin"
        playing_state = "bowed_tremolo" if "tremolo" in name else "bowed_legato"

    elif "viola" in name:
        instrument = "viola"
        playing_state = "bowed_legato"

    elif "cello" in name:
        instrument = "cello"
        playing_state = "spiccato_fast" if "spiccato" in name else "bowed_legato"

    elif "contrabass" in name or "upright_bass" in name:
        instrument = "contrabass"
        playing_state = "bowed_legato"

    elif "strings" in name:
        instrument = "strings_ensemble"
        playing_state = "bowed_legato"

    elif "brass" in name or "trumpet" in name or "horn" in name or "trombone" in name:
        instrument = "brass"
        playing_state = "brass_swell_blare"

    elif "woodwind" in name or "flute" in name or "sax" in name:
        instrument = "woodwinds"
        playing_state = "woodwind_expressive_solo"

    elif "choir" in name:
        instrument = "choir"
        playing_state = "choir_epic_chant"

    elif "orchestra" in name:
        instrument = "strings_ensemble"
        playing_state = "bowed_legato"

    # 4. Drums & Bass & Keys
    elif "drum" in name:
        instrument = "drums"
        if "breakdown" in name or "cymbal" in name or "china" in name:
            playing_state = "heavy_breakdown_cymbal"
        elif "blast" in name:
            playing_state = "blast_beat"
        else:
            playing_state = "heavy_breakdown_cymbal"

    elif "bass" in name:
        instrument = "bass"
        playing_state = "palm_mute_chug"

    elif "synth" in name or "key" in name or "piano" in name:
        instrument = "keyboard"
        playing_state = "sustained_pad"

    elif "broll" in name or "scene" in name or "stage" in name:
        instrument = "broll"
        playing_state = "idle"

    return {
        "instrument": instrument,
        "playing_state": playing_state,
    }


def list_and_classify_footage(footage_dir: str) -> Dict[str, Any]:
    """Scan a folder of Google Veo clips, read metadata, and map them to InstrumentEvents."""
    if not os.path.exists(footage_dir):
        return {
            "footage_dir": footage_dir,
            "total_clips": 0,
            "clips": [],
            "classified_by_instrument": {},
        }

    valid_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
    clips = []
    by_inst = {
        "guitar": [],
        "guitar_rhythm": [],
        "guitar_lead": [],
        "guitar_additional": [],
        "vocal_lead": [],
        "vocal_co_lead": [],
        "vocal_backing": [],
        "vocals": [],
        "violin": [],
        "cello": [],
        "strings_ensemble": [],
        "brass": [],
        "woodwinds": [],
        "choir": [],
        "bass": [],
        "drums": [],
        "keyboard": [],
        "broll": [],
    }

    for fname in sorted(os.listdir(footage_dir)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in valid_exts:
            continue

        full_path = os.path.abspath(os.path.join(footage_dir, fname))
        class_info = classify_footage_file(fname)
        motion_info = estimate_video_motion_bpm(full_path)

        inst_type = class_info["instrument"]
        clip_data = {
            "filename": fname,
            "filepath": full_path,
            "instrument": inst_type,
            "playing_state": class_info["playing_state"],
            "duration_sec": motion_info["duration_sec"],
            "fps": motion_info["fps"],
            "resolution": f"{motion_info['width']}x{motion_info['height']}",
            "native_bpm": motion_info["estimated_bpm"],
            "motion_energy": motion_info["motion_energy"],
        }
        clips.append(clip_data)

        # File under specific instrument
        by_inst.setdefault(inst_type, []).append(clip_data)

        # Aliasing for guitars
        if inst_type in ("guitar_rhythm", "guitar_lead", "guitar_additional"):
            by_inst.setdefault("guitar", []).append(clip_data)
        elif inst_type == "guitar":
            by_inst.setdefault("guitar_rhythm", []).append(clip_data)

        # Aliasing for vocals
        if inst_type in ("vocal_lead", "vocal_co_lead", "vocal_backing"):
            by_inst.setdefault("vocals", []).append(clip_data)
        elif inst_type == "vocals":
            by_inst.setdefault("vocal_lead", []).append(clip_data)

        # Aliasing for orchestral
        if inst_type in ("violin", "viola", "cello", "contrabass", "strings_ensemble", "brass", "woodwinds", "choir"):
            by_inst.setdefault("orchestra", []).append(clip_data)
            by_inst.setdefault("strings_ensemble", []).append(clip_data)

    return {
        "footage_dir": footage_dir,
        "total_clips": len(clips),
        "clips": clips,
        "classified_by_instrument": by_inst,
    }


def calculate_speed_multiplier(song_bpm: float, clip_native_bpm: float) -> float:
    """Calculate micro speed-ramping multiplier: clip(Song BPM / Clip Native BPM, 0.75, 1.50)."""
    if clip_native_bpm <= 0:
        return 1.0
    ratio = float(song_bpm / clip_native_bpm)
    return float(np.clip(ratio, 0.75, 1.50))
