"""Module for audio analysis, BPM warping, key detection, and crossfaded stem splicing."""

import os
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import soundfile as sf
import librosa
import pyloudnorm as pyln

# Krumhansl-Schmuckler key profiles for key-finding
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def detect_key_krumhansl(y: np.ndarray, sr: int) -> Tuple[str, str, int]:
    """Detect musical key (Root + Mode) using Krumhansl-Schmuckler profile correlation."""
    # Compute chromagram
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_vector = np.sum(chroma, axis=1)
    norm = np.linalg.norm(chroma_vector)
    if norm > 0:
        chroma_vector = chroma_vector / norm
    else:
        return "C", "Major", 0

    best_score = -float("inf")
    best_key = "C"
    best_mode = "Major"
    best_root_idx = 0

    for i in range(12):
        # Rotate major and minor profiles
        rot_major = np.roll(MAJOR_PROFILE, i)
        rot_minor = np.roll(MINOR_PROFILE, i)

        corr_major = np.corrcoef(chroma_vector, rot_major)[0, 1]
        corr_minor = np.corrcoef(chroma_vector, rot_minor)[0, 1]

        if not np.isnan(corr_major) and corr_major > best_score:
            best_score = corr_major
            best_key = NOTE_NAMES[i]
            best_mode = "Major"
            best_root_idx = i

        if not np.isnan(corr_minor) and corr_minor > best_score:
            best_score = corr_minor
            best_key = NOTE_NAMES[i]
            best_mode = "Minor"
            best_root_idx = i

    return best_key, best_mode, best_root_idx


def calculate_pitch_shift(base_root_idx: int, donor_root_idx: int) -> int:
    """Calculate the shortest pitch shift in semitones (between -6 and +6) to match roots."""
    diff = (base_root_idx - donor_root_idx) % 12
    if diff > 6:
        diff -= 12
    return int(diff)


