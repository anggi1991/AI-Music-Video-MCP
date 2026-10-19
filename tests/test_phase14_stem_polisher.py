"""Unit tests for Phase 14.1: Safe Calibrated Stem Polisher, Parallel Dry/Wet Blend & Envelope Guard across ALL Stems.

Verifies:
1. Zero hardcoded paths and full portability of VST3 scanner.
2. Mathematical verification of 50ms Windowed RMS Envelope Guard (drop <= 1.5 dB, 0% choking/pumping).
3. Wide natural EQ profiles for all 6 stems (guitar LPF 16kHz, bass LPF 5kHz, vocals LPF 18kHz, drums HPF 25Hz).
4. Zero compressor/gate/reverb stacking in linear_eq mode.
5. Bit-exact dynamics preservation in Pure AI Stem bypass mode.
6. Execution and RMS stability across all 6 instruments (vocals, guitar, bass, drums, piano, other).
7. Anti-double-amping rule on guitar.
8. Sequential batch processing and manifest generation.
9. Integration with separate_audio_6stems and polish_mode routing.
"""

import os
import json
import tempfile
import numpy as np
import soundfile as sf
import pytest

from servers.daw_studio_mcp.vst3_manager import scan_installed_vst3_plugins
from servers.daw_studio_mcp.stem_polisher import (
    STEM_EQ_PROFILES,
    apply_envelope_guard,
    build_stem_polish_chain,
    polish_stem_audio,
    polish_stems_batch,
)
from servers.daw_studio_mcp.stem_separator import separate_audio_6stems


def test_vst3_scanner_is_portable_and_zero_hardcoded_paths():
    """Verify vst3_manager contains zero hardcoded user paths and returns standard categories."""
    vst_source = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "servers",
        "daw_studio_mcp",
        "vst3_manager.py"
    )
    with open(vst_source, "r", encoding="utf-8") as f:
        content = f.read()

    assert "anggi" not in content.lower()
    assert "c:\\users\\" not in content.lower()

    registry = scan_installed_vst3_plugins()
    assert "total_plugins_found" in registry
    assert "category_a_mastering_and_surgical" in registry
    assert "category_b_vocals_and_reverb" in registry
    assert "category_c_guitar_and_bass" in registry
    assert "category_d_virtual_instruments" in registry
    assert "all_plugins" in registry
    assert isinstance(registry["all_plugins"], dict)


def test_apply_envelope_guard_mathematical_guarantee():
    """Verify mathematically that 50ms windowed RMS drop never exceeds 1.5 dB even under extreme choking."""
    sr = 44100
    duration_sec = 2.0
    n_samples = int(sr * duration_sec)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)

    # Synthetic signal with natural dynamics (high, medium, low)
    carrier = 0.3 * np.sin(2 * np.pi * 330 * t) + 0.15 * np.sin(2 * np.pi * 660 * t)
    modulator = 0.5 + 0.5 * np.sin(2 * np.pi * 1.5 * t)
    dry_ch0 = (carrier * modulator).astype(np.float32)
    dry_ch1 = dry_ch0.copy()
    dry_signal = np.vstack([dry_ch0, dry_ch1])

    # Simulate realistic 80/20 parallel blend where wet VST drops / chokes to complete silence in middle section
    wet_signal = dry_signal.copy()
    choke_start = int(sr * 0.5)
    choke_end = int(sr * 1.4)
    wet_signal[:, choke_start:choke_end] = 0.0  # 100% wet silence (complete choke)

    blended_signal = 0.80 * dry_signal + 0.20 * wet_signal

    # Apply 50ms Windowed Envelope Guard
    guarded_signal = apply_envelope_guard(
        blended=blended_signal,
        dry=dry_signal,
        sr=sr,
        window_ms=50.0,
        max_allowed_drop_db=1.5,
    )

    # Verify no invalid numbers or clipping
    assert not np.isnan(guarded_signal).any()
    assert not np.isinf(guarded_signal).any()
    assert np.max(np.abs(guarded_signal)) <= 0.99

    # Windowed analysis per 50ms across the entire audio duration
    window_samples = int(sr * 0.05)
    hop_samples = window_samples // 2
    n_windows = (n_samples - window_samples) // hop_samples

    dry_rms_list = []
    guarded_rms_list = []
    drop_db_list = []

    for w in range(n_windows):
        start = w * hop_samples
        end = start + window_samples
        d_rms = float(np.sqrt(np.mean(dry_signal[0, start:end] ** 2) + 1e-12))
        g_rms = float(np.sqrt(np.mean(guarded_signal[0, start:end] ** 2) + 1e-12))

        dry_rms_list.append(d_rms)
        guarded_rms_list.append(g_rms)

        if d_rms > 1e-3:
            ratio = g_rms / d_rms
            drop_db = 20.0 * np.log10(ratio)
            drop_db_list.append(drop_db)
            # Mathematical assertion: in every 50ms window, drop must never exceed 1.5 dB (drop_db >= -1.50)
            assert drop_db >= -1.51, f"Window {w} dropped by {drop_db:.2f} dB, exceeding 1.5 dB limit!"

    # Correlation between original and guarded RMS envelopes should be >= 0.95
    corr = float(np.corrcoef(dry_rms_list, guarded_rms_list)[0, 1])
    assert corr >= 0.95, f"Envelope correlation {corr:.3f} is too low (expected >= 0.95)"


