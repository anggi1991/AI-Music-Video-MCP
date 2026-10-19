"""Dynamic Stem Polisher with VST3 Discovery & Native DSP Fallback (Phase 14).

Applies surgical de-bleed EQ, gentle compression, and dynamic resonance suppression
to isolated Demucs audio stems. Dynamically discovers installed VST3 plugins across Windows,
macOS, and Linux without hardcoded user PC paths. If commercial VST3 plugins are not found,
gracefully falls back to pristine native Pedalboard DSP filters.

Chains per stem:
- vocals: Base Native (HPF 85Hz + LPF 12kHz + Compressor)
          Optional VST3: Pro-Q 4/3 -> Pro-DS -> Pro-C 3/2 -> soothe2 -> Valhalla
- guitar: Base Native (HPF 75Hz + LPF 6kHz)
          Optional VST3: RX 11 De-noise -> Pro-Q 4 -> Pro-MB -> soothe2 -> Ozone 12 Clarity
          (NO full amp distortion to prevent double-amping)
- bass:   Base Native (HPF 30Hz + LPF 2.5kHz + Compressor)
          Optional VST3: Pro-Q 4 -> Ozone 12 Bass Control / Parallax X -> Pro-L 2
- drums:  Base Native (HPF 30Hz + Compressor)
          Optional VST3: Pro-Q 4 -> Saturn 2 -> Pro-C 3 -> soothe2
- piano & other: Base Native (HPF 60Hz + LPF 10kHz)
          Optional VST3: Pro-Q 4 -> soothe2 -> Ozone 12 Clarity -> Valhalla
"""

import json
import os
import sys
import time
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
import soundfile as sf
import pedalboard

try:
    from servers.daw_studio_mcp.vst3_manager import (
        scan_installed_vst3_plugins,
        _find_best_plugin_path,
    )
except ImportError:
    try:
        from vst3_manager import (
            scan_installed_vst3_plugins,
            _find_best_plugin_path,
        )
    except Exception:
        scan_installed_vst3_plugins = None
        _find_best_plugin_path = None


# Module-level Base Native DSP EQ & Dynamics Profiles
STEM_EQ_PROFILES = {
    "vocals": {"hpf": 85.0, "lpf": 12000.0, "comp": True},
    "guitar": {"hpf": 75.0, "lpf": 6000.0, "comp": False},
    "bass": {"hpf": 30.0, "lpf": 2500.0, "comp": True},
    "drums": {"hpf": 30.0, "lpf": None, "comp": True},
    "piano": {"hpf": 60.0, "lpf": 10000.0, "comp": False},
    "other": {"hpf": 60.0, "lpf": 10000.0, "comp": False},
}


