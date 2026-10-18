import os
import json
import pytest
import numpy as np
import soundfile as sf

from servers.daw_studio_mcp.vst3_manager import (
    scan_installed_vst3_plugins,
    inspect_vst3_parameters,
    build_flagship_role_chain,
    apply_vst3_chain_to_audio,
)
from servers.daw_studio_mcp.mix_master_engine import auto_mix_and_master_stems
from servers.daw_studio_mcp.daw_bridge import (
    generate_reaper_project_rpp,
    export_ableton_als_session_manifest,
)
from shared_schemas.sync_map_schema import InstrumentEvent, SongSyncMap


def test_vst3_scanner_and_role_chains():
    reg = scan_installed_vst3_plugins()
    assert reg["status"] == "success"
    assert "category_a_mastering_and_surgical" in reg
    assert "category_b_vocals_and_reverb" in reg
    assert "category_c_guitar_and_bass" in reg
    assert "category_d_virtual_instruments" in reg

    # Validate all 10 roles build complete flagship chains
    all_roles = [
        "vocal_lead",
        "vocal_co_lead",
        "vocal_backing",
        "guitar_rhythm",
        "guitar_lead",
        "guitar_additional",
        "bass",
        "drums",
        "orchestra",
        "master_bus",
    ]

    for role in all_roles:
        chain = build_flagship_role_chain(role, reg)
        assert len(chain) >= 2, f"Chain for {role} should have at least 2 plugins"
        for item in chain:
            assert "plugin_name" in item
            assert "category" in item
            assert "active" in item
            assert item["active"] is True


def test_inspect_vst3_parameters_graceful():
    # Test on a real or mock path
    res = inspect_vst3_parameters("C:/NonExistent/Plugin.vst3")
    assert res["status"] == "error"
    assert res["is_instrument"] is False

    reg = scan_installed_vst3_plugins()
    # If any VST3 is installed on system, test inspection on it
    if reg["total_plugins_found"] > 0:
        sample_path = next(iter(reg["all_plugins"].values()))
        inspect_res = inspect_vst3_parameters(sample_path)
        assert inspect_res["status"] in ("success", "partial")


