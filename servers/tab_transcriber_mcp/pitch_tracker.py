"""Audio-to-MIDI pitch tracker and drum onset/component detector."""

import os
from typing import List, Dict, Any, Optional
import numpy as np
import librosa
from scipy.signal import butter, sosfilt


def bandpass_filter(data: np.ndarray, sr: int, low_cut: float, high_cut: float) -> np.ndarray:
    """Apply a Butterworth bandpass filter to extract instrument frequency bands."""
    nyquist = 0.5 * sr
    low = max(10.0, low_cut) / nyquist
    high = min(nyquist - 10.0, high_cut) / nyquist
    if low >= high:
        return data
    sos = butter(4, [low, high], btype="bandpass", output="sos")
    return sosfilt(sos, data)


def detect_drum_hits(y: np.ndarray, sr: int) -> List[Dict[str, Any]]:
    """Detect drum components (Kick, Snare, Hi-Hat/Crash/China) across frequency sub-bands."""
    # 1. Bandpass filter for drum components
    kick_signal = bandpass_filter(y, sr, 30.0, 120.0)
    snare_signal = bandpass_filter(y, sr, 150.0, 400.0)
    cymbal_signal = bandpass_filter(y, sr, 5000.0, 16000.0)

    # 2. Onset envelope for each sub-band
    kick_env = librosa.onset.onset_strength(y=kick_signal, sr=sr)
    snare_env = librosa.onset.onset_strength(y=snare_signal, sr=sr)
    cymbal_env = librosa.onset.onset_strength(y=cymbal_signal, sr=sr)

    # Global onsets
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    drum_events = []
    hop_length = 512
    max_frames = min(len(kick_env), len(snare_env), len(cymbal_env))

    for i, t in enumerate(onset_times):
        frame = int(librosa.time_to_frames(t, sr=sr, hop_length=hop_length))
        if frame >= max_frames:
            break

        components = []
        midi_notes = []

        k_val = kick_env[frame]
        s_val = snare_env[frame]
        c_val = cymbal_env[frame]

        # Component thresholds
        if k_val > 0.3 * np.max(kick_env) if np.max(kick_env) > 0 else 0:
            components.append("kick")
            midi_notes.append(36)
        if s_val > 0.3 * np.max(snare_env) if np.max(snare_env) > 0 else 0:
            components.append("snare")
            midi_notes.append(38)
        if c_val > 0.3 * np.max(cymbal_env) if np.max(cymbal_env) > 0 else 0:
            # Distinguish heavy china/crash vs hihat based on energy
            if c_val > 0.7 * np.max(cymbal_env):
                components.append("china_cymbal")
                midi_notes.append(52)
            else:
                components.append("hi_hat")
                midi_notes.append(42)

        if not components:
            components.append("snare")
            midi_notes.append(38)

        end_t = onset_times[i + 1] if i + 1 < len(onset_times) else t + 0.25
        duration = float(end_t - t)

        drum_events.append({
            "start_time_sec": float(t),
            "end_time_sec": float(end_t),
            "duration_sec": round(duration, 3),
            "components": components,
            "midi_notes": midi_notes,
            "energy": float(max(k_val, s_val, c_val)),
        })

    return drum_events


def track_tonal_pitches(y: np.ndarray, sr: int, instrument: str = "guitar") -> List[Dict[str, Any]]:
    """Track pitches, durations, and chords for guitar, bass, or synth."""
    # Harmonic component isolation
    y_harm = librosa.effects.harmonic(y)

    # Detect onsets
    onset_frames = librosa.onset.onset_detect(y=y_harm, sr=sr, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    if len(onset_times) == 0:
        # Fallback to uniform grid
        onset_times = np.arange(0, len(y) / sr, 0.5)

    fmin = librosa.note_to_hz("C1") if instrument == "bass" else librosa.note_to_hz("C2")
    fmax = librosa.note_to_hz("C5") if instrument == "bass" else librosa.note_to_hz("E7")

    # Estimate pitch via pyin or chromagram
    try:
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y_harm,
            fmin=fmin,
            fmax=fmax,
            sr=sr,
            fill_na=None,
        )
        pyin_times = librosa.times_like(f0, sr=sr)
    except Exception:
        f0 = None
        pyin_times = None

    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr)
    chroma_times = librosa.times_like(chroma, sr=sr)

    events = []
    hop_length = 512

    for i, t_start in enumerate(onset_times):
        t_end = onset_times[i + 1] if i + 1 < len(onset_times) else float(len(y) / sr)
        duration = max(0.08, float(t_end - t_start))

        # Sample RMS energy in segment
        start_samp = int(t_start * sr)
        end_samp = min(len(y), int(t_end * sr))
        segment = y[start_samp:end_samp]
        rms = float(np.sqrt(np.mean(segment**2))) if len(segment) > 0 else 0.0
        db = float(librosa.amplitude_to_db(np.array([rms]), ref=1.0)[0])

        # Find fundamental pitch from pyin
        midi_pitch = None
        if f0 is not None and pyin_times is not None:
            mask = (pyin_times >= t_start) & (pyin_times < t_end)
            segment_f0 = f0[mask]
            valid_f0 = segment_f0[~np.isnan(segment_f0)] if segment_f0 is not None else []
            if len(valid_f0) > 0:
                median_hz = float(np.median(valid_f0))
                midi_pitch = int(round(librosa.hz_to_midi(median_hz)))

        # Fallback to chromagram peak + instrument register
        if midi_pitch is None or midi_pitch < 20 or midi_pitch > 100:
            frame_idx = min(len(chroma_times) - 1, int(librosa.time_to_frames(t_start, sr=sr, hop_length=hop_length)))
            pitch_class = int(np.argmax(chroma[:, frame_idx]))
            base_octave = 2 if instrument == "bass" else (3 if instrument == "guitar" else 4)
            midi_pitch = (base_octave + 1) * 12 + pitch_class

        # Check for polyphonic chord (power chord / triad)
        frame_idx = min(len(chroma_times) - 1, int(librosa.time_to_frames(t_start, sr=sr, hop_length=hop_length)))
        chroma_slice = chroma[:, frame_idx]
        top_classes = np.where(chroma_slice > 0.65 * np.max(chroma_slice))[0]

        chord_midi = [midi_pitch]
        root_class = midi_pitch % 12
        # Check power chord: Fifth (root + 7) and Octave (root + 12)
        has_fifth = (root_class + 7) % 12 in top_classes
        has_fourth = (root_class + 5) % 12 in top_classes

        if has_fifth:
            chord_midi.append(midi_pitch + 7)
            chord_midi.append(midi_pitch + 12)
        elif has_fourth:
            chord_midi.append(midi_pitch + 5)

        events.append({
            "start_time_sec": round(float(t_start), 3),
            "end_time_sec": round(float(t_end), 3),
            "duration_sec": round(duration, 3),
            "root_midi": midi_pitch,
            "midi_notes": sorted(list(set(chord_midi))),
            "rms": round(rms, 4),
            "db": round(db, 1),
        })

    return events


def analyze_stem_pitches(stem_path: str, instrument: str) -> List[Dict[str, Any]]:
    """Load stem audio file and extract pitch/drum events."""
    if not os.path.exists(stem_path):
        return []
    # Optimize to 22050 Hz for ultra-fast, robust pitch tracking without loss of fundamental notes
    y, sr = librosa.load(stem_path, sr=22050, mono=True)
    if "drum" in instrument.lower():
        return detect_drum_hits(y, sr)
    else:
        return track_tonal_pitches(y, sr, instrument=instrument.lower())
