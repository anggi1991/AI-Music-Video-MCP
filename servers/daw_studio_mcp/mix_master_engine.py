"""Module for stem mixing, genre DSP chains via pedalboard, LUFS balancing, and mastering."""

import os
import tempfile
from typing import Dict, Optional, Any, List
import numpy as np
import soundfile as sf
import librosa
import pedalboard as pb
import pyloudnorm as pyln
import matchering as mg

try:
    from .vst3_manager import (
        scan_installed_vst3_plugins,
        build_flagship_role_chain,
        apply_vst3_chain_to_audio,
    )
except ImportError:
    from vst3_manager import (
        scan_installed_vst3_plugins,
        build_flagship_role_chain,
        apply_vst3_chain_to_audio,
    )


def get_genre_dsp_chain(instrument: str, genre: str) -> pb.Pedalboard:
    """Return a genre-specific pedalboard DSP chain for a given stem instrument."""
    genre = genre.lower().strip()
    instrument = instrument.lower().strip()

    board = pb.Pedalboard()

    if "guitar" in instrument:
        if "metal" in genre:
            board.append(pb.HighpassFilter(cutoff_frequency_hz=95.0))
            board.append(pb.PeakFilter(cutoff_frequency_hz=3500.0, gain_db=2.0))
            board.append(pb.Compressor(threshold_db=-18.0, ratio=3.0))
        elif "rock" in genre:
            board.append(pb.HighpassFilter(cutoff_frequency_hz=80.0))
            board.append(pb.Compressor(threshold_db=-16.0, ratio=2.5))
        elif "edm" in genre or "pop" in genre:
            board.append(pb.HighpassFilter(cutoff_frequency_hz=120.0))
            board.append(pb.Chorus(rate_hz=1.0, depth=0.25))
        else:
            board.append(pb.HighpassFilter(cutoff_frequency_hz=85.0))

    elif "bass" in instrument:
        if "metal" in genre:
            board.append(pb.HighpassFilter(cutoff_frequency_hz=35.0))
            board.append(pb.LowpassFilter(cutoff_frequency_hz=4200.0))
            board.append(pb.Compressor(threshold_db=-20.0, ratio=4.0))
            board.append(pb.Gain(gain_db=1.0))
        elif "edm" in genre:
            board.append(pb.HighpassFilter(cutoff_frequency_hz=30.0))
            board.append(pb.Compressor(threshold_db=-18.0, ratio=4.5))
        else:
            board.append(pb.HighpassFilter(cutoff_frequency_hz=35.0))
            board.append(pb.Compressor(threshold_db=-18.0, ratio=3.0))

    elif "drum" in instrument:
        if "metal" in genre:
            board.append(pb.Compressor(threshold_db=-16.0, ratio=4.0, attack_ms=10.0, release_ms=80.0))
            board.append(pb.PeakFilter(cutoff_frequency_hz=60.0, gain_db=2.0))
            board.append(pb.Gain(gain_db=1.5))
        elif "edm" in genre:
            board.append(pb.Compressor(threshold_db=-14.0, ratio=4.5, attack_ms=5.0, release_ms=100.0))
            board.append(pb.Gain(gain_db=2.0))
        else:
            board.append(pb.Compressor(threshold_db=-16.0, ratio=3.0))

    elif "vocal_lead" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=90.0))
        board.append(pb.PeakFilter(cutoff_frequency_hz=3000.0, gain_db=2.5))
        board.append(pb.Compressor(threshold_db=-18.0, ratio=3.5, attack_ms=10.0, release_ms=100.0))
        board.append(pb.Reverb(room_size=0.20, wet_level=0.12))

    elif "vocal_co_lead" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=100.0))
        board.append(pb.PeakFilter(cutoff_frequency_hz=2400.0, gain_db=1.8))
        board.append(pb.Compressor(threshold_db=-20.0, ratio=4.0, attack_ms=8.0, release_ms=90.0))
        board.append(pb.Reverb(room_size=0.25, wet_level=0.15))

    elif "vocal_backing" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=125.0))
        board.append(pb.Chorus(rate_hz=1.0, depth=0.35))
        board.append(pb.Compressor(threshold_db=-22.0, ratio=3.0))
        board.append(pb.Reverb(room_size=0.45, wet_level=0.28))

    elif "vocal" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=100.0))
        board.append(pb.Compressor(threshold_db=-18.0, ratio=3.5, attack_ms=15.0, release_ms=120.0))
        board.append(pb.Reverb(room_size=0.25, wet_level=0.15))

    elif "violin" in instrument or "viola" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=180.0))
        board.append(pb.PeakFilter(cutoff_frequency_hz=2500.0, gain_db=2.0))
        board.append(pb.Compressor(threshold_db=-16.0, ratio=2.5))
        board.append(pb.Reverb(room_size=0.30, wet_level=0.18))

    elif "cello" in instrument or "contrabass" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=55.0))
        board.append(pb.PeakFilter(cutoff_frequency_hz=280.0, gain_db=2.0))
        board.append(pb.Compressor(threshold_db=-18.0, ratio=3.0))

    elif "brass" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=120.0))
        board.append(pb.PeakFilter(cutoff_frequency_hz=1500.0, gain_db=2.0))
        board.append(pb.Compressor(threshold_db=-18.0, ratio=3.0))

    elif "choir" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=160.0))
        board.append(pb.Chorus(rate_hz=0.8, depth=0.25))
        board.append(pb.Reverb(room_size=0.50, wet_level=0.35))

    elif "string" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=100.0))
        board.append(pb.Chorus(rate_hz=0.7, depth=0.25))
        board.append(pb.Reverb(room_size=0.40, wet_level=0.22))

    elif "synth" in instrument or "key" in instrument or "piano" in instrument:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=130.0))
        board.append(pb.Chorus(rate_hz=1.2, depth=0.3))
        board.append(pb.Reverb(room_size=0.35, wet_level=0.18))

    else:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=50.0))

    return board