def test_auto_mix_and_master_with_vst3(tmp_path):
    output_master = str(tmp_path / "master_vst3.wav")
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)

    g_wav = str(tmp_path / "guitar_rhythm.wav")
    b_wav = str(tmp_path / "bass.wav")
    d_wav = str(tmp_path / "drums.wav")
    v_wav = str(tmp_path / "vocal_lead.wav")

    sf.write(g_wav, (0.5 * np.sin(2 * np.pi * 130.81 * t)), sr)
    sf.write(b_wav, (0.6 * np.sin(2 * np.pi * 65.41 * t)), sr)
    d_audio = np.zeros_like(t)
    d_audio[:: sr // 2] = 0.8
    sf.write(d_wav, d_audio, sr)
    sf.write(v_wav, (0.6 * np.sin(2 * np.pi * 440.0 * t)), sr)

    stems = {
        "guitar_rhythm": g_wav,
        "bass": b_wav,
        "drums": d_wav,
        "vocal_lead": v_wav,
    }

    res = auto_mix_and_master_stems(
        stem_paths=stems,
        genre_profile="metalcore",
        target_lufs=-11.0,
        output_master_path=output_master,
        auto_use_detected_vst3=True,
    )

    assert res["status"] == "success"
    assert os.path.exists(output_master)
    assert "vst3_applied_per_stem" in res
    assert "master_vst3_applied" in res

    data, _ = sf.read(output_master)
    assert len(data) > 0
    assert not np.isnan(data).any()


def test_generate_reaper_project_rpp_with_vsti_and_buses(tmp_path):
    output_rpp = str(tmp_path / "test_session.rpp")
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)

    g_wav = str(tmp_path / "guitar_rhythm.wav")
    lead_wav = str(tmp_path / "guitar_lead.wav")
    b_wav = str(tmp_path / "bass.wav")
    d_wav = str(tmp_path / "drums.wav")
    v_wav = str(tmp_path / "vocal_lead.wav")
    v_co = str(tmp_path / "vocal_co_lead.wav")
    v_back = str(tmp_path / "vocal_backing.wav")
    sf.write(g_wav, (0.5 * np.sin(2 * np.pi * 130.81 * t)), sr)
    sf.write(lead_wav, (0.5 * np.sin(2 * np.pi * 659.25 * t)), sr)
    sf.write(b_wav, (0.6 * np.sin(2 * np.pi * 65.41 * t)), sr)
    sf.write(d_wav, (0.7 * np.sin(2 * np.pi * 100.0 * t)), sr)
    sf.write(v_wav, (0.6 * np.sin(2 * np.pi * 440.0 * t)), sr)
    sf.write(v_co, (0.5 * np.sin(2 * np.pi * 523.25 * t)), sr)
    sf.write(v_back, (0.4 * np.sin(2 * np.pi * 659.25 * t)), sr)

    stems = {
        "guitar_rhythm": g_wav,
        "guitar_lead": lead_wav,
        "bass": b_wav,
        "drums": d_wav,
        "vocal_lead": v_wav,
        "vocal_co_lead": v_co,
        "vocal_backing": v_back,
    }

    # Create dummy sync map
    sync_map_file = str(tmp_path / "sync_map.json")
    sync_map = SongSyncMap(
        project_name="Reaper_Metalcore",
        bpm=140.0,
        musical_key="C Minor",
        master_audio_path="master.wav",
        gp5_tab_path="tabs.gp5",
        events=[
            InstrumentEvent(
                start_time_sec=0.0,
                end_time_sec=1.0,
                duration_sec=1.0,
                instrument="guitar_rhythm",
                playing_state="palm_mute_chug",
                nano_banana_keyframe_prompt="Rhythm chug",
                veo_motion_prompt="Heavy downpicking",
                is_transient_peak=True,
            ),
            InstrumentEvent(
                start_time_sec=1.0,
                end_time_sec=2.0,
                duration_sec=1.0,
                instrument="drums",
                playing_state="heavy_breakdown_cymbal",
                drum_components=["china_cymbal", "kick"],
                nano_banana_keyframe_prompt="Breakdown smash",
                veo_motion_prompt="Slow motion crash",
                is_transient_peak=True,
            ),
        ],
    )
    with open(sync_map_file, "w", encoding="utf-8") as f:
        f.write(sync_map.model_dump_json(indent=2))

    res = generate_reaper_project_rpp(
        project_name="Reaper_Metalcore",
        bpm=140.0,
        time_signature="4/4",
        stem_paths=stems,
        sync_map_json_path=sync_map_file,
        include_vsti_midi_tracks=True,
        output_rpp_path=output_rpp,
    )

    assert res["status"] == "success"
    assert os.path.exists(output_rpp)
    assert res["folder_buses_count"] == 3

    # Read and inspect .rpp content
    with open(output_rpp, "r", encoding="utf-8") as f:
        rpp_text = f.read()

    # 1. Check REAPER project header and master track
    assert "<REAPER_PROJECT" in rpp_text
    assert "<MASTERTRACK" in rpp_text
    assert "TEMPO 140.000000 4 4" in rpp_text

    # Only create buses for stem groups that exist; this fixture has no orchestra/VSTi sources.
    assert 'NAME "VOCAL BUS"' in rpp_text
    assert 'NAME "GUITAR BUS"' in rpp_text
    assert 'NAME "BASS & DRUM BUS"' in rpp_text

    # 3. Check GUITAR RE-TRACK track
    assert 'NAME "GUITAR RE-TRACK (Human DI -> Archetype Gojira X)"' in rpp_text
    assert "REC 1" in rpp_text

    # 4. Check VSTi tracks and MIDI items
    # VSTi tracks are emitted only when matching plugins and transcribed MIDI exist.
    assert ('NAME "VSTi Drums (Superior Drummer 3)"' in rpp_text) == ("<SOURCE MIDI" in rpp_text)

    # 5. Check Category A-D VST declarations
    assert "FabFilter" in rpp_text or "Pro-Q" in rpp_text
    assert "Ozone" in rpp_text or "soothe2" in rpp_text or "Valhalla" in rpp_text
    assert "MARKER" in rpp_text


def test_ableton_session_manifest(tmp_path):
    out_dir = str(tmp_path / "ableton_out")
    res = export_ableton_als_session_manifest(
        project_name="Ableton_Metalcore",
        bpm=140.0,
        musical_key="D Minor",
        stem_paths={"guitar_rhythm": "g.wav", "bass": "b.wav", "drums": "d.wav"},
        output_dir=out_dir,
    )

    assert res["status"] == "success"
    assert os.path.exists(res["manifest_path"])
    with open(res["manifest_path"], "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["project_name"] == "Ableton_Metalcore"
    assert manifest["bpm"] == 140.0
    assert len(manifest["groups"]) >= 3
