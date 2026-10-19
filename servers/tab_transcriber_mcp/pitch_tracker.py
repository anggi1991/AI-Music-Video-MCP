"""Audio-to-MIDI pitch tracker and drum onset/component detector.

Uses high-resolution Constant-Q Transform (CQT) spectral peak tracking,
harmonic overtone pruning, and multi-band percussive transient separation
to authentically capture instrument pitches, chords, and drum grooves.
"""

import os
from typing import List, Dict, Any, Optional
import numpy as np
import librosa
try:
    from .pre_cleaner import pre_clean_stem_audio
except ImportError:
    try:
        from pre_cleaner import pre_clean_stem_audio
    except Exception:
        pre_clean_stem_audio = lambda y, sr, inst: y

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
    """Detect drum components (Kick, Snare, Hi-Hat/Crash/China/Toms) across frequency sub-bands.
    
    Produces simultaneous drum kit hits (e.g. Kick + Hi-Hat or Snare + Hi-Hat)
    with precise 16th-note transient alignment.
    """
    hop_length = 512
    # Sub-band signals
    kick_sig = bandpass_filter(y, sr, 35.0, 110.0)
    snare_sig = bandpass_filter(y, sr, 160.0, 420.0)
    snare_wire_sig = bandpass_filter(y, sr, 2500.0, 5000.0)
    cymb_sig = bandpass_filter(y, sr, 5500.0, 15000.0)
    tom_sig = bandpass_filter(y, sr, 110.0, 220.0)

    # Compute onset strength envelopes
    kick_env = librosa.onset.onset_strength(y=kick_sig, sr=sr, hop_length=hop_length)
    snare_env = librosa.onset.onset_strength(y=snare_sig, sr=sr, hop_length=hop_length) *                 (1.0 + librosa.onset.onset_strength(y=snare_wire_sig, sr=sr, hop_length=hop_length))
    cymb_env = librosa.onset.onset_strength(y=cymb_sig, sr=sr, hop_length=hop_length)
    tom_env = librosa.onset.onset_strength(y=tom_sig, sr=sr, hop_length=hop_length)

    # Global drum onsets from percussive energy
    _, y_perc = librosa.effects.hpss(y)
    onset_frames = librosa.onset.onset_detect(y=y_perc, sr=sr, hop_length=hop_length, backtrack=True)
    if len(onset_frames) == 0:
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop_length, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

    drum_events = []
    max_frames = min(len(kick_env), len(snare_env), len(cymb_env), len(tom_env))

    # Adaptive dynamic thresholds
    k_thresh = np.percentile(kick_env[kick_env > 0], 50) * 0.8 if np.any(kick_env > 0) else 0.1
    s_thresh = np.percentile(snare_env[snare_env > 0], 50) * 0.8 if np.any(snare_env > 0) else 0.1
    c_thresh = np.percentile(cymb_env[cymb_env > 0], 40) * 0.7 if np.any(cymb_env > 0) else 0.1
    t_thresh = np.percentile(tom_env[tom_env > 0], 65) * 0.9 if np.any(tom_env > 0) else 0.1

    for i, t in enumerate(onset_times):
        frame = int(librosa.time_to_frames(t, sr=sr, hop_length=hop_length))
        if frame >= max_frames:
            break

        components = []
        midi_notes = []

        k_val = kick_env[frame]
        s_val = snare_env[frame]
        c_val = cymb_env[frame]
        t_val = tom_env[frame]

        # 1. Kick Drum (MIDI 36)
        if k_val >= k_thresh and k_val > 0.05:
            components.append("kick")
            midi_notes.append(36)

        # 2. Snare Drum (MIDI 38)
        if s_val >= s_thresh and s_val > 0.05:
            components.append("snare")
            midi_notes.append(38)

        # 3. Cymbals & Hi-Hat
        if c_val >= c_thresh and c_val > 0.05:
            if c_val > 2.0 * c_thresh:
                components.append("china_cymbal")
                midi_notes.append(52)
            else:
                components.append("hi_hat")
                midi_notes.append(42)

        # 4. Tom (if no kick or snare)
        if not ("kick" in components or "snare" in components) and t_val >= t_thresh and t_val > 0.08:
            components.append("tom")
            midi_notes.append(45)

        # If nothing met threshold, assign strongest transient
        if not components:
            vals = [("kick", 36, k_val), ("snare", 38, s_val), ("hi_hat", 42, c_val)]
            best_comp, best_midi, _ = max(vals, key=lambda x: x[2])
            components.append(best_comp)
            midi_notes.append(best_midi)

        end_t = onset_times[i + 1] if i + 1 < len(onset_times) else t + 0.25
        duration = float(end_t - t)

        drum_events.append({
            "start_time_sec": round(float(t), 3),
            "end_time_sec": round(float(end_t), 3),
            "duration_sec": round(duration, 3),
            "components": components,
            "midi_notes": sorted(list(set(midi_notes))),
            "energy": float(max(k_val, s_val, c_val, t_val)),
        })

    return drum_events


