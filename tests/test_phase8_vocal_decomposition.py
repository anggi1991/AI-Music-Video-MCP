import os
import json
import pytest
import numpy as np
import soundfile as sf
import guitarpro as gp
import cv2

from shared_schemas.sync_map_schema import InstrumentEvent, SongSyncMap
from servers.daw_studio_mcp.vocal_decomposer import (
    decompose_vocal_stem,
    apply_lip_sync_readiness_gate,
)
from servers.tab_transcriber_mcp.fretboard_solver import (
    classify_vocal_events,
    classify_playing_state,
)
from servers.tab_transcriber_mcp.server import transcribe_stems_to_gp5_and_sync_map
from servers.capcut_director_mcp.beat_cutter import (
    classify_footage_file,
    list_and_classify_footage,
)
from servers.capcut_director_mcp.server import assemble_capcut_music_video


def create_synthetic_vocal_composite(filepath: str, duration_sec: float = 2.0, sr: int = 44100):
    """Generate a stereo vocal mix containing center lead vocal, co-lead vocal, and side backing harmony."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # 1. Lead Vocal (Melodic 440Hz A4, center channel)
    lead_mono = 0.6 * np.sin(2 * np.pi * 440.0 * t) + 0.3 * np.sin(2 * np.pi * 880.0 * t)
    # Active between 0.0 and 1.2 sec, then silence
    lead_mono[int(1.2 * sr):] = 0.0
    lead_L = lead_mono * 0.8
    lead_R = lead_mono * 0.8

    # 2. Co-Lead Vocal (Scream/Roughness or counter-melody, active 1.2 to 2.0 sec)
    co_lead_mono = 0.5 * np.sin(2 * np.pi * 659.25 * t) + 0.2 * np.random.normal(0, 0.1, len(t))
    co_lead_mono[: int(1.2 * sr)] = 0.0
    co_lead_L = co_lead_mono * 0.75
    co_lead_R = co_lead_mono * 0.70

    # 3. Backing Vocal (Harmonies panned wide, side-heavy)
    backing_mono = 0.3 * np.sin(2 * np.pi * 554.37 * t)  # C#5
    backing_L = backing_mono * 0.8
    backing_R = -backing_mono * 0.8  # Side stereo

    stereo = np.column_stack([lead_L + co_lead_L + backing_L, lead_R + co_lead_R + backing_R])
    sf.write(filepath, stereo, sr, subtype="PCM_16")


def test_vocal_decomposer_3way(tmp_path):
    vocal_wav = str(tmp_path / "composite_vocals.wav")
    create_synthetic_vocal_composite(vocal_wav, duration_sec=2.0)
    out_dir = str(tmp_path / "decomp_vocals")

    res = decompose_vocal_stem(
        vocal_stem_path=vocal_wav,
        output_dir=out_dir,
        enable_lip_sync_gate=True,
        gate_threshold_db=-40.0,
    )

    assert res["status"] == "success"
    assert os.path.exists(res["vocal_lead_path"])
    assert os.path.exists(res["vocal_co_lead_path"])
    assert os.path.exists(res["vocal_backing_path"])

    # Check non-empty and non-NaN
    lead, sr_l = sf.read(res["vocal_lead_path"])
    co_lead, sr_c = sf.read(res["vocal_co_lead_path"])
    backing, sr_b = sf.read(res["vocal_backing_path"])

    assert len(lead) > 0 and not np.isnan(lead).any()
    assert len(co_lead) > 0 and not np.isnan(co_lead).any()
    assert len(backing) > 0 and not np.isnan(backing).any()

    # Energy distribution
    dist = res["energy_distribution"]
    assert "lead_percent" in dist
    assert "co_lead_percent" in dist
    assert "backing_percent" in dist
    assert dist["lead_percent"] > 0
    assert dist["backing_percent"] > 0


def test_vocal_style_classification():
    # Clean melodic
    ev_clean = {"duration_sec": 0.60, "db": -22.0, "rms": 0.1}
    st_clean, _, _ = classify_playing_state(ev_clean, "vocal_lead")
    assert st_clean == "vocal_clean_melodic"

    # Aggressive scream
    ev_scream = {"duration_sec": 0.50, "db": -14.0, "rms": 0.3}
    st_scream, is_trans, _ = classify_playing_state(ev_scream, "vocal_lead")
    assert st_scream == "vocal_aggressive_scream"
    assert is_trans is True

    # Rap flow
    ev_rap = {"duration_sec": 0.14, "db": -20.0, "rms": 0.15}
    st_rap, _, _ = classify_playing_state(ev_rap, "vocal_lead")
    assert st_rap == "vocal_rap_flow"

    # Spoken whisper
    ev_whisper = {"duration_sec": 0.40, "db": -38.0, "rms": 0.02}
    st_whisper, _, _ = classify_playing_state(ev_whisper, "vocal_lead")
    assert st_whisper == "vocal_spoken_whisper"

    # Backing vocal harmony vs gang shout
    ev_harm = {"duration_sec": 0.50, "db": -25.0, "rms": 0.08}
    st_harm, _, _ = classify_playing_state(ev_harm, "vocal_backing")
    assert st_harm == "vocal_backing_harmony"

    ev_shout = {"duration_sec": 0.18, "db": -16.0, "rms": 0.25}
    st_shout, is_shout_trans, _ = classify_playing_state(ev_shout, "vocal_backing")
    assert st_shout == "vocal_gang_shout"
    assert is_shout_trans is True


def test_multi_vocal_gp5_and_sync_map(tmp_path):
    output_dir = str(tmp_path / "vocal_tabs")
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    g_wav = str(tmp_path / "guitar.wav")
    v_lead = str(tmp_path / "vocal_lead.wav")
    v_co = str(tmp_path / "vocal_co_lead.wav")
    v_back = str(tmp_path / "vocal_backing.wav")

    sf.write(g_wav, (0.5 * np.sin(2 * np.pi * 130.81 * t)), sr)
    sf.write(v_lead, (0.6 * np.sin(2 * np.pi * 440.0 * t)), sr)  # A4
    sf.write(v_co, (0.5 * np.sin(2 * np.pi * 523.25 * t)), sr)   # C5
    sf.write(v_back, (0.4 * np.sin(2 * np.pi * 659.25 * t)), sr) # E5

    res = transcribe_stems_to_gp5_and_sync_map(
        project_name="Vocal_Mastery",
        bpm=128.0,
        musical_key="A Minor",
        guitar_stem=g_wav,
        vocal_lead_stem=v_lead,
        vocal_co_lead_stem=v_co,
        vocal_backing_stem=v_back,
        output_dir=output_dir,
    )

    assert res["status"] == "success"
    assert os.path.exists(res["gp5_path"])
    assert os.path.exists(res["sync_map_path"])

    # Check tracks exist in GP5
    parsed_gp5 = gp.parse(res["gp5_path"])
    track_names = [t.name for t in parsed_gp5.tracks]
    assert "Lead Vocals" in track_names
    assert "Co-Lead Vocals" in track_names
    assert "Backing Vocals" in track_names

    # Check GM Programs: Lead Vocals is 53, Co-Lead is 54, Backing is 52
    for t_obj in parsed_gp5.tracks:
        if t_obj.name == "Lead Vocals":
            assert t_obj.channel.instrument == 53
        elif t_obj.name == "Co-Lead Vocals":
            assert t_obj.channel.instrument == 54
        elif t_obj.name == "Backing Vocals":
            assert t_obj.channel.instrument == 52

    # Verify visual sync map prompts
    with open(res["sync_map_path"], "r", encoding="utf-8") as f:
        sync_map = json.load(f)

    vocal_events = [e for e in sync_map["events"] if "vocal" in e["instrument"]]
    assert len(vocal_events) > 0

    for ev in vocal_events:
        prompt = ev["nano_banana_keyframe_prompt"].lower()
        if ev["instrument"] == "vocal_lead":
            assert "lead" in prompt or "singer" in prompt or "frontman" in prompt or "vocalist" in prompt
        elif ev["instrument"] == "vocal_co_lead":
            assert "co-lead" in prompt or "secondary" in prompt
        elif ev["instrument"] == "vocal_backing":
            assert "backing" in prompt or "harmony" in prompt


def test_capcut_multi_vocal_assembly(tmp_path):
    footage_dir = str(tmp_path / "footage")
    os.makedirs(footage_dir, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    def make_video(path):
        out = cv2.VideoWriter(path, fourcc, 30.0, (160, 120))
        for _ in range(30):
            frame = np.zeros((120, 160, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

    lead_vid = os.path.join(footage_dir, "vocal_lead_frontman_01.mp4")
    co_vid = os.path.join(footage_dir, "vocal_co_lead_screamer_01.mp4")
    back_vid = os.path.join(footage_dir, "vocal_backing_harmony_01.mp4")
    make_video(lead_vid)
    make_video(co_vid)
    make_video(back_vid)

    assert classify_footage_file("vocal_lead_frontman_01.mp4")["instrument"] == "vocal_lead"
    assert classify_footage_file("vocal_co_lead_screamer_01.mp4")["instrument"] == "vocal_co_lead"
    assert classify_footage_file("vocal_backing_harmony_01.mp4")["instrument"] == "vocal_backing"

    footage_list = list_and_classify_footage(footage_dir)
    assert len(footage_list["classified_by_instrument"]["vocal_lead"]) >= 1
    assert len(footage_list["classified_by_instrument"]["vocal_co_lead"]) >= 1
    assert len(footage_list["classified_by_instrument"]["vocal_backing"]) >= 1

    # CapCut assembly with multi-vocal sync map
    audio_wav = str(tmp_path / "master.wav")
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    sf.write(audio_wav, 0.5 * np.sin(2 * np.pi * 440.0 * t), sr)

    events = [
        InstrumentEvent(
            start_time_sec=0.0,
            end_time_sec=1.0,
            duration_sec=1.0,
            instrument="vocal_lead",
            playing_state="vocal_clean_melodic",
            nano_banana_keyframe_prompt="Lead singer melodic hook",
            veo_motion_prompt="Push into lead vocalist",
            is_transient_peak=False,
            recommended_capcut_fx="none",
        ),
        InstrumentEvent(
            start_time_sec=1.0,
            end_time_sec=2.0,
            duration_sec=1.0,
            instrument="vocal_co_lead",
            playing_state="vocal_aggressive_scream",
            nano_banana_keyframe_prompt="Co-lead screamer explosion",
            veo_motion_prompt="Whip pan to co-lead",
            is_transient_peak=True,
            recommended_capcut_fx="white_flash",
        ),
    ]

    sync_map = SongSyncMap(
        project_name="Duet_CapCut",
        bpm=128.0,
        musical_key="A Minor",
        master_audio_path=audio_wav,
        gp5_tab_path="output.gp5",
        events=events,
    )
    sync_map_file = str(tmp_path / "sync_map.json")
    with open(sync_map_file, "w", encoding="utf-8") as f:
        f.write(sync_map.model_dump_json(indent=2))

    drafts_root = str(tmp_path / "drafts")
    res = assemble_capcut_music_video(
        draft_name="Duet_Video_Draft",
        sync_map_json_path=sync_map_file,
        footage_dir=footage_dir,
        capcut_drafts_root=drafts_root,
    )

    assert res["status"] == "success"
    assert res["video_segments_placed"] >= 2
    assert os.path.exists(res["draft_content_json"])
