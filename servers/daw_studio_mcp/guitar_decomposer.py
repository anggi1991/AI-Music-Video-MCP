"""Hybrid Spatial (Mid/Side) + Spectral-Salience 3-Way Guitar Stem Decomposer.

Separates guitar.wav into:
1. guitar_rhythm.wav: Power chords, palm-mute chugs, low-mid riffs, side-heavy spatial weighting.
2. guitar_lead.wav: High-register melody lines, solos, octave leads, bends, centered spatial image.
3. guitar_additional.wav: Ambient layers, clean arpeggios, secondary harmony, stereo diffuse shimmer.
"""

import os
from typing import Dict, Any, Tuple
import numpy as np
import soundfile as sf
import librosa


def create_smooth_frequency_curve(
    freqs: np.ndarray,
    low_cutoff: float,
    low_trans: float,
    high_trans: float,
    high_cutoff: float,
) -> np.ndarray:
    """Create a smooth trapezoidal frequency window curve with cosine roll-offs."""
    curve = np.zeros_like(freqs, dtype=np.float32)

    # In band: full pass
    pass_band = (freqs >= low_trans) & (freqs <= high_trans)
    curve[pass_band] = 1.0

    # Low roll-off
    low_band = (freqs >= low_cutoff) & (freqs < low_trans)
    if np.any(low_band):
        t = (freqs[low_band] - low_cutoff) / max(1.0, (low_trans - low_cutoff))
        curve[low_band] = 0.5 * (1.0 - np.cos(np.pi * t))

    # High roll-off
    high_band = (freqs > high_trans) & (freqs <= high_cutoff)
    if np.any(high_band):
        t = (high_cutoff - freqs[high_band]) / max(1.0, (high_cutoff - high_trans))
        curve[high_band] = 0.5 * (1.0 - np.cos(np.pi * t))

    return curve