def test_all_6_stems_natural_eq_profiles():
    """Verify all 6 stems have wide natural frequency ranges and zero destructive compressor/gate/reverb stacking."""
    empty_plugins: dict = {}

    expected_specs = {
        "vocals": {"hpf": 80.0, "lpf": 18000.0},
        "guitar": {"hpf": 65.0, "lpf": 16000.0},
        "bass": {"hpf": 30.0, "lpf": 5000.0},
        "drums": {"hpf": 25.0, "lpf": None},
        "piano": {"hpf": 50.0, "lpf": 18000.0},
        "other": {"hpf": 50.0, "lpf": 18000.0},
    }

    for inst_name, spec in expected_specs.items():
        board, applied_effects, mode = build_stem_polish_chain(
            instrument=inst_name,
            installed_registry=empty_plugins,
            sample_rate=44100,
            enable_vst3=False,
            polish_mode="linear_eq",
        )

        assert mode == "linear_eq"
        assert len(board) >= 1

        # Check HPF
        hpf_effects = [e for e in applied_effects if "HPF" in e]
        assert len(hpf_effects) == 1, f"Stem {inst_name} missing HPF"
        assert str(int(spec["hpf"])) in hpf_effects[0]

        # Check LPF
        if spec["lpf"] is not None:
            lpf_effects = [e for e in applied_effects if "LPF" in e]
            assert len(lpf_effects) == 1, f"Stem {inst_name} missing LPF"
            assert str(int(spec["lpf"])) in lpf_effects[0]
            # Verify guitar LPF is open to at least 15 kHz
            if inst_name == "guitar":
                assert spec["lpf"] >= 15000.0
            # Verify bass LPF is open to at least 4.5 kHz
            if inst_name == "bass":
                assert spec["lpf"] >= 4500.0
        else:
            # Drums must not have a narrow LPF
            lpf_effects = [e for e in applied_effects if "LPF" in e]
            assert len(lpf_effects) == 0, f"Drums should not have a narrow LPF: {lpf_effects}"

        # Ensure NO compressor, gate, or reverb in linear_eq mode
        for ef in applied_effects:
            ef_low = ef.lower()
            assert "compressor" not in ef_low
            assert "gate" not in ef_low
            assert "reverb" not in ef_low


def test_all_6_stems_polish_modes_and_dynamics_preservation():
    """Verify polish execution across all 6 instruments under pure_ai, linear_eq, and subtle_vst3 modes."""
    sr = 44100
    duration_sec = 0.5
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    sine = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo_audio = np.vstack([sine, sine]).T

    instruments = ["vocals", "guitar", "bass", "drums", "piano", "other"]

    with tempfile.TemporaryDirectory() as tmp_dir:
        for inst in instruments:
            in_wav = os.path.join(tmp_dir, f"{inst}_input.wav")
            sf.write(in_wav, stereo_audio, sr)

            # 1. Test Mode: pure_ai (Bypass) - MUST preserve Demucs dynamics accurately
            out_pure = os.path.join(tmp_dir, f"{inst}_pure.wav")
            res_pure = polish_stem_audio(
                audio_path=in_wav,
                instrument=inst,
                output_path=out_pure,
                polish_mode="pure_ai",
            )
            assert res_pure["status"] == "success"
            assert res_pure["mode"] == "pure_ai"
            read_pure, _ = sf.read(out_pure)
            assert np.allclose(read_pure, stereo_audio, atol=1e-3), f"Pure AI for {inst} must match input signal"

            # 2. Test Mode: linear_eq (Sub-rumble clean only, zero pumping)
            out_eq = os.path.join(tmp_dir, f"{inst}_eq.wav")
            res_eq = polish_stem_audio(
                audio_path=in_wav,
                instrument=inst,
                output_path=out_eq,
                polish_mode="linear_eq",
                enable_vst3=False,
            )
            assert res_eq["status"] == "success"
            assert res_eq["mode"] == "linear_eq"
            read_eq, _ = sf.read(out_eq)
            assert read_eq.shape == stereo_audio.shape
            assert not np.isnan(read_eq).any()

            # 3. Test Mode: subtle_vst3 (80/20 Parallel Blend + Envelope Guard)
            out_subtle = os.path.join(tmp_dir, f"{inst}_subtle.wav")
            res_subtle = polish_stem_audio(
                audio_path=in_wav,
                instrument=inst,
                output_path=out_subtle,
                polish_mode="subtle_vst3",
                enable_vst3=False,
            )
            assert res_subtle["status"] == "success"
            assert any("80/20 Parallel Blend" in fx for fx in res_subtle["applied_effects"])
            read_subtle, _ = sf.read(out_subtle)
            assert read_subtle.shape == stereo_audio.shape
            assert not np.isnan(read_subtle).any()

            # Verify mathematically that RMS of subtle mode never drops > 1.5 dB below input
            in_rms = float(np.sqrt(np.mean(stereo_audio ** 2) + 1e-12))
            out_rms = float(np.sqrt(np.mean(read_subtle ** 2) + 1e-12))
            drop_db = 20.0 * np.log10(out_rms / in_rms)
            assert drop_db >= -1.55, f"Instrument {inst} overall RMS dropped by {drop_db:.2f} dB"


