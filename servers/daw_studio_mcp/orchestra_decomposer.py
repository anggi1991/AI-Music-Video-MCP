"""Dynamic Orchestral Instrument Detection and Stem Decomposer.

Detects active orchestral components (Violin, Viola, Cello, Strings Ensemble, Brass,
Woodwinds, Choir, Harp) and decomposes them via STFT Time-Frequency Soft-Masking.
"""

import os
from typing import Dict, Any, List, Optional
import numpy as np
import soundfile as sf
import librosa


ORCHESTRAL_PROFILES = {
    "violin": {
        "freq_range": (196.0, 3800.0),
        "target_centroid": (1200.0, 3500.0),
        "min_harmonic_ratio": 0.55,
        "side_preference": 0.5,  # balanced or slightly panned
    },
    "cello": {
        "freq_range": (65.0, 950.0),
        "target_centroid": (250.0, 900.0),
        "min_harmonic_ratio": 0.60,
        "side_preference": 0.4,
    },
    "strings_ensemble": {
        "freq_range": (130.0, 3000.0),
        "target_centroid": (600.0, 2200.0),
        "min_harmonic_ratio": 0.50,
        "side_preference": 0.7,  # wide stereo spread
    },
    "brass": {
        "freq_range": (150.0, 2800.0),
        "target_centroid": (800.0, 2600.0),
        "min_harmonic_ratio": 0.55,
        "side_preference": 0.45,
    },
    "woodwinds": {
        "freq_range": (260.0, 3200.0),
        "target_centroid": (700.0, 2400.0),
        "min_harmonic_ratio": 0.65,
        "side_preference": 0.35,
    },
    "choir": {
        "freq_range": (220.0, 2400.0),
        "target_centroid": (500.0, 2000.0),
        "min_harmonic_ratio": 0.50,
        "side_preference": 0.65,
    },
}