def build_stem_polish_chain(
    instrument: str,
    installed_registry: Optional[Dict[str, Any]] = None,
    sample_rate: int = 44100,
    enable_vst3: bool = True,
) -> Tuple[pedalboard.Pedalboard, List[str], str]:
    """Build an adaptive processing chain for a specific instrument stem.

    Returns:
        (board, applied_chain_descriptions, mode)
        where mode is 'flagship_vst3_hybrid' if at least one VST3 plugin was loaded,
        or 'native_dsp_fallback' if only native DSP was used.
    """
    inst = instrument.lower().strip()
    board = pedalboard.Pedalboard()
    applied_effects: List[str] = []
    vst3_loaded_count = 0

    reg = None
    if enable_vst3:
        if installed_registry is not None:
            reg = installed_registry
        elif scan_installed_vst3_plugins is not None:
            try:
                reg = scan_installed_vst3_plugins()
            except Exception:
                reg = None

    def try_load_vst(search_keys: List[str], label: str) -> bool:
        nonlocal vst3_loaded_count
        if not enable_vst3 or not reg or not _find_best_plugin_path:
            return False

        reg_dict = reg if (isinstance(reg, dict) and "all_plugins" in reg) else {"all_plugins": reg}
        all_plugins = reg_dict.get("all_plugins")
        if not isinstance(all_plugins, dict) or not all_plugins:
            return False

        plugin_path = _find_best_plugin_path(search_keys, reg_dict)
        if plugin_path and os.path.exists(plugin_path):
            try:
                loaded = pedalboard.load_plugin(plugin_path)
                board.append(loaded)
                applied_effects.append(label)
                vst3_loaded_count += 1
                return True
            except Exception:
                pass
        return False

    # 1. VOCALS
    if inst == "vocals":
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=85.0))
        board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=12000.0))
        applied_effects.extend(["HPF 85Hz", "LPF 12000Hz"])

        if not try_load_vst(["Pro-Q 4", "Pro-Q 3", "FabFilter Pro-Q"], "FabFilter Pro-Q 4"):
            pass

        try_load_vst(["Pro-DS", "FabFilter Pro-DS"], "FabFilter Pro-DS")

        if not try_load_vst(["Pro-C 3", "Pro-C 2", "FabFilter Pro-C"], "FabFilter Pro-C 3"):
            board.append(pedalboard.Compressor(threshold_db=-18.0, ratio=2.5, attack_ms=15.0, release_ms=100.0))
            applied_effects.append("Native Vocal Compressor")

        try_load_vst(["soothe2", "soothe"], "soothe2")
        try_load_vst(["ValhallaFutureVerb", "ValhallaVintageVerb", "ValhallaRoom"], "Valhalla Reverb")

    # 2. GUITAR (Do NOT add amp distortion directly on Demucs guitar stems to prevent double-amping)
    elif inst == "guitar":
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=75.0))
        board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=6000.0))
        applied_effects.extend(["HPF 75Hz (rumble cut)", "LPF 6000Hz (cymbal bleed cut)"])

        try_load_vst(["Guitar De-noise", "RX 11 Guitar De-noise", "RX 10 Guitar De-noise"], "iZotope RX Guitar De-noise")
        try_load_vst(["Pro-Q 4", "Pro-Q 3", "FabFilter Pro-Q"], "FabFilter Pro-Q 4")
        try_load_vst(["Pro-MB", "FabFilter Pro-MB"], "FabFilter Pro-MB")
        try_load_vst(["soothe2", "soothe"], "soothe2")
        try_load_vst(["Ozone 12 Clarity", "Ozone 11 Clarity", "Ozone Clarity"], "Ozone 12 Clarity")

    # 3. BASS
    elif inst == "bass":
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=30.0))
        board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=2500.0))
        applied_effects.extend(["HPF 30Hz (sub-rumble cut)", "LPF 2500Hz (fret-click/bleed cut)"])

        try_load_vst(["Pro-Q 4", "Pro-Q 3", "FabFilter Pro-Q"], "FabFilter Pro-Q 4")

        loaded_bass_vst = try_load_vst(["Ozone 12 Bass Control", "Ozone 11 Bass Control", "Parallax X", "Parallax"], "Ozone Bass Control / Parallax")
        if not loaded_bass_vst:
            board.append(pedalboard.Compressor(threshold_db=-14.0, ratio=4.0, attack_ms=25.0, release_ms=120.0))
            applied_effects.append("Native Bass Compressor")

        try_load_vst(["Pro-L 2", "Pro-L", "FabFilter Pro-L"], "FabFilter Pro-L 2")

    # 4. DRUMS
    elif inst == "drums":
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=30.0))
        applied_effects.append("HPF 30Hz (sub-sonic rumble cut)")

        try_load_vst(["Pro-Q 4", "Pro-Q 3", "FabFilter Pro-Q"], "FabFilter Pro-Q 4")
        try_load_vst(["Saturn 2", "FabFilter Saturn"], "FabFilter Saturn 2")

        if not try_load_vst(["Pro-C 3", "Pro-C 2", "FabFilter Pro-C"], "FabFilter Pro-C 3"):
            board.append(pedalboard.Compressor(threshold_db=-16.0, ratio=3.0, attack_ms=20.0, release_ms=80.0))
            applied_effects.append("Native Drum Bus Compressor")

        try_load_vst(["soothe2", "soothe"], "soothe2")

    # 5. PIANO, SYNTH, OTHER
    else:
        board.append(pedalboard.HighpassFilter(cutoff_frequency_hz=60.0))
        board.append(pedalboard.LowpassFilter(cutoff_frequency_hz=10000.0))
        applied_effects.extend(["HPF 60Hz", "LPF 10000Hz"])

        try_load_vst(["Pro-Q 4", "Pro-Q 3", "FabFilter Pro-Q"], "FabFilter Pro-Q 4")
        try_load_vst(["soothe2", "soothe"], "soothe2")
        try_load_vst(["Ozone 12 Clarity", "Ozone 11 Clarity"], "Ozone 12 Clarity")
        try_load_vst(["ValhallaFutureVerb", "ValhallaVintageVerb"], "Valhalla Reverb")

    mode = "flagship_vst3_hybrid" if vst3_loaded_count > 0 else "native_dsp_fallback"
    return board, applied_effects, mode


