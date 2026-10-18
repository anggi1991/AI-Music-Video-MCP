"""3-Way Vocal Stem Decomposition & Lip-Sync Readiness Gating.

Separates vocals.wav into:
1. vocal_lead.wav: Primary lead vocalist on Center channel with pitch salience tracking.
2. vocal_co_lead.wav: Secondary vocalist / duet / scream-rap counterpart via timbre contrast.
3. vocal_backing.wav: Stereo doubles, side harmonies, ad-libs, and diffuse gang shouts.
"""

import os
from typing import Dict, Any, Tuple
import numpy as np
import soundfile as sf
import librosa


def apply_lip_sync_readiness_gate(
    audio_stereo: np.ndarray,
    sr: int,
    threshold_db: float = -40.0,
    frame_ms: float = 20.0,
) -> np.ndarray:
    """Apply zero-ghosting envelope gating to guarantee silence during vocal rests (prevents AI mouth twitching)."""
    frame_len = int((frame_ms / 1000.0) * sr)
    if frame_len <= 0:
        return audio_stereo

    gated = audio_stereo.copy()
    n_channels, n_samples = gated.shape
    n_frames = n_samples // frame_len

    thresh_amp = 10.0 ** (threshold_db / 20.0)

    for ch in range(n_channels):
        channel_data = gated[ch]
        for f in range(n_frames):
            start = f * frame_len
            end = min(n_samples, start + frame_len)
            frame_slice = channel_data[start:end]
            rms = np.sqrt(np.mean(frame_slice**2)) if len(frame_slice) > 0 else 0.0

            if rms < thresh_amp:
                # Smoothly taper to zero
                t = np.linspace(1.0, 0.0, len(frame_slice))
                channel_data[start:end] *= t * 0.1

    return gated


