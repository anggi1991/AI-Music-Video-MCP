"""Phase 14 Test Suite: Optional Auto-Polish Stems with Dynamic VST3 Discovery & Native DSP Fallback.

Tests:
1. Dynamic VST3 Discovery without hardcoded absolute user paths.
2. Simulated zero-VST3 environment guaranteeing 100% graceful fallback to native Pedalboard DSP.
3. Per-stem adaptive chains for all 6 Demucs stem types (vocals, guitar, bass, drums, piano, other).
4. Guitar chain compliance: anti-double-amping rule (NO full amp sims on Demucs guitar stems).
5. Sequential stem processing, manifest persistence (stem_polish_manifest.json), and transparent reporting.
6. Integration with stem_separator.py: separate_audio_6stems(auto_polish_stems=True).
"""

import json
import os
import shutil
import tempfile
import numpy as np
import pytest
import soundfile as sf
import pedalboard as pb

from servers.daw_studio_mcp.vst3_manager import (
    scan_installed_vst3_plugins,
    DEFAULT_VST3_PATHS,
)
from servers.daw_studio_mcp.stem_polisher import (
    build_stem_polish_chain,
    polish_stem_audio,
    polish_stems_batch,
    STEM_EQ_PROFILES,
)
from servers.daw_studio_mcp.stem_separator import separate_audio_6stems


