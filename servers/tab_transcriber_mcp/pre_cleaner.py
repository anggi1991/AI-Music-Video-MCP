"""Pre-cleaning module for audio stems using dynamic VST3 plugins and high-order DSP filtering.

Filters drum and cymbal bleed from melodic stems (guitar, bass, vocals) before
pitch tracking, BPM detection, and tuning estimation. Dynamically discovers installed
VST3 plugins (FabFilter Pro-Q 4, oeksound soothe2) via Pedalboard,
with seamless fallback to high-precision IIR/FIR filter chains.

Phase 14.1 Updates:
- Removed RX Guitar De-noise to eliminate note choking / dropouts during pitch analysis.
- Raised guitar LPF from 5.5 kHz to 12.0 kHz so string transients and upper harmonics are preserved.
- Raised bass LPF to 4.5 kHz and vocal LPF to 16.0 kHz.
- Calibrated soothe2 to gentle depth (1.0) and moderate mix (35%) so chords are not scooped.
"""

import os
import numpy as np
import pedalboard
from typing import Optional, Tuple, Dict, Any

try:
    from servers.daw_studio_mcp.vst3_manager import scan_installed_vst3_plugins, _find_best_plugin_path
except ImportError:
    try:
        from vst3_manager import scan_installed_vst3_plugins, _find_best_plugin_path
    except Exception:
        scan_installed_vst3_plugins = None
        _find_best_plugin_path = None


def build_cleaning_board(instrument: str = "guitar", sample_rate: int = 44100) -> pedalboard.Pedalboard:
    """Build a Pedalboard chain tailored for cleaning instrument stems before transcription.

    - Guitar: Highpass 65 Hz (remove rumble), Lowpass 12.0 kHz (preserve string attack & pitch).
    - Bass: Highpass 30 Hz, Lowpass 4.5 kHz (retain clank/articulation for pitch solver).
    - Vocals: Highpass 80 Hz, Lowpass 16.0 kHz.
    - Drums: Highpass 25 Hz (DC sub-rumble).
    """
    inst = instrument.lower().strip()
    board = pedalboard.Pedalboard()

    # Dynamic VST3 resolution
    reg = None
    if scan_installed_vst3_plugins:
        try:
            reg = scan_installed_vst3_plugins()
        except Exception:
            reg = None

    max_nyquist = 0.48 * sample_rate

    if "bass" in inst:
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=30.0))
        lpf_cut = min(4500.0, max_nyquist)
        if lpf_cut < max_nyquist:
            board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=lpf_cut))
    elif any(k in inst for k in ["guitar", "string", "violin", "cello"]):
        # 1. Base surgical highpass and natural lowpass
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=65.0))
        lpf_cut = min(12000.0, max_nyquist)
        if lpf_cut < max_nyquist:
            board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=lpf_cut))

        # 2. Dynamic VST3 resonance suppression (only at standard studio SR >= 44.1kHz)
        if sample_rate >= 44100 and reg and _find_best_plugin_path:
            soothe_p = _find_best_plugin_path(["soothe2", "soothe"], reg)
            pro_q_p = _find_best_plugin_path(["pro-q 4", "pro-q 3", "pro-q"], reg)

            if soothe_p and os.path.exists(soothe_p):
                try:
                    loaded = pedalboard.load_plugin(soothe_p)
                    # Calibrate soothe2 to gentle mode
                    if hasattr(loaded, "depth"):
                        loaded.depth = 1.0
                    if hasattr(loaded, "sharpness"):
                        loaded.sharpness = 2.0
                    if hasattr(loaded, "mix"):
                        loaded.mix = 35.0
                    board.append(loaded)
                except Exception:
                    pass
            elif pro_q_p and os.path.exists(pro_q_p):
                try:
                    board.append(pedalboard.load_plugin(pro_q_p))
                except Exception:
                    pass
    elif "vocal" in inst:
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=80.0))
        lpf_cut = min(16000.0, max_nyquist)
        if lpf_cut < max_nyquist:
            board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=lpf_cut))
    else:
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=35.0))

    return board


def pre_clean_stem_audio(y: np.ndarray, sr: int, instrument: str = "guitar") -> np.ndarray:
    """Clean an audio signal (1D mono or 2D stereo) before pitch/BPM analysis."""
    if y is None or len(y) == 0:
        return y

    orig_mono = (y.ndim == 1)
    if orig_mono:
        audio_2d = np.ascontiguousarray(np.stack([y, y]), dtype=np.float32)
    else:
        audio_2d = np.ascontiguousarray(y if y.shape[0] <= 2 else y.T, dtype=np.float32)

    try:
        board = build_cleaning_board(instrument=instrument, sample_rate=sr)
        cleaned_2d = board(audio_2d, sr)
        if np.isnan(cleaned_2d).any() or np.isinf(cleaned_2d).any():
            return y
        if orig_mono:
            return cleaned_2d[0]
        return cleaned_2d
    except Exception:
        return y