def track_tonal_pitches(y: np.ndarray, sr: int, instrument: str = "guitar") -> List[Dict[str, Any]]:
    """Track authentic pitches, chords, and durations using CQT harmonic analysis."""
    y_harm, y_perc = librosa.effects.hpss(y)

    hop_length = 512
    onset_frames = librosa.onset.onset_detect(y=y_perc, sr=sr, hop_length=hop_length, backtrack=True)
    if len(onset_frames) == 0:
        onset_frames = librosa.onset.onset_detect(y=y_harm, sr=sr, hop_length=hop_length, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
    if len(onset_times) == 0:
        onset_times = np.arange(0, len(y) / sr, 0.5)

    inst_lower = instrument.lower()
    if "bass" in inst_lower:
        fmin = librosa.note_to_hz("C1")   # MIDI 24 (32.7 Hz)
        base_midi = 24
        n_bins = 48                      # 4 octaves up to C5 (MIDI 72)
        max_polyphony = 2
    elif any(k in inst_lower for k in ["guitar", "string", "violin", "cello"]):
        fmin = librosa.note_to_hz("E2")   # MIDI 40 (82.4 Hz)
        base_midi = 40
        n_bins = 60                      # 5 octaves up to E7 (MIDI 100)
        max_polyphony = 6
    elif "vocal" in inst_lower:
        fmin = librosa.note_to_hz("C2")   # MIDI 36 (65.4 Hz)
        base_midi = 36
        n_bins = 60                      # 5 octaves
        max_polyphony = 2
    else:  # piano, synth, keyboard, orchestra
        fmin = librosa.note_to_hz("C1")   # MIDI 24
        base_midi = 24
        n_bins = 72                      # 6 octaves
        max_polyphony = 6

    cqt = np.abs(librosa.cqt(
        y_harm,
        sr=sr,
        fmin=fmin,
        n_bins=n_bins,
        bins_per_octave=12,
        hop_length=hop_length,
    ))
    cqt_times = librosa.times_like(cqt, sr=sr, hop_length=hop_length)

    events = []

    for i, t_start in enumerate(onset_times):
        t_end = onset_times[i + 1] if i + 1 < len(onset_times) else float(len(y) / sr)
        duration = max(0.08, float(t_end - t_start))

        start_samp = int(t_start * sr)
        end_samp = min(len(y), int(t_end * sr))
        segment = y[start_samp:end_samp]
        rms = float(np.sqrt(np.mean(segment**2))) if len(segment) > 0 else 0.0
        db = float(librosa.amplitude_to_db(np.array([rms]), ref=1.0)[0])

        f_start = np.searchsorted(cqt_times, t_start)
        f_end = max(f_start + 1, np.searchsorted(cqt_times, t_end))
        slice_spec = np.mean(cqt[:, f_start:f_end], axis=1)
        max_val = np.max(slice_spec)

        if max_val < 0.02 and rms < 0.005:
            continue

        peaks = []
        for b in range(1, len(slice_spec) - 1):
            if slice_spec[b] > slice_spec[b - 1] and slice_spec[b] > slice_spec[b + 1]:
                if slice_spec[b] >= 0.22 * max_val:
                    peaks.append((b, float(slice_spec[b])))

        fundamentals = []
        for b, eng in sorted(peaks, key=lambda x: x[0]):
            m = base_midi + b
            is_harmonic = False
            for f in fundamentals:
                diff = m - f
                if diff in (12, 19, 24, 28, 31):
                    is_harmonic = True
                    break
            if not is_harmonic:
                fundamentals.append(m)

        if not fundamentals:
            fundamentals = [base_midi + int(np.argmax(slice_spec))]

        chord_midi = sorted(fundamentals[:max_polyphony])
        root_midi = chord_midi[0]

        events.append({
            "start_time_sec": round(float(t_start), 3),
            "end_time_sec": round(float(t_end), 3),
            "duration_sec": round(duration, 3),
            "root_midi": root_midi,
            "midi_notes": chord_midi,
            "rms": round(rms, 4),
            "db": round(db, 1),
        })

    return events


ONNX_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "nmp.onnx")