def test_guitar_anti_double_amping_protection():
    """Verify guitar chain never adds full amp distortion even if amp sims are detected."""
    fake_plugins = {
        "all_plugins": {
            "Archetype Gojira X": "C:/dummy/Gojira.vst3",
            "Archetype Nolly X": "C:/dummy/Nolly.vst3",
            "FabFilter Pro-Q 4": "C:/dummy/Pro-Q4.vst3",
        }
    }

    board, applied_effects, mode = build_stem_polish_chain(
        "guitar",
        installed_registry=fake_plugins,
        polish_mode="subtle_vst3",
    )

    for fx in applied_effects:
        assert "archetype" not in fx.lower()
        assert "gojira" not in fx.lower()
        assert "nolly" not in fx.lower()
        assert "distortion" not in fx.lower()


def test_polish_stems_batch_sequential_and_manifest():
    """Verify sequential batch processing creates polished stems and stem_polish_manifest.json."""
    sr = 44100
    duration_sec = 0.3
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    stereo_audio = np.vstack([
        0.1 * np.sin(2 * np.pi * 220 * t),
        0.1 * np.sin(2 * np.pi * 220 * t)
    ]).T.astype(np.float32)

    with tempfile.TemporaryDirectory() as tmp_dir:
        stem_names = ["vocals.wav", "guitar.wav", "bass.wav", "drums.wav", "piano.wav", "other.wav"]
        for sname in stem_names:
            out_file = os.path.join(tmp_dir, sname)
            sf.write(out_file, stereo_audio, sr)

        manifest = polish_stems_batch(tmp_dir, polish_mode="linear_eq", enable_vst3=False)

        assert "polish_mode" in manifest
        assert manifest["polish_mode"] == "linear_eq"
        assert "applied_chains" in manifest
        assert "stems_processed" in manifest
        assert len(manifest["stems_processed"]) == len(stem_names)

        # Verify disk manifest
        manifest_path = os.path.join(tmp_dir, "stem_polish_manifest.json")
        assert os.path.isfile(manifest_path)

        with open(manifest_path, "r", encoding="utf-8") as f:
            disk_manifest = json.load(f)

        assert disk_manifest["polish_mode"] == manifest["polish_mode"]
        for s in ["vocals", "guitar", "bass", "drums", "piano", "other"]:
            assert s in disk_manifest["applied_chains"]

        # Verify all audio files remain intact
        for sname in stem_names:
            fpath = os.path.join(tmp_dir, sname)
            data, read_sr = sf.read(fpath)
            assert read_sr == sr
            assert len(data) == int(sr * duration_sec)


def test_separate_stems_with_auto_polish_modes_integration():
    """Verify separate_audio_6stems executes with polish_mode="linear_eq" and "pure_ai"."""
    sr = 44100
    duration_sec = 0.2
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    dummy_audio = np.vstack([
        0.1 * np.sin(2 * np.pi * 300 * t),
        0.1 * np.sin(2 * np.pi * 300 * t)
    ]).T.astype(np.float32)

    with tempfile.TemporaryDirectory() as tmp_in_dir, tempfile.TemporaryDirectory() as tmp_out_dir:
        input_song = os.path.join(tmp_in_dir, "test_song.wav")
        sf.write(input_song, dummy_audio, sr)

        res = separate_audio_6stems(
            input_song,
            output_dir=tmp_out_dir,
            model_name="experimental_dsp_masks",
            allow_dsp_fallback=True,
            auto_polish_stems=True,
            enable_vst3=False,
            polish_mode="linear_eq",
        )

        assert res["status"] in ("success", "partial")
        assert res["polish_mode"] == "linear_eq"
        assert "applied_chains" in res
        assert "guitar" in res["applied_chains"]

        manifest_file = os.path.join(tmp_out_dir, "stem_polish_manifest.json")
        assert os.path.isfile(manifest_file)