def decompose_guitar_stem(
    guitar_stem_path: str,
    output_dir: str,
) -> Dict[str, Any]:
    """Decompose guitar.wav into 3 sub-stems using Hybrid Spatial (M/S) + Spectral-Salience decomposition.

    Args:
        guitar_stem_path: Path to the input guitar audio file.
        output_dir: Directory where guitar_rhythm.wav, guitar_lead.wav, and guitar_additional.wav will be written.

    Returns:
        dict: Paths, energy ratios, duration, and decomposition status.
    """
    if not os.path.exists(guitar_stem_path):
        raise FileNotFoundError(f"Guitar stem file not found: {guitar_stem_path}")

    os.makedirs(output_dir, exist_ok=True)

    # 1. Load audio (preserve native sample rate and stereo channels)
    y, sr = librosa.load(guitar_stem_path, sr=None, mono=False)
    if y.ndim == 1:
        # Mono: duplicate to dual-mono stereo
        y_stereo = np.stack([y, y], axis=0)
    else:
        y_stereo = y

    n_channels, n_samples = y_stereo.shape
    y_mono = librosa.to_mono(y_stereo)
    duration_sec = float(n_samples / sr)

    n_fft = 2048
    hop_length = 512

    # 2. Mid/Side (M/S) Spatial Analysis
    # Mid = (L + R) / 2, Side = (L - R) / 2
    y_mid = 0.5 * (y_stereo[0] + y_stereo[1])
    y_side = 0.5 * (y_stereo[0] - y_stereo[1])

    D_L = librosa.stft(y_stereo[0], n_fft=n_fft, hop_length=hop_length)
    D_R = librosa.stft(y_stereo[1], n_fft=n_fft, hop_length=hop_length)
    D_M = librosa.stft(y_mid, n_fft=n_fft, hop_length=hop_length)
    D_S = librosa.stft(y_side, n_fft=n_fft, hop_length=hop_length)

    mag_L = np.abs(D_L)
    mag_R = np.abs(D_R)
    mag_M = np.abs(D_M)
    mag_S = np.abs(D_S)

    # Spatial Side Ratio: 0.0 = completely center/mid, 1.0 = completely wide/side
    side_ratio = mag_S / (mag_M + mag_S + 1e-6)

    # Frequency grid
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)[:, np.newaxis]

    # 3. Harmonic-Percussive Source Separation (HPSS) for Transient & Chug Detection
    H_L, P_L = librosa.decompose.hpss(D_L, margin=(1.2, 1.2))
    H_R, P_R = librosa.decompose.hpss(D_R, margin=(1.2, 1.2))

    H_mag = 0.5 * (np.abs(H_L) + np.abs(H_R))
    P_mag = 0.5 * (np.abs(P_L) + np.abs(P_R))
    percussive_ratio = P_mag / (H_mag + P_mag + 1e-6)
    harmonic_ratio = H_mag / (H_mag + P_mag + 1e-6)

    # 4. Predominant Pitch Salience Tracking for Lead/Melody Lines (350Hz - 3500Hz)
    try:
        pitches, magnitudes = librosa.piptrack(
            y=y_mono,
            sr=sr,
            n_fft=n_fft,
            hop_length=hop_length,
            fmin=350.0,
            fmax=3500.0,
            threshold=0.2,
        )
        max_sal = np.max(magnitudes)
        salience_map = (magnitudes / max_sal) if max_sal > 0 else np.zeros_like(mag_M)
    except Exception:
        salience_map = np.zeros_like(mag_M)

    # 5. Build Spectral Weight Profiles
    # Rhythm: 75Hz - 650Hz core, taper to 1600Hz
    curve_rhythm = create_smooth_frequency_curve(
        freqs, low_cutoff=50.0, low_trans=85.0, high_trans=650.0, high_cutoff=1800.0
    )

    # Lead: 350Hz - 3500Hz core, taper to 5500Hz
    curve_lead = create_smooth_frequency_curve(
        freqs, low_cutoff=250.0, low_trans=400.0, high_trans=3200.0, high_cutoff=5500.0
    )

    # Additional: High shimmer > 2500Hz and diffuse residual
    curve_additional = create_smooth_frequency_curve(
        freqs, low_cutoff=2000.0, low_trans=3000.0, high_trans=sr / 2.0 - 200.0, high_cutoff=sr / 2.0
    )

    # 6. Hybrid Spatial + Salience Weighting
    # Rhythm weight: Low-mid frequency + percussive chugs + side-panned stereo dominance
    W_rhythm = curve_rhythm * (
        1.0
        + 1.8 * percussive_ratio
        + 1.0 * side_ratio
    )

    # Lead weight: Melody band + harmonic tone + center spatial focus + pitch salience
    center_focus = 1.0 - side_ratio
    W_lead = curve_lead * (
        1.0
        + 1.5 * harmonic_ratio
        + 1.5 * center_focus
        + 2.5 * salience_map
    )

    # Additional weight: Ambient/shimmer + diffuse residual + baseline energy
    W_additional = (
        curve_additional * (1.0 + 0.8 * side_ratio)
        + 0.15  # baseline noise/ambient floor
    )

    # 7. Soft Mask Normalization (Wiener-like energy conservation: M_r + M_l + M_a == 1)
    W_total = W_rhythm + W_lead + W_additional + 1e-7
    M_rhythm = np.clip(W_rhythm / W_total, 0.0, 1.0)
    M_lead = np.clip(W_lead / W_total, 0.0, 1.0)
    M_additional = np.clip(W_additional / W_total, 0.0, 1.0)

    # Re-normalize to guarantee sum == 1.0 for zero phase cancellation
    M_sum = M_rhythm + M_lead + M_additional + 1e-8
    M_rhythm /= M_sum
    M_lead /= M_sum
    M_additional /= M_sum

    # 8. Apply Soft Masks & Inverse STFT (iSTFT)
    y_rhythm_channels = []
    y_lead_channels = []
    y_add_channels = []

    for ch_idx, D_ch in enumerate([D_L, D_R]):
        D_rhythm_ch = D_ch * M_rhythm
        D_lead_ch = D_ch * M_lead
        D_add_ch = D_ch * M_additional

        out_r = librosa.istft(D_rhythm_ch, hop_length=hop_length, length=n_samples)
        out_l = librosa.istft(D_lead_ch, hop_length=hop_length, length=n_samples)
        out_a = librosa.istft(D_add_ch, hop_length=hop_length, length=n_samples)

        y_rhythm_channels.append(out_r)
        y_lead_channels.append(out_l)
        y_add_channels.append(out_a)

    y_rhythm = np.stack(y_rhythm_channels, axis=0)
    y_lead = np.stack(y_lead_channels, axis=0)
    y_additional = np.stack(y_add_channels, axis=0)

    # 9. Export output audio files
    rhythm_path = os.path.join(output_dir, "guitar_rhythm.wav")
    lead_path = os.path.join(output_dir, "guitar_lead.wav")
    additional_path = os.path.join(output_dir, "guitar_additional.wav")

    sf.write(rhythm_path, y_rhythm.T, sr, subtype="PCM_16")
    sf.write(lead_path, y_lead.T, sr, subtype="PCM_16")
    sf.write(additional_path, y_additional.T, sr, subtype="PCM_16")

    # Measure RMS energies
    rms_rhythm = float(np.sqrt(np.mean(y_rhythm**2)))
    rms_lead = float(np.sqrt(np.mean(y_lead**2)))
    rms_add = float(np.sqrt(np.mean(y_additional**2)))
    total_rms = rms_rhythm + rms_lead + rms_add + 1e-8

    return {
        "status": "success",
        "input_guitar_path": guitar_stem_path,
        "guitar_rhythm_path": rhythm_path,
        "guitar_lead_path": lead_path,
        "guitar_additional_path": additional_path,
        "duration_sec": round(duration_sec, 3),
        "sample_rate": sr,
        "energy_distribution": {
            "rhythm_percent": round((rms_rhythm / total_rms) * 100, 1),
            "lead_percent": round((rms_lead / total_rms) * 100, 1),
            "additional_percent": round((rms_add / total_rms) * 100, 1),
        },
    }