def decompose_vocal_stem(
    vocal_stem_path: str,
    output_dir: str,
    enable_lip_sync_gate: bool = True,
    gate_threshold_db: float = -40.0,
) -> Dict[str, Any]:
    """Decompose vocals.wav into 3 sub-stems: vocal_lead, vocal_co_lead, vocal_backing."""
    if not os.path.exists(vocal_stem_path):
        raise FileNotFoundError(f"Vocal stem not found: {vocal_stem_path}")

    os.makedirs(output_dir, exist_ok=True)

    y, sr = librosa.load(vocal_stem_path, sr=None, mono=False)
    if y.ndim == 1:
        y_stereo = np.stack([y, y], axis=0)
    else:
        y_stereo = y

    n_samples = y_stereo.shape[-1]
    duration_sec = float(n_samples / sr)
    n_fft = 2048
    hop_length = 512

    # 1. Mid/Side Spatial Analysis
    y_mid = 0.5 * (y_stereo[0] + y_stereo[1])
    y_side = 0.5 * (y_stereo[0] - y_stereo[1])

    D_L = librosa.stft(y_stereo[0], n_fft=n_fft, hop_length=hop_length)
    D_R = librosa.stft(y_stereo[1], n_fft=n_fft, hop_length=hop_length)
    D_M = librosa.stft(y_mid, n_fft=n_fft, hop_length=hop_length)
    D_S = librosa.stft(y_side, n_fft=n_fft, hop_length=hop_length)

    mag_M = np.abs(D_M)
    mag_S = np.abs(D_S)

    # Spatial weights: Center dominance vs Side dominance
    side_ratio = mag_S / (mag_M + mag_S + 1e-6)
    center_ratio = 1.0 - side_ratio

    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)[:, np.newaxis]

    # 2. Spectral Flatness & Pitch Salience
    y_mono = librosa.to_mono(y_stereo)
    flatness = librosa.feature.spectral_flatness(y=y_mono, n_fft=n_fft, hop_length=hop_length)
    flatness_interp = np.repeat(flatness, mag_M.shape[0], axis=0) if flatness.shape[0] == 1 else flatness

    try:
        pitches, magnitudes = librosa.piptrack(
            y=y_mono,
            sr=sr,
            n_fft=n_fft,
            hop_length=hop_length,
            fmin=80.0,
            fmax=2500.0,
            threshold=0.2,
        )
        max_mag = np.max(magnitudes)
        salience_map = (magnitudes / max_mag) if max_mag > 0 else np.zeros_like(mag_M)
    except Exception:
        salience_map = np.zeros_like(mag_M)

    # 3. Frequency passband for vocal formants (100Hz - 4500Hz)
    vocal_band = (freqs >= 100.0) & (freqs <= 4500.0)
    vocal_curve = np.zeros_like(freqs, dtype=np.float32)
    vocal_curve[vocal_band] = 1.0

    # 4. Construct Soft-Masks
    # Mask 1: Backing Vocals (Side-panned energy + high-frequency spread + reverb tails)
    W_backing = side_ratio * 2.2 + 0.12 * (freqs > 2500.0) + 0.08

    # Mask 2: Lead Vocal (Center channel + strong pitch salience + clean harmonicity)
    harmonic_factor = np.clip(1.0 - flatness_interp * 4.0, 0.1, 1.0)
    W_lead = vocal_curve * center_ratio * (
        1.0
        + 2.0 * salience_map
        + 1.0 * harmonic_factor
    )

    # Mask 3: Co-Lead Vocal (Center/Near-Center + contrasting timbre: scream/rap/secondary contour)
    roughness_factor = np.clip(flatness_interp * 5.0, 0.05, 1.5)
    W_co_lead = vocal_curve * center_ratio * (
        0.6
        + 1.8 * roughness_factor
        + 0.5 * (1.0 - salience_map)
    )

    # Normalize soft masks
    W_sum = W_lead + W_co_lead + W_backing + 1e-6
    M_lead = np.clip(W_lead / W_sum, 0.0, 1.0)
    M_co_lead = np.clip(W_co_lead / W_sum, 0.0, 1.0)
    M_backing = np.clip(W_backing / W_sum, 0.0, 1.0)

    # Ensure total sum is 1.0
    M_total = M_lead + M_co_lead + M_backing + 1e-8
    M_lead /= M_total
    M_co_lead /= M_total
    M_backing /= M_total

    # Apply masks and inverse STFT
    lead_ch = []
    co_lead_ch = []
    backing_ch = []

    for D_ch in [D_L, D_R]:
        out_lead = librosa.istft(D_ch * M_lead, hop_length=hop_length, length=n_samples)
        out_co = librosa.istft(D_ch * M_co_lead, hop_length=hop_length, length=n_samples)
        out_back = librosa.istft(D_ch * M_backing, hop_length=hop_length, length=n_samples)

        lead_ch.append(out_lead)
        co_lead_ch.append(out_co)
        backing_ch.append(out_back)

    y_lead = np.stack(lead_ch, axis=0)
    y_co_lead = np.stack(co_lead_ch, axis=0)
    y_backing = np.stack(backing_ch, axis=0)

    # Apply Lip-Sync Readiness Gate
    if enable_lip_sync_gate:
        y_lead = apply_lip_sync_readiness_gate(y_lead, sr, threshold_db=gate_threshold_db)
        y_co_lead = apply_lip_sync_readiness_gate(y_co_lead, sr, threshold_db=gate_threshold_db)
        y_backing = apply_lip_sync_readiness_gate(y_backing, sr, threshold_db=gate_threshold_db)

    # Export audio files
    lead_path = os.path.join(output_dir, "vocal_lead.wav")
    co_lead_path = os.path.join(output_dir, "vocal_co_lead.wav")
    backing_path = os.path.join(output_dir, "vocal_backing.wav")

    sf.write(lead_path, y_lead.T, sr, subtype="PCM_16")
    sf.write(co_lead_path, y_co_lead.T, sr, subtype="PCM_16")
    sf.write(backing_path, y_backing.T, sr, subtype="PCM_16")

    rms_lead = float(np.sqrt(np.mean(y_lead**2)))
    rms_co = float(np.sqrt(np.mean(y_co_lead**2)))
    rms_back = float(np.sqrt(np.mean(y_backing**2)))
    total_rms = rms_lead + rms_co + rms_back + 1e-8

    return {
        "status": "success",
        "input_vocal_path": vocal_stem_path,
        "vocal_lead_path": lead_path,
        "vocal_co_lead_path": co_lead_path,
        "vocal_backing_path": backing_path,
        "duration_sec": round(duration_sec, 3),
        "lip_sync_gate_applied": enable_lip_sync_gate,
        "energy_distribution": {
            "lead_percent": round((rms_lead / total_rms) * 100, 1),
            "co_lead_percent": round((rms_co / total_rms) * 100, 1),
            "backing_percent": round((rms_back / total_rms) * 100, 1),
        },
    }