def track_pitches_onnx(y: np.ndarray, sr: int, instrument: str = "guitar") -> List[Dict[str, Any]]:
    """Track authentic polyphonic pitches and chords using Spotify Basic Pitch ONNX neural model.

    Runs offline without TensorFlow dependencies on CPU/GPU via onnxruntime.
    """
    if not os.path.exists(ONNX_MODEL_PATH):
        return []

    try:
        import onnxruntime as ort
    except ImportError:
        return []

    try:
        # Pre-clean audio to remove cymbal/drum bleed
        if pre_clean_stem_audio:
            y_clean = pre_clean_stem_audio(y, sr, instrument=instrument)
        else:
            y_clean = y

        # Resample to 22050 Hz for basic-pitch
        if sr != 22050:
            y_22k = librosa.resample(y_clean, orig_sr=sr, target_sr=22050)
        else:
            y_22k = y_clean
        y_22k = y_22k.astype(np.float32)

        sess = ort.InferenceSession(ONNX_MODEL_PATH, providers=["CPUExecutionProvider"])
        window_samples = 43844
        hop_samples = 22050
        frame_dur = 256.0 / 22050.0

        num_windows = max(1, int(np.ceil((len(y_22k) - window_samples) / hop_samples)) + 1) if len(y_22k) > window_samples else 1
        total_frames = int(np.ceil(len(y_22k) / 256.0))
        note_probs = np.zeros((total_frames, 88), dtype=np.float32)
        weights = np.zeros((total_frames, 1), dtype=np.float32)

        for w_idx in range(num_windows):
            start_samp = w_idx * hop_samples
            end_samp = start_samp + window_samples
            if start_samp >= len(y_22k):
                break
            chunk = y_22k[start_samp:end_samp]
            if len(chunk) < window_samples:
                chunk = np.pad(chunk, (0, window_samples - len(chunk)))

            inp = chunk.reshape(1, window_samples, 1)
            res = sess.run(None, {"serving_default_input_2:0": inp})
            w_notes = res[0][0]

            start_frame = int(round(start_samp / 256.0))
            end_frame = min(total_frames, start_frame + w_notes.shape[0])
            n_copy = end_frame - start_frame
            note_probs[start_frame:end_frame] += w_notes[:n_copy]
            weights[start_frame:end_frame] += 1.0

        weights[weights == 0] = 1.0
        note_probs /= weights

        onset_frames = librosa.onset.onset_detect(y=y_22k, sr=22050, hop_length=256, backtrack=True)
        if len(onset_frames) == 0:
            onset_frames = np.arange(0, total_frames, max(1, int(0.25 / frame_dur)))

        events = []
        inst_lower = instrument.lower()
        threshold = 0.30 if "guitar" in inst_lower else 0.35
        max_poly = 6 if "guitar" in inst_lower else (2 if "bass" in inst_lower else 4)

        for i, f_start in enumerate(onset_frames):
            f_end = onset_frames[i + 1] if i + 1 < len(onset_frames) else total_frames
            if f_start >= total_frames:
                break

            slice_prob = np.mean(note_probs[f_start:f_end], axis=0) if f_end > f_start else note_probs[f_start]
            active_bins = np.where(slice_prob >= threshold)[0]

            if len(active_bins) == 0:
                peak_bin = int(np.argmax(slice_prob))
                if slice_prob[peak_bin] >= 0.22:
                    active_bins = [peak_bin]
                else:
                    continue

            t_start = float(f_start * frame_dur)
            t_end = float(min(total_frames * frame_dur, f_end * frame_dur))
            dur = max(0.08, t_end - t_start)
            midi_notes = sorted([int(b + 21) for b in active_bins])[:max_poly]

            events.append({
                "start_time_sec": round(t_start, 3),
                "end_time_sec": round(t_end, 3),
                "duration_sec": round(dur, 3),
                "root_midi": midi_notes[0],
                "midi_notes": midi_notes,
                "rms": float(np.max(slice_prob[active_bins])),
                "db": -12.0,
            })

        return events
    except Exception:
        return []


def analyze_stem_pitches(stem_path: str, instrument: str, use_onnx: bool = True) -> List[Dict[str, Any]]:
    """Load stem audio file and extract pitch/drum events using ONNX neural model with CQT fallback."""
    if not os.path.exists(stem_path):
        return []
    y, sr = librosa.load(stem_path, sr=22050, mono=True)
    if "drum" in instrument.lower():
        return detect_drum_hits(y, sr)
    else:
        inst_lower = instrument.lower()
        if use_onnx:
            onnx_events = track_pitches_onnx(y, sr, instrument=inst_lower)
            if onnx_events:
                return onnx_events
        # Graceful fallback to pre-cleaned CQT
        if pre_clean_stem_audio:
            y_clean = pre_clean_stem_audio(y, sr, instrument=inst_lower)
        else:
            y_clean = y
        return track_tonal_pitches(y_clean, sr, instrument=inst_lower)

