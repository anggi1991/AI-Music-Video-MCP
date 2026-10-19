import sys
import os
import json
import subprocess
import pytest
import numpy as np
import soundfile as sf

import servers.cli_runner as cli_runner
from servers.cli_runner import run_action


def create_test_wav(filepath: str, duration_sec: float = 2.0, sr: int = 44100):
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    stereo = np.column_stack([audio, audio])
    sf.write(filepath, stereo, sr, subtype="PCM_16")


def test_cli_runner_scan_vst3():
    res = run_action("scan_vst3", {})
    assert res["status"] == "success"
    assert "total_plugins_found" in res
    assert "category_a_mastering_and_surgical" in res
    assert "category_b_vocals_and_reverb" in res
    assert "category_c_guitar_and_bass" in res
    assert "category_d_virtual_instruments" in res


def test_cli_runner_inspect_vst3():
    res = run_action("inspect_vst3", {"vst3_path": "C:/NonExistent/Plugin.vst3"})
    assert res["status"] == "error"
    assert res["is_instrument"] is False


def test_cli_runner_audio_and_stems(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    source_dir = project_root / "workspace" / "source_songs"
    source_dir.mkdir(parents=True)
    mix_wav = str(source_dir / "song_mix.wav")
    monkeypatch.setattr(cli_runner, "PROJECT_ROOT", str(project_root))
    create_test_wav(mix_wav, duration_sec=2.0)

    # 1. analyze_audio
    meta = run_action("analyze_audio", {"audio_path": mix_wav})
    assert "bpm" in meta
    assert "musical_key" in meta

    # 2. separate_stems
    sep = run_action("separate_stems", {
        "audio_path": mix_wav,
        "apply_bleed_gate": True,
        "split_guitar_substems": True,
        "split_vocal_substems": True,
        "split_orchestral_substems": True,
    })
    assert sep["status"] == "partial"  # requested DSP sub-stems remain explicitly experimental
    assert "stems" in sep
    assert "vocals" in sep["stems"]
    assert "guitar" in sep["stems"]
    assert sep["model_metadata"]["verification_status"] == "verified_pretrained"


def test_cli_runner_mashup_and_mixing(tmp_path):
    base_wav = str(tmp_path / "base.wav")
    donor_wav = str(tmp_path / "donor.wav")
    mash_out = str(tmp_path / "mashup.wav")
    master_out = str(tmp_path / "master.wav")

    create_test_wav(base_wav, duration_sec=3.0)
    create_test_wav(donor_wav, duration_sec=3.0)

    # 1. mashup
    mash = run_action("mashup", {
        "base_stem_path": base_wav,
        "donor_stem_path": donor_wav,
        "base_replace_start": 0.5,
        "base_replace_end": 1.5,
        "donor_extract_start": 0.0,
        "donor_extract_end": 1.0,
        "output_path": mash_out,
    })
    assert mash["status"] == "success"
    assert os.path.exists(mash_out)

    # 2. mix_master
    mix = run_action("mix_master", {
        "stem_paths": {"guitar": base_wav, "drums": donor_wav},
        "genre_profile": "metalcore",
        "target_lufs": -10.0,
        "output_master_path": master_out,
        "auto_use_detected_vst3": True,
    })
    assert mix["status"] == "success"
    assert os.path.exists(master_out)


def test_cli_runner_daw_projects_and_capcut(tmp_path):
    g_wav = str(tmp_path / "guitar_rhythm.wav")
    b_wav = str(tmp_path / "bass.wav")
    d_wav = str(tmp_path / "drums.wav")
    create_test_wav(g_wav, duration_sec=2.0)
    create_test_wav(b_wav, duration_sec=2.0)
    create_test_wav(d_wav, duration_sec=2.0)

    stems = {"guitar_rhythm": g_wav, "bass": b_wav, "drums": d_wav}

    # 1. create_reaper_rpp
    rpp_path = str(tmp_path / "test_session.rpp")
    rpp_res = run_action("create_reaper_rpp", {
        "project_name": "Studio_UI_Reaper",
        "bpm": 140.0,
        "stem_paths": stems,
        "include_vsti_midi_tracks": True,
        "output_rpp_path": rpp_path,
    })
    assert rpp_res["status"] == "success"
    assert os.path.exists(rpp_path)
    assert rpp_res["folder_buses_count"] == 2

    # 2. create_ableton
    ableton_res = run_action("create_ableton", {
        "project_name": "Studio_UI_Ableton",
        "bpm": 140.0,
        "musical_key": "C Minor",
        "stem_paths": stems,
        "output_dir": str(tmp_path),
    })
    assert ableton_res["status"] == "success"
    assert os.path.exists(ableton_res["manifest_path"])

    # 3. classify_footage
    footage_dir = str(tmp_path / "footage")
    os.makedirs(footage_dir, exist_ok=True)
    f_res = run_action("classify_footage", {"footage_dir": footage_dir})
    assert f_res["total_clips"] == 0


def test_cli_runner_subcommand_via_subprocess():
    # Test that running cli_runner.py from command line outputs valid JSON
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cmd = [
        sys.executable,
        os.path.join(repo_root, "servers", "cli_runner.py"),
        "scan_vst3",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "success"
    assert "total_plugins_found" in data