def test_dynamic_vst3_discovery_zero_hardcoding():
    """Verify that VST3 discovery source code uses dynamic scanning and standard paths, without static user paths."""
    vst_source = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "servers",
        "daw_studio_mcp",
        "vst3_manager.py"
    )
    with open(vst_source, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure no personal Windows username is hardcoded in the source code
    assert "anggi" not in content.lower()
    assert "c:\\users\\" not in content.lower()

    # Verify scan returns valid structure
    registry = scan_installed_vst3_plugins()
    assert "total_plugins_found" in registry
    assert "category_a_mastering_and_surgical" in registry
    assert "category_b_vocals_and_reverb" in registry
    assert "category_c_guitar_and_bass" in registry
    assert "category_d_virtual_instruments" in registry
    assert "all_plugins" in registry
    assert isinstance(registry["all_plugins"], dict)


def test_native_dsp_fallback_simulation():
    """Verify 100% graceful fallback to native Pedalboard DSP when zero VST3 plugins exist."""
    empty_plugins: dict = {}

    expected_profiles = {
        "vocals": (85.0, 12000.0, True),
        "guitar": (75.0, 6000.0, False),
        "bass": (30.0, 2500.0, True),
        "drums": (30.0, None, True),
        "piano": (60.0, 10000.0, False),
        "other": (60.0, 10000.0, False),
    }

    for stem_name, (hpf, lpf, has_comp) in expected_profiles.items():
        board, applied_effects, mode = build_stem_polish_chain(stem_name, empty_plugins)

        assert mode == "native_dsp_fallback", f"Stem {stem_name} should report native_dsp_fallback"
        assert len(board) > 0, f"Stem {stem_name} board must contain native DSP filters"
        assert len(applied_effects) > 0

        # Check highpass filter
        hpf_effects = [e for e in applied_effects if "HPF" in e]
        assert len(hpf_effects) == 1, f"Stem {stem_name} missing HPF"
        assert str(int(hpf)) in hpf_effects[0]

        # Check lowpass filter if expected
        if lpf is not None:
            lpf_effects = [e for e in applied_effects if "LPF" in e]
            assert len(lpf_effects) == 1, f"Stem {stem_name} missing LPF"
            assert str(int(lpf)) in lpf_effects[0]

        # Check compressor if expected
        if has_comp:
            comp_effects = [e for e in applied_effects if "Compressor" in e]
            assert len(comp_effects) >= 1, f"Stem {stem_name} missing native compressor"

        # Anti-double-amping rule: NO full amp sims (Archetype) on guitar stem
        if stem_name == "guitar":
            for fx in applied_effects:
                assert "archetype" not in fx.lower(), f"Forbidden amp sim found in guitar polish: {fx}"
                assert "distortion" not in fx.lower(), f"Forbidden distortion found in guitar polish: {fx}"


def test_guitar_anti_double_amping_protection():
    """Verify guitar chain never adds full amp distortion even if Archetype Gojira/Nolly are detected."""
    # Simulate presence of Archetype Gojira and Nolly
    fake_plugins = {
        "all_plugins": {
            "Archetype Gojira X": "C:/dummy/Gojira.vst3",
            "Archetype Nolly X": "C:/dummy/Nolly.vst3",
            "FabFilter Pro-Q 4": "C:/dummy/Pro-Q4.vst3",
        }
    }

    board, applied_effects, mode = build_stem_polish_chain("guitar", fake_plugins)

    for fx in applied_effects:
        assert "archetype" not in fx.lower()
        assert "gojira" not in fx.lower()
        assert "nolly" not in fx.lower()


def test_polish_stem_audio_execution():
    """Verify polish_stem_audio processes audio file, produces output, and preserves audio integrity."""
    sr = 44100
    duration_sec = 0.5
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # Generate test sine wave on 2 channels (stereo)
    sine = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo_audio = np.vstack([sine, sine]).T

    with tempfile.TemporaryDirectory() as tmp_dir:
        in_wav = os.path.join(tmp_dir, "test_vocals.wav")
        out_wav = os.path.join(tmp_dir, "polished_vocals.wav")
        sf.write(in_wav, stereo_audio, sr)

        # Run polish with simulated fallback native DSP
        empty_plugins: dict = {}
        res = polish_stem_audio(
            audio_path=in_wav,
            instrument="vocals",
            output_path=out_wav,
            installed_registry=empty_plugins,
            enable_vst3=False,
        )

        assert res["status"] == "success"
        assert res["mode"] == "native_dsp_fallback"
        assert os.path.isfile(out_wav)
        assert len(res["applied_effects"]) > 0

        # Read back processed audio and check valid values
        processed, read_sr = sf.read(out_wav)
        assert read_sr == sr
        assert processed.shape == stereo_audio.shape
        assert not np.isnan(processed).any()
        assert not np.isinf(processed).any()


def test_polish_stems_batch_sequential_and_manifest():
    """Verify sequential batch processing creates polished stems and stem_polish_manifest.json."""
    sr = 44100
    duration_sec = 0.5
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    stereo_audio = np.vstack([
        0.1 * np.sin(2 * np.pi * 220 * t),
        0.1 * np.sin(2 * np.pi * 220 * t)
    ]).T.astype(np.float32)

    with tempfile.TemporaryDirectory() as tmp_dir:
        stem_names = ["vocals.wav", "guitar.wav", "bass.wav", "drums.wav"]
        for sname in stem_names:
            out_file = os.path.join(tmp_dir, sname)
            sf.write(out_file, stereo_audio, sr)

        manifest = polish_stems_batch(tmp_dir, enable_vst3=False)

        # Verify return structure
        assert "polish_mode" in manifest
        assert manifest["polish_mode"] == "native_dsp_fallback"
        assert "applied_chains" in manifest
        assert "stems_processed" in manifest
        assert len(manifest["stems_processed"]) == len(stem_names)

        # Verify disk manifest
        manifest_path = os.path.join(tmp_dir, "stem_polish_manifest.json")
        assert os.path.isfile(manifest_path)

        with open(manifest_path, "r", encoding="utf-8") as f:
            disk_manifest = json.load(f)

        assert disk_manifest["polish_mode"] == manifest["polish_mode"]
        assert "vocals" in disk_manifest["applied_chains"]
        assert "guitar" in disk_manifest["applied_chains"]
        assert "bass" in disk_manifest["applied_chains"]
        assert "drums" in disk_manifest["applied_chains"]

        # Verify files on disk are valid non-empty audio
        for sname in stem_names:
            fpath = os.path.join(tmp_dir, sname)
            data, read_sr = sf.read(fpath)
            assert read_sr == sr
            assert len(data) == int(sr * duration_sec)


def test_separate_stems_with_auto_polish_integration():
    """Verify separate_audio_6stems executes auto-polish when auto_polish_stems=True."""
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

        # Run with fast experimental_dsp_masks and auto_polish_stems=True
        res = separate_audio_6stems(
            input_song,
            output_dir=tmp_out_dir,
            model_name="experimental_dsp_masks",
            allow_dsp_fallback=True,
            auto_polish_stems=True,
            enable_vst3=False,
        )

        assert res["status"] in ("success", "partial")
        assert res["polish_mode"] == "native_dsp_fallback"
        assert "applied_chains" in res
        assert "vocals" in res["applied_chains"]
        assert "guitar" in res["applied_chains"]

        # Check that manifest file exists on disk
        manifest_file = os.path.join(tmp_out_dir, "stem_polish_manifest.json")
        assert os.path.isfile(manifest_file)