def polish_stem_audio(
    audio_path: str,
    instrument: str,
    output_path: Optional[str] = None,
    installed_registry: Optional[Dict[str, Any]] = None,
    enable_vst3: bool = True,
) -> Dict[str, Any]:
    """Polish a single stem file sequentially to conserve system RAM and VRAM."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Stem file not found: {audio_path}")

    y, sr = sf.read(audio_path, dtype="float32")
    orig_mono = (y.ndim == 1)
    if orig_mono:
        audio_2d = np.ascontiguousarray(np.stack([y, y]), dtype=np.float32)
    else:
        audio_2d = np.ascontiguousarray(y.T if y.shape[1] == 2 and y.shape[0] > 2 else y, dtype=np.float32)

    board, applied_effects, mode = build_stem_polish_chain(
        instrument=instrument,
        installed_registry=installed_registry,
        sample_rate=sr,
        enable_vst3=enable_vst3,
    )

    try:
        processed_2d = board(audio_2d, sr)
    except Exception:
        # Fallback to returning original audio if board processing fails
        processed_2d = audio_2d
        applied_effects.append("Error in DSP processing - bypassed")
        mode = "bypassed"

    out_file = output_path or audio_path
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)

    if orig_mono:
        out_signal = processed_2d[0]
    else:
        out_signal = processed_2d.T

    # Write out polished audio
    sf.write(out_file, out_signal, sr)

    return {
        "status": "success",
        "instrument": instrument,
        "input_path": audio_path,
        "output_path": out_file,
        "mode": mode,
        "applied_effects": applied_effects,
    }


def polish_stems_batch(
    stems_input: Union[Dict[str, str], str],
    output_dir: Optional[str] = None,
    installed_registry: Optional[Dict[str, Any]] = None,
    enable_vst3: bool = True,
) -> Dict[str, Any]:
    """Sequentially polish a collection or directory of stems (vocals, guitar, bass, drums, piano, other)."""
    if isinstance(stems_input, str):
        dir_path = stems_input
        stems_dict: Dict[str, str] = {}
        if os.path.isdir(dir_path):
            for fname in os.listdir(dir_path):
                if fname.lower().endswith(".wav"):
                    inst_key = os.path.splitext(fname)[0].lower()
                    stems_dict[inst_key] = os.path.join(dir_path, fname)
        target_dir = output_dir or dir_path
    else:
        stems_dict = stems_input or {}
        target_dir = output_dir or (
            os.path.dirname(next(iter(stems_dict.values()))) if stems_dict else None
        )

    if not stems_dict:
        return {
            "status": "success",
            "polish_mode": "native_dsp_fallback",
            "applied_chains": {},
            "polished_stems": {},
            "stems_processed": [],
        }

    # Pre-scan registry once for the batch
    reg = None
    if enable_vst3:
        if installed_registry is not None:
            reg = installed_registry
        elif scan_installed_vst3_plugins is not None:
            try:
                reg = scan_installed_vst3_plugins()
            except Exception:
                reg = None

    polished_stems: Dict[str, str] = {}
    applied_chains: Dict[str, List[str]] = {}
    modes: List[str] = []

    for inst_name, stem_path in stems_dict.items():
        if not stem_path or not os.path.exists(stem_path):
            continue

        if output_dir:
            file_name = os.path.basename(stem_path)
            out_file = os.path.join(output_dir, file_name)
        else:
            out_file = stem_path

        res = polish_stem_audio(
            audio_path=stem_path,
            instrument=inst_name,
            output_path=out_file,
            installed_registry=reg,
            enable_vst3=enable_vst3,
        )

        polished_stems[inst_name] = res["output_path"]
        applied_chains[inst_name] = res["applied_effects"]
        modes.append(res["mode"])

    overall_mode = "flagship_vst3_hybrid" if any(m == "flagship_vst3_hybrid" for m in modes) else "native_dsp_fallback"

    manifest_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "polish_mode": overall_mode,
        "applied_chains": applied_chains,
        "stems_processed": list(polished_stems.keys()),
        "polished_stems": polished_stems,
    }

    manifest_path = None
    if target_dir and os.path.isdir(target_dir):
        manifest_path = os.path.join(target_dir, "stem_polish_manifest.json")
        try:
            with open(manifest_path, "w", encoding="utf-8") as mf:
                json.dump(manifest_data, mf, indent=2)
        except Exception:
            pass

    return {
        "status": "success",
        "polish_mode": overall_mode,
        "applied_chains": applied_chains,
        "polished_stems": polished_stems,
        "stems_processed": list(polished_stems.keys()),
        "manifest_path": manifest_path,
    }