def detect_active_instruments_in_stem(
    audio_path: str,
    energy_threshold_db: float = -38.0,
    min_confidence: float = 0.25,
) -> Dict[str, Any]:
    """Analyze time-frequency spectrum and acoustic features to detect which orchestral instruments are present."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    y, sr = librosa.load(audio_path, sr=None, mono=False)
    if y.ndim == 1:
        y_stereo = np.stack([y, y], axis=0)
    else:
        y_stereo = y

    y_mono = librosa.to_mono(y_stereo)
    duration_sec = float(len(y_mono) / sr)

    rms = float(np.sqrt(np.mean(y_mono**2)))
    rms_db = float(librosa.amplitude_to_db(np.array([rms]), ref=1.0)[0]) if rms > 0 else -100.0

    if rms_db < energy_threshold_db:
        return {
            "audio_path": audio_path,
            "overall_energy_db": round(rms_db, 2),
            "is_silent": True,
            "active_instruments": [],
            "detection_summary": {},
        }

    # Acoustic feature extraction
    n_fft = 2048
    hop_length = 512

    # Mid/Side
    y_mid = 0.5 * (y_stereo[0] + y_stereo[1])
    y_side = 0.5 * (y_stereo[0] - y_stereo[1])
    D_mid = librosa.stft(y_mid, n_fft=n_fft, hop_length=hop_length)
    D_side = librosa.stft(y_side, n_fft=n_fft, hop_length=hop_length)
    mag_M = np.abs(D_mid)
    mag_S = np.abs(D_side)
    side_ratio = float(np.mean(mag_S) / (np.mean(mag_M) + np.mean(mag_S) + 1e-6))

    # Spectral centroid & flatness
    centroid = librosa.feature.spectral_centroid(y=y_mono, sr=sr, n_fft=n_fft, hop_length=hop_length)[0]
    mean_centroid = float(np.mean(centroid))
    flatness = librosa.feature.spectral_flatness(y=y_mono, n_fft=n_fft, hop_length=hop_length)[0]
    mean_flatness = float(np.mean(flatness))

    # HPSS (Harmonic vs Percussive)
    H, P = librosa.decompose.hpss(D_mid, margin=(1.2, 1.2))
    h_energy = float(np.mean(np.abs(H)))
    p_energy = float(np.mean(np.abs(P)))
    harmonic_ratio = h_energy / (h_energy + p_energy + 1e-6)

    # Sub-band energy distribution
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    mag_mono = np.abs(librosa.stft(y_mono, n_fft=n_fft, hop_length=hop_length))
    total_energy = float(np.sum(mag_mono) + 1e-6)

    active_instruments = []
    detection_summary = {}

    for inst_name, prof in ORCHESTRAL_PROFILES.items():
        f_low, f_high = prof["freq_range"]
        c_low, c_high = prof["target_centroid"]

        # 1. Band energy score
        band_mask = (freqs >= f_low) & (freqs <= f_high)
        band_energy = float(np.sum(mag_mono[band_mask, :])) / total_energy
        band_score = float(np.clip(band_energy * 3.5, 0.0, 1.0))

        # 2. Centroid fit score
        if c_low <= mean_centroid <= c_high:
            centroid_score = 1.0
        else:
            dist = min(abs(mean_centroid - c_low), abs(mean_centroid - c_high))
            centroid_score = float(np.exp(-dist / 1200.0))

        # 3. Harmonicity score
        harm_score = float(np.clip(harmonic_ratio / prof["min_harmonic_ratio"], 0.0, 1.0))

        # 4. Spatial / Stereo fit
        expected_side = prof["side_preference"]
        spatial_score = float(1.0 - abs(side_ratio - expected_side))

        # Weighted confidence calculation
        confidence = (
            0.40 * band_score
            + 0.25 * centroid_score
            + 0.20 * harm_score
            + 0.15 * spatial_score
        )
        confidence = float(np.clip(confidence, 0.0, 1.0))

        detection_summary[inst_name] = {
            "confidence": round(confidence, 3),
            "band_energy_percent": round(band_energy * 100, 1),
            "centroid_score": round(centroid_score, 2),
        }

        if confidence >= min_confidence:
            active_instruments.append({
                "instrument": inst_name,
                "confidence": round(confidence, 3),
                "start_time_sec": 0.0,
                "end_time_sec": round(duration_sec, 3),
            })

    # Sort detected instruments by confidence descending
    active_instruments.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "audio_path": audio_path,
        "duration_sec": round(duration_sec, 3),
        "overall_energy_db": round(rms_db, 2),
        "is_silent": False,
        "mean_centroid_hz": round(mean_centroid, 1),
        "harmonic_ratio": round(harmonic_ratio, 3),
        "side_stereo_ratio": round(side_ratio, 3),
        "active_instruments": active_instruments,
        "detection_summary": detection_summary,
    }


def decompose_orchestral_stem(
    other_stem_path: str,
    output_dir: str,
    auto_detect_only: bool = True,
    min_confidence: float = 0.25,
) -> Dict[str, Any]:
    """Decompose other.wav into separated orchestral instrument stems using soft-masking."""
    if not os.path.exists(other_stem_path):
        raise FileNotFoundError(f"Stem file not found: {other_stem_path}")

    os.makedirs(output_dir, exist_ok=True)

    # 1. Detect active instruments
    detect_res = detect_active_instruments_in_stem(
        other_stem_path,
        min_confidence=min_confidence,
    )
    detected_list = [item["instrument"] for item in detect_res.get("active_instruments", [])]

    if auto_detect_only and not detected_list:
        # Default to strings_ensemble if none crossed threshold
        detected_list = ["strings_ensemble"]

    target_instruments = detected_list if auto_detect_only else list(ORCHESTRAL_PROFILES.keys())

    # 2. Load audio
    y, sr = librosa.load(other_stem_path, sr=None, mono=False)
    if y.ndim == 1:
        y_stereo = np.stack([y, y], axis=0)
    else:
        y_stereo = y

    n_samples = y_stereo.shape[-1]
    n_fft = 2048
    hop_length = 512

    D_L = librosa.stft(y_stereo[0], n_fft=n_fft, hop_length=hop_length)
    D_R = librosa.stft(y_stereo[1], n_fft=n_fft, hop_length=hop_length)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)[:, np.newaxis]

    # 3. Build acoustic soft masks
    masks = {}
    total_weights = np.zeros_like(freqs, dtype=np.float32)

    for inst in target_instruments:
        prof = ORCHESTRAL_PROFILES.get(inst, ORCHESTRAL_PROFILES["strings_ensemble"])
        f_low, f_high = prof["freq_range"]

        # Frequency curve
        center_f = 0.5 * (f_low + f_high)
        bandwidth = max(100.0, 0.5 * (f_high - f_low))
        w_curve = np.exp(-0.5 * ((freqs - center_f) / bandwidth) ** 2)

        # Enhance specific characteristics
        if inst in ("violin", "cello"):
            w_curve *= 1.2
        elif inst == "brass":
            # Formant boost around 1500Hz
            w_curve += 0.5 * np.exp(-0.5 * ((freqs - 1500.0) / 400.0) ** 2)
        elif inst == "choir":
            # Formant double peaks (F1 600Hz, F2 1500Hz)
            w_curve += 0.4 * np.exp(-0.5 * ((freqs - 600.0) / 150.0) ** 2)
            w_curve += 0.4 * np.exp(-0.5 * ((freqs - 1500.0) / 250.0) ** 2)

        masks[inst] = w_curve
        total_weights += w_curve

    total_weights += 0.1  # residual floor

    # Normalize soft masks
    exported_stems = {}
    energy_shares = {}

    for inst, mask in masks.items():
        norm_mask = mask / total_weights
        out_L = librosa.istft(D_L * norm_mask, hop_length=hop_length, length=n_samples)
        out_R = librosa.istft(D_R * norm_mask, hop_length=hop_length, length=n_samples)
        out_stereo = np.stack([out_L, out_R], axis=0)

        out_path = os.path.join(output_dir, f"{inst}.wav")
        sf.write(out_path, out_stereo.T, sr, subtype="PCM_16")
        exported_stems[inst] = out_path

        rms_val = float(np.sqrt(np.mean(out_stereo**2)))
        energy_shares[inst] = round(rms_val, 4)

    return {
        "status": "success",
        "input_stem_path": other_stem_path,
        "output_dir": output_dir,
        "detected_active_instruments": detect_res.get("active_instruments", []),
        "exported_stems": exported_stems,
        "energy_shares": energy_shares,
        "duration_sec": detect_res.get("duration_sec", 0.0),
    }