def analyze_audio_metadata(
    audio_path: str,
    drum_stem_path: Optional[str] = None,
    harmonic_stem_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Detect exact BPM, Musical Key, duration, integrated LUFS, and transient onset timestamps.
    Supports drum stem transient priority for BPM and cleaned harmonic stems for musical key.

    Args:
        audio_path: Path to the audio file.
        drum_stem_path: Optional path to isolated drum stem for transient BPM tracking.
        harmonic_stem_paths: Optional paths to cleaned harmonic stems for musical key detection.

    Returns:
        dict: Audio metadata including BPM, key, duration, LUFS, and onsets.
    """
    if isinstance(audio_path, str):
        audio_path = audio_path.strip().strip('"').strip("'")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load audio
    y, sr = librosa.load(audio_path, sr=None, mono=False)
    if y.ndim > 1:
        y_mono = librosa.to_mono(y)
    else:
        y_mono = y

    duration_sec = float(len(y_mono) / sr)

    # 1. BPM and beat tracking (Prioritize clean drum transient envelope if available)
    if drum_stem_path and os.path.exists(drum_stem_path):
        try:
            y_d, sr_d = librosa.load(drum_stem_path, sr=None, mono=True)
            d_tempo, _ = librosa.beat.beat_track(y=y_d, sr=sr_d)
            if isinstance(d_tempo, np.ndarray):
                bpm = float(d_tempo[0]) if d_tempo.size > 0 else 120.0
            else:
                bpm = float(d_tempo)
        except Exception:
            tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
            bpm = float(tempo[0]) if isinstance(tempo, np.ndarray) and tempo.size > 0 else float(tempo)
    else:
        tempo, beats = librosa.beat.beat_track(y=y_mono, sr=sr)
        if isinstance(tempo, np.ndarray):
            bpm = float(tempo[0]) if tempo.size > 0 else 120.0
        else:
            bpm = float(tempo)

    # 2. Key detection (Prioritize cleaned harmonic stems: bass, guitar, piano)
    if harmonic_stem_paths:
        try:
            harm_signals = []
            for hp in harmonic_stem_paths:
                if hp and os.path.exists(hp):
                    yh, _ = librosa.load(hp, sr=sr, mono=True)
                    harm_signals.append(yh)
            if harm_signals:
                min_len = min(len(s) for s in harm_signals)
                sum_harm = np.sum([s[:min_len] for s in harm_signals], axis=0)
                root_note, mode, root_idx = detect_key_krumhansl(sum_harm, sr)
                musical_key = f"{root_note} {mode}"
            else:
                root_note, mode, root_idx = detect_key_krumhansl(y_mono, sr)
                musical_key = f"{root_note} {mode}"
        except Exception:
            root_note, mode, root_idx = detect_key_krumhansl(y_mono, sr)
            musical_key = f"{root_note} {mode}"
    else:
        root_note, mode, root_idx = detect_key_krumhansl(y_mono, sr)
        musical_key = f"{root_note} {mode}"

    # 3. Integrated LUFS
    try:
        meter = pyln.Meter(sr)
        # Meter expects (samples, channels)
        if y.ndim > 1:
            audio_for_lufs = y.T
        else:
            audio_for_lufs = y_mono[:, np.newaxis]
        loudness_lufs = float(meter.integrated_loudness(audio_for_lufs))
        if np.isneginf(loudness_lufs) or np.isnan(loudness_lufs):
            loudness_lufs = -70.0
    except Exception:
        loudness_lufs = -24.0

    # 4. Transient Onsets
    onset_frames = librosa.onset.onset_detect(y=y_mono, sr=sr, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()

    return {
        "audio_path": audio_path,
        "bpm": round(bpm, 2),
        "root_note": root_note,
        "mode": mode,
        "root_idx": root_idx,
        "musical_key": musical_key,
        "duration_sec": round(duration_sec, 3),
        "integrated_lufs": round(loudness_lufs, 2),
        "onset_count": len(onset_times),
        "onset_timestamps_sec": [round(t, 4) for t in onset_times[:100]],  # First 100 onsets
    }


def apply_cosine_crossfade(
    base_segment: np.ndarray,
    donor_segment: np.ndarray,
    fade_len: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply equal-power cosine crossfade curves between base and donor slices."""
    if fade_len <= 0:
        return base_segment, donor_segment

    t = np.linspace(0, np.pi / 2, fade_len)
    fade_in = np.sin(t)
    fade_out = np.cos(t)

    # If stereo/multichannel, match dims
    if donor_segment.ndim > 1:
        fade_in = fade_in[np.newaxis, :]
        fade_out = fade_out[np.newaxis, :]

    # In-place or copy fade on borders
    donor_mod = donor_segment.copy()
    donor_mod[..., :fade_len] *= fade_in
    donor_mod[..., -fade_len:] *= fade_out

    return base_segment, donor_mod


def mashup_replace_segment(
    base_stem_path: str,
    donor_stem_path: str,
    base_replace_start: float,
    base_replace_end: float,
    donor_extract_start: float,
    donor_extract_end: float,
    output_path: str,
) -> Dict[str, Any]:
    """Replace a segment in base stem with a time-stretched and pitch-shifted segment from donor stem.

    Uses 15ms cosine crossfade at splice boundaries to prevent clicks.
    """
    if isinstance(base_stem_path, str):
        base_stem_path = base_stem_path.strip().strip('"').strip("'")
    if isinstance(donor_stem_path, str):
        donor_stem_path = donor_stem_path.strip().strip('"').strip("'")
    if isinstance(output_path, str):
        output_path = output_path.strip().strip('"').strip("'")

    if not os.path.exists(base_stem_path):
        raise FileNotFoundError(f"Base stem not found: {base_stem_path}")
    if not os.path.exists(donor_stem_path):
        raise FileNotFoundError(f"Donor stem not found: {donor_stem_path}")

    # Analyze metadata of both stems
    base_meta = analyze_audio_metadata(base_stem_path)
    donor_meta = analyze_audio_metadata(donor_stem_path)

    base_bpm = base_meta["bpm"]
    donor_bpm = donor_meta["bpm"]

    # Calculate stretch ratio and pitch shift
    # ratio = base_bpm / donor_bpm
    stretch_ratio = float(base_bpm / donor_bpm) if donor_bpm > 0 else 1.0
    pitch_semitones = calculate_pitch_shift(base_meta["root_idx"], donor_meta["root_idx"])

    # Load audio data
    y_base, sr = librosa.load(base_stem_path, sr=None, mono=False)
    y_donor, _ = librosa.load(donor_stem_path, sr=sr, mono=False)

    # Slice donor segment
    d_start_idx = max(0, int(donor_extract_start * sr))
    d_end_idx = min(y_donor.shape[-1], int(donor_extract_end * sr))
    donor_slice = y_donor[..., d_start_idx:d_end_idx]

    if donor_slice.shape[-1] == 0:
        raise ValueError("Donor slice duration is 0 samples.")

    # Time-stretch and Pitch-shift donor slice
    # librosa.effects.time_stretch expects 1D or 2D (channels, samples)
    if stretch_ratio != 1.0:
        # Note: librosa.effects.time_stretch rate argument: rate > 1 speeds up, rate < 1 slows down
        # If base is 140 and donor is 120, ratio=1.1667 (needs to speed up by 1.1667)
        donor_processed = librosa.effects.time_stretch(donor_slice, rate=stretch_ratio)
    else:
        donor_processed = donor_slice

    if pitch_semitones != 0:
        donor_processed = librosa.effects.pitch_shift(donor_processed, sr=sr, n_steps=pitch_semitones)

    # Target duration in base stem
    target_samples = int((base_replace_end - base_replace_start) * sr)
    b_start_idx = max(0, int(base_replace_start * sr))
    b_end_idx = b_start_idx + target_samples

    # Align donor_processed duration to target_samples
    curr_len = donor_processed.shape[-1]
    if curr_len < target_samples:
        pad_width = [(0, 0)] * (donor_processed.ndim - 1) + [(0, target_samples - curr_len)]
        donor_processed = np.pad(donor_processed, pad_width, mode="constant")
    elif curr_len > target_samples:
        donor_processed = donor_processed[..., :target_samples]

    # 15ms cosine crossfade at splice boundaries
    crossfade_samples = min(int(0.015 * sr), target_samples // 4)
    if crossfade_samples > 0:
        t = np.linspace(0, np.pi / 2, crossfade_samples)
        fade_in = np.sin(t)
        fade_out = np.cos(t)

        if donor_processed.ndim > 1:
            fade_in = fade_in[np.newaxis, :]
            fade_out = fade_out[np.newaxis, :]

        # Blend boundaries with base audio if available
        # Left boundary
        if b_start_idx > 0 and b_start_idx + crossfade_samples <= y_base.shape[-1]:
            donor_processed[..., :crossfade_samples] = (
                donor_processed[..., :crossfade_samples] * fade_in
                + y_base[..., b_start_idx : b_start_idx + crossfade_samples] * fade_out
            )
        # Right boundary
        right_end = b_end_idx
        if right_end < y_base.shape[-1]:
            donor_processed[..., -crossfade_samples:] = (
                donor_processed[..., -crossfade_samples:] * fade_out
                + y_base[..., right_end - crossfade_samples : right_end] * fade_in
            )

    # Assemble output audio
    output_len = max(y_base.shape[-1], b_end_idx)
    if y_base.ndim > 1:
        out_audio = np.zeros((y_base.shape[0], output_len), dtype=np.float32)
        out_audio[:, :y_base.shape[-1]] = y_base
        out_audio[:, b_start_idx:b_end_idx] = donor_processed
    else:
        out_audio = np.zeros(output_len, dtype=np.float32)
        out_audio[:y_base.shape[-1]] = y_base
        out_audio[b_start_idx:b_end_idx] = donor_processed

    # Export output
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if out_audio.ndim > 1:
        sf.write(output_path, out_audio.T, sr)
    else:
        sf.write(output_path, out_audio, sr)

    return {
        "status": "success",
        "output_path": output_path,
        "base_bpm": base_bpm,
        "donor_bpm": donor_bpm,
        "stretch_ratio": round(stretch_ratio, 4),
        "pitch_semitones": pitch_semitones,
        "base_key": base_meta["musical_key"],
        "donor_key": donor_meta["musical_key"],
        "crossfade_ms": round((crossfade_samples / sr) * 1000, 1),
        "replaced_range_sec": [base_replace_start, base_replace_end],
    }
