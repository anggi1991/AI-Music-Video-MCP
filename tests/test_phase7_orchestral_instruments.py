import os
import json
import pytest
import numpy as np
import soundfile as sf
import guitarpro as gp
import cv2

from shared_schemas.sync_map_schema import InstrumentEvent, SongSyncMap
from servers.daw_studio_mcp.orchestra_decomposer import (
    detect_active_instruments_in_stem,
    decompose_orchestral_stem,
)
from servers.tab_transcriber_mcp.fretboard_solver import (
    get_bowed_instrument_tuning,
    classify_playing_state,
    viterbi_fretboard_solver,
)
from servers.tab_transcriber_mcp.server import transcribe_stems_to_gp5_and_sync_map
from servers.capcut_director_mcp.beat_cutter import (
    classify_footage_file,
    list_and_classify_footage,
)
from servers.capcut_director_mcp.server import assemble_capcut_music_video


def create_synthetic_orchestral_stem(filepath: str, duration_sec: float = 2.0, sr: int = 44100):
    """Generate synthetic orchestral audio with violin melody and cello bassline."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # Violin: high harmonic tone around 1200Hz with 6Hz vibrato
    vibrato = 1.0 + 0.03 * np.sin(2 * np.pi * 6.0 * t)
    violin_mono = 0.5 * np.sin(2 * np.pi * 1200.0 * vibrato * t) + 0.25 * np.sin(2 * np.pi * 2400.0 * t)
    violin_L = violin_mono * 0.85
    violin_R = violin_mono * 0.65

    # Cello: low-mid warm tone around 220Hz
    cello_mono = 0.6 * np.sin(2 * np.pi * 220.0 * t) + 0.3 * np.sin(2 * np.pi * 440.0 * t)
    cello_L = cello_mono * 0.7
    cello_R = cello_mono * 0.7

    stereo = np.column_stack([violin_L + cello_L, violin_R + cello_R])
    sf.write(filepath, stereo, sr, subtype="PCM_16")


def test_detect_active_instruments_and_decompose(tmp_path):
    orch_stem = str(tmp_path / "other_orchestra.wav")
    create_synthetic_orchestral_stem(orch_stem, duration_sec=2.0)

    # 1. Detection test
    detect_res = detect_active_instruments_in_stem(orch_stem, min_confidence=0.20)
    assert detect_res["is_silent"] is False
    active = [x["instrument"] for x in detect_res["active_instruments"]]
    assert len(active) > 0
    # Violin and/or cello should be detected
    assert "violin" in active or "cello" in active or "strings_ensemble" in active

    # 2. Decomposition test
    out_dir = str(tmp_path / "decomp_orch")
    decomp_res = decompose_orchestral_stem(orch_stem, out_dir, auto_detect_only=True)
    assert decomp_res["status"] == "success"
    assert len(decomp_res["exported_stems"]) > 0

    for inst, file_path in decomp_res["exported_stems"].items():
        assert os.path.exists(file_path)
        data, sr = sf.read(file_path)
        assert len(data) > 0
        assert not np.isnan(data).any()


def test_bowed_tunings_and_playing_states():
    # Violin tuning: [76, 69, 62, 55] (E5, A4, D4, G3)
    v_tun = get_bowed_instrument_tuning("violin")
    assert v_tun == [76, 69, 62, 55]

    # Cello tuning: [57, 50, 43, 36] (A3, D3, G2, C2)
    c_tun = get_bowed_instrument_tuning("cello")
    assert c_tun == [57, 50, 43, 36]

    # Legato vs Tremolo classification
    ev_legato = {"duration_sec": 0.60, "db": -20.0}
    state_l, _, _ = classify_playing_state(ev_legato, "violin")
    assert state_l == "bowed_legato"

    ev_trem = {"duration_sec": 0.08, "db": -18.0}
    state_t, is_trans, fx = classify_playing_state(ev_trem, "violin")
    assert state_t == "bowed_tremolo"
    assert is_trans is True

    # Brass & Choir
    ev_brass = {"duration_sec": 0.40, "db": -15.0}
    state_b, is_b_trans, _ = classify_playing_state(ev_brass, "brass")
    assert state_b == "brass_swell_blare"
    assert is_b_trans is True

    ev_choir = {"duration_sec": 0.80, "db": -16.0}
    state_c, _, _ = classify_playing_state(ev_choir, "choir")
    assert state_c == "choir_epic_chant"


def test_orchestral_gp5_and_sync_map(tmp_path):
    output_dir = str(tmp_path / "orch_tabs")
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    g_wav = str(tmp_path / "guitar.wav")
    b_wav = str(tmp_path / "bass.wav")
    d_wav = str(tmp_path / "drums.wav")
    violin_wav = str(tmp_path / "violin.wav")
    cello_wav = str(tmp_path / "cello.wav")
    brass_wav = str(tmp_path / "brass.wav")

    sf.write(g_wav, (0.5 * np.sin(2 * np.pi * 130.81 * t)), sr)
    sf.write(b_wav, (0.6 * np.sin(2 * np.pi * 65.41 * t)), sr)
    d_audio = np.zeros_like(t)
    d_audio[:: sr // 2] = 0.8
    sf.write(d_wav, d_audio, sr)
    sf.write(violin_wav, (0.5 * np.sin(2 * np.pi * 659.25 * t)), sr)  # E5
    sf.write(cello_wav, (0.6 * np.sin(2 * np.pi * 110.0 * t)), sr)    # A2
    sf.write(brass_wav, (0.4 * np.sin(2 * np.pi * 329.63 * t)), sr)   # E4

    res = transcribe_stems_to_gp5_and_sync_map(
        project_name="Symphonic_Metal_Opus",
        bpm=135.0,
        musical_key="E Minor",
        guitar_stem=g_wav,
        bass_stem=b_wav,
        drum_stem=d_wav,
        extra_instrument_stems={
            "violin": violin_wav,
            "cello": cello_wav,
            "brass": brass_wav,
        },
        output_dir=output_dir,
    )

    assert res["status"] == "success"
    assert os.path.exists(res["gp5_path"])
    assert os.path.exists(res["sync_map_path"])

    # Check that tracks exist in GP5
    parsed_gp5 = gp.parse(res["gp5_path"])
    track_names = [t.name for t in parsed_gp5.tracks]
    assert "Violin" in track_names
    assert "Cello" in track_names
    assert "Brass" in track_names

    # Check GM Programs: Violin is 40, Cello is 42
    for t_obj in parsed_gp5.tracks:
        if t_obj.name == "Violin":
            assert t_obj.channel.instrument == 40
        elif t_obj.name == "Cello":
            assert t_obj.channel.instrument == 42

    # Check sync map has orchestral events with bowing prompts
    with open(res["sync_map_path"], "r", encoding="utf-8") as f:
        sync_map = json.load(f)

    inst_in_map = [e["instrument"] for e in sync_map["events"]]
    assert "violin" in inst_in_map
    assert "cello" in inst_in_map
    assert "brass" in inst_in_map

    for ev in sync_map["events"]:
        if ev["instrument"] == "violin":
            assert "bow" in ev["nano_banana_keyframe_prompt"].lower() or "violin" in ev["nano_banana_keyframe_prompt"].lower()


def test_capcut_orchestral_classification_and_assembly(tmp_path):
    footage_dir = str(tmp_path / "footage")
    os.makedirs(footage_dir, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    def make_video(path):
        out = cv2.VideoWriter(path, fourcc, 30.0, (160, 120))
        for _ in range(30):
            frame = np.zeros((120, 160, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

    v_vid = os.path.join(footage_dir, "violin_solo_01.mp4")
    c_vid = os.path.join(footage_dir, "cello_performance_01.mp4")
    b_vid = os.path.join(footage_dir, "brass_section_01.mp4")
    make_video(v_vid)
    make_video(c_vid)
    make_video(b_vid)

    assert classify_footage_file("violin_solo_01.mp4")["instrument"] == "violin"
    assert classify_footage_file("cello_performance_01.mp4")["instrument"] == "cello"
    assert classify_footage_file("brass_section_01.mp4")["instrument"] == "brass"

    footage_list = list_and_classify_footage(footage_dir)
    assert len(footage_list["classified_by_instrument"]["violin"]) >= 1
    assert len(footage_list["classified_by_instrument"]["cello"]) >= 1

    # CapCut assembly with orchestral sync map
    audio_wav = str(tmp_path / "master.wav")
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    sf.write(audio_wav, 0.5 * np.sin(2 * np.pi * 440.0 * t), sr)

    events = [
        InstrumentEvent(
            start_time_sec=0.0,
            end_time_sec=1.0,
            duration_sec=1.0,
            instrument="violin",
            playing_state="bowed_legato",
            nano_banana_keyframe_prompt="Violin solo",
            veo_motion_prompt="Sweeping camera",
            is_transient_peak=False,
            recommended_capcut_fx="none",
        ),
        InstrumentEvent(
            start_time_sec=1.0,
            end_time_sec=2.0,
            duration_sec=1.0,
            instrument="cello",
            playing_state="bowed_legato",
            nano_banana_keyframe_prompt="Cello low melody",
            veo_motion_prompt="Low angle dolly",
            is_transient_peak=True,
            recommended_capcut_fx="hard_zoom",
        ),
    ]

    sync_map = SongSyncMap(
        project_name="Orchestra_CapCut",
        bpm=130.0,
        musical_key="G Major",
        master_audio_path=audio_wav,
        gp5_tab_path="output.gp5",
        events=events,
    )
    sync_map_file = str(tmp_path / "sync_map.json")
    with open(sync_map_file, "w", encoding="utf-8") as f:
        f.write(sync_map.model_dump_json(indent=2))

    drafts_root = str(tmp_path / "drafts")
    res = assemble_capcut_music_video(
        draft_name="Orchestra_Video_Draft",
        sync_map_json_path=sync_map_file,
        footage_dir=footage_dir,
        capcut_drafts_root=drafts_root,
    )

    assert res["status"] == "success"
    assert res["video_segments_placed"] >= 2
    assert os.path.exists(res["draft_content_json"])
