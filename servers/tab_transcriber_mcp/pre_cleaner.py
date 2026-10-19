"""Pre-cleaning module for audio stems using dynamic VST3 plugins and high-order DSP filtering.

Filters drum and cymbal bleed from melodic stems (guitar, bass, vocals) before
pitch tracking, BPM detection, and tuning estimation. Dynamically discovers installed
VST3 plugins (FabFilter Pro-Q 4, oeksound soothe2, iZotope RX 11) via Pedalboard,
with seamless fallback to high-precision IIR/FIR filter chains.
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
    """Build a Pedalboard chain tailored for cleaning instrument stems.

    - Guitar: Highpass < 75 Hz (remove kick/sub rumble), Lowpass > 5.5 kHz (remove cymbal hiss/sizzle),
              plus FabFilter Pro-Q 4 / soothe2 if discovered to tame harsh resonances.
    - Bass: Highpass < 30 Hz, Lowpass > 2.5 kHz (remove guitar and snare bleed).
    - Vocals: Highpass < 85 Hz (plosives/rumble), Lowpass > 8 kHz.
    - Drums: Highpass < 25 Hz (DC sub-rumble).
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

    if "bass" in inst:
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=30.0))
        board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=2500.0))
    elif any(k in inst for k in ["guitar", "string", "violin", "cello"]):
        # 1. Base surgical highpass and lowpass to eliminate bleed
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=75.0))
        board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=5500.0))

        # 2. Dynamic VST3 resonance suppression and cleanup
        if reg and _find_best_plugin_path:
            soothe_p = _find_best_plugin_path(["soothe2", "soothe"], reg)
            pro_q_p = _find_best_plugin_path(["pro-q 4", "pro-q 3", "pro-q"], reg)
            denoise_p = _find_best_plugin_path(["guitar de-noise", "de-noise"], reg)

            if denoise_p and os.path.exists(denoise_p):
                try:
                    board.append(pedalboard.load_plugin(denoise_p))
                except Exception:
                    pass

            if soothe_p and os.path.exists(soothe_p):
                try:
                    board.append(pedalboard.load_plugin(soothe_p))
                except Exception:
                    pass
            elif pro_q_p and os.path.exists(pro_q_p):
                try:
                    board.append(pedalboard.load_plugin(pro_q_p))
                except Exception:
                    pass
    elif "vocal" in inst:
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=85.0))
        board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=8000.0))
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
        if orig_mono:
            return cleaned_2d[0]
        return cleaned_2d
    except Exception:
        return y