def auto_mix_and_master_stems(
    stem_paths: Dict[str, str],
    genre_profile: str = "metalcore",
    target_lufs: float = -9.0,
    reference_track_path: Optional[str] = None,
    output_master_path: Optional[str] = None,
    auto_use_detected_vst3: bool = True,
    vst3_track_overrides: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    master_vst3_chain: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Mix separated audio stems with Flagship VST3 or genre DSP chains and master to target LUFS or reference."""
    if not stem_paths:
        raise ValueError("stem_paths cannot be empty.")

    if not output_master_path:
        first_stem_path = next(iter(stem_paths.values()))
        project_id = os.path.basename(os.path.dirname(os.path.abspath(first_stem_path))) or os.path.splitext(os.path.basename(first_stem_path))[0]
        output_master_path = os.path.join("workspace", "output_audio", f"{project_id}_master.wav")

    processed_stems = {}
    sample_rate = None
    max_len = 0
    vst_applied_registry = {}

    vst_reg = scan_installed_vst3_plugins() if auto_use_detected_vst3 else None

    # 1. Load and process each stem with VST3 or genre-specific DSP chains
    for stem_name, file_path in stem_paths.items():
        if not os.path.exists(file_path):
            continue

        audio, sr = librosa.load(file_path, sr=None, mono=False)
        if sample_rate is None:
            sample_rate = sr

        # Ensure stereo (2, N)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=0)

        audio_processed = audio
        applied_vsts: List[str] = []

        # Attempt VST3 chain first if enabled
        if auto_use_detected_vst3 and vst_reg:
            chain = (vst3_track_overrides or {}).get(stem_name) or build_flagship_role_chain(stem_name, vst_reg)
            if chain:
                audio_vst, applied_vsts = apply_vst3_chain_to_audio(audio_processed, sample_rate, chain)
                if len(applied_vsts) > 0:
                    audio_processed = audio_vst

        # If no VST3 was applied, apply internal pedalboard DSP chain
        if len(applied_vsts) == 0:
            dsp_chain = get_genre_dsp_chain(stem_name, genre_profile)
            if len(dsp_chain) > 0:
                audio_processed = dsp_chain(audio_processed, sample_rate)

        vst_applied_registry[stem_name] = applied_vsts
        processed_stems[stem_name] = audio_processed
        max_len = max(max_len, audio_processed.shape[-1])

    if not processed_stems:
        raise ValueError("No valid audio stems could be loaded from stem_paths.")

    # 2. Mathematical stem balancing and summing
    mixed_audio = np.zeros((2, max_len), dtype=np.float32)

    # Stem balance weights
    stem_balance_weights = {
        "vocal_lead": 1.0,
        "vocal_co_lead": 0.88,
        "vocal_backing": 0.72,
        "vocals": 1.0,
        "drums": 1.0,
        "bass": 0.85,
        "guitar_rhythm": 0.82,
        "guitar_lead": 0.88,
        "guitar_additional": 0.65,
        "guitar": 0.80,
        "violin": 0.78,
        "cello": 0.78,
        "string": 0.72,
        "brass": 0.75,
        "woodwind": 0.70,
        "choir": 0.72,
        "synth": 0.65,
        "piano": 0.65,
    }

    for stem_name, audio_data in processed_stems.items():
        weight = 0.8
        for k, v in stem_balance_weights.items():
            if k in stem_name.lower():
                weight = v
                break

        curr_len = audio_data.shape[-1]
        mixed_audio[:, :curr_len] += audio_data * weight

    # Prevent digital clipping before mastering
    peak = np.max(np.abs(mixed_audio))
    if peak > 0.95:
        mixed_audio = mixed_audio * (0.95 / peak)

    # Apply Master Bus VST3 chain (Ozone / Pro-Q / Pro-L) if enabled
    master_vsts_applied = []
    if auto_use_detected_vst3 and vst_reg:
        m_chain = master_vst3_chain or build_flagship_role_chain("master_bus", vst_reg)
        if m_chain:
            mixed_audio, master_vsts_applied = apply_vst3_chain_to_audio(mixed_audio, sample_rate, m_chain)

    os.makedirs(os.path.dirname(os.path.abspath(output_master_path)), exist_ok=True)

    # 3. Mastering stage
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_unmastered:
        temp_unmastered_path = tmp_unmastered.name

    try:
        sf.write(temp_unmastered_path, mixed_audio.T, sample_rate)

        mastering_method = "matchering" if reference_track_path and os.path.exists(reference_track_path) else "pyloudnorm_dsp"

        if mastering_method == "matchering":
            # Matchering reference mastering
            mg.process(
                target=temp_unmastered_path,
                reference=reference_track_path,
                results=[mg.pcm16(output_master_path)],
            )
        else:
            # Pyloudnorm + Pedalboard True-Peak Limiter
            meter = pyln.Meter(sample_rate)
            current_lufs = meter.integrated_loudness(mixed_audio.T)

            if not np.isneginf(current_lufs) and not np.isnan(current_lufs):
                gain_db = target_lufs - current_lufs
            else:
                gain_db = 0.0

            # Master chain: Gain to target LUFS + Brickwall Limiter to -0.5 dB
            master_chain = pb.Pedalboard([
                pb.Gain(gain_db=float(gain_db)),
                pb.Limiter(threshold_db=-0.5),
            ])
            mastered_data = master_chain(mixed_audio, sample_rate)
            sf.write(output_master_path, mastered_data.T, sample_rate, subtype="PCM_16")

    finally:
        if os.path.exists(temp_unmastered_path):
            try:
                os.remove(temp_unmastered_path)
            except OSError:
                pass

    # 4. Measure final integrated LUFS
    final_audio, _ = sf.read(output_master_path)
    final_meter = pyln.Meter(sample_rate)
    final_lufs = float(final_meter.integrated_loudness(final_audio))

    return {
        "status": "success",
        "output_master_path": output_master_path,
        "genre_profile": genre_profile,
        "mastering_method": mastering_method,
        "target_lufs": target_lufs,
        "final_lufs": round(final_lufs, 2),
        "stems_processed": list(processed_stems.keys()),
        "vst3_applied_per_stem": vst_applied_registry,
        "master_vst3_applied": master_vsts_applied,
        "sample_rate": sample_rate,
        "duration_sec": round(len(final_audio) / sample_rate, 3),
    }
