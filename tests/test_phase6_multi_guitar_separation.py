import os
import json
import pytest
import numpy as np
import soundfile as sf
import guitarpro as gp
import cv2

from shared_schemas.sync_map_schema import InstrumentEvent, SongSyncMap
from servers.daw_studio_mcp.guitar_decomposer import decompose_guitar_stem
from servers.daw_studio_mcp.stem_separator import (
    separate_audio_6stems,
    apply_anti_bleed_gate,
)
from servers.tab_transcriber_mcp.server import transcribe_stems_to_gp5_and_sync_map
from servers.capcut_director_mcp.beat_cutter import (
    classify_footage_file,
    list_and_classify_footage,
)
from servers.capcut_director_mcp.server import assemble_capcut_music_video


def create_synthetic_composite_guitar(filepath: str, duration_sec: float = 2.0, sr: int = 44100):
    """Generate a stereo guitar audio file containing rhythm chugs, lead melody, and ambient shimmer."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # 1. Rhythm chugs (Low frequency 110Hz-220Hz, side-panned / out of phase)
    rhythm_mono = 0.5 * np.sin(2 * np.pi * 110.0 * t) + 0.3 * np.sin(2 * np.pi * 165.0 * t)
    # Pulses
    rhythm_mono *= (0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * t))
    rhythm_L = rhythm_mono * 0.9
    rhythm_R = -rhythm_mono * 0.7  # heavy side energy

    # 2. Lead melody (Mid frequency 880Hz-1320Hz, centered / in-phase)
    lead_mono = 0.4 * np.sin(2 * np.pi * 880.0 * t) + 0.2 * np.sin(2 * np.pi * 1320.0 * t)
    lead_L = lead_mono * 0.8
    lead_R = lead_mono * 0.8  # centered

    # 3. Additional shimmer (> 3000Hz, light stereo)
    shimmer_L = 0.15 * np.sin(2 * np.pi * 3500.0 * t)
    shimmer_R = 0.15 * np.sin(2 * np.pi * 4200.0 * t)

    stereo_L = rhythm_L + lead_L + shimmer_L
    stereo_R = rhythm_R + lead_R + shimmer_R

    audio_stereo = np.column_stack([stereo_L, stereo_R])
    sf.write(filepath, audio_stereo, sr, subtype="PCM_16")


def test_guitar_decomposer_3way(tmp_path):
    output_dir = str(tmp_path / "guitar_substems")
    guitar_wav = str(tmp_path / "composite_guitar.wav")
    create_synthetic_composite_guitar(guitar_wav, duration_sec=2.0)

    res = decompose_guitar_stem(guitar_wav, output_dir)

    assert res["status"] == "success"
    assert os.path.exists(res["guitar_rhythm_path"])
    assert os.path.exists(res["guitar_lead_path"])
    assert os.path.exists(res["guitar_additional_path"])

    # Verify all 3 sub-stems are non-empty and non-NaN
    rhythm, sr_r = sf.read(res["guitar_rhythm_path"])
    lead, sr_l = sf.read(res["guitar_lead_path"])
    add, sr_a = sf.read(res["guitar_additional_path"])

    assert len(rhythm) > 0 and not np.isnan(rhythm).any()
    assert len(lead) > 0 and not np.isnan(lead).any()
    assert len(add) > 0 and not np.isnan(add).any()

    # Energy distribution check
    dist = res["energy_distribution"]
    assert "rhythm_percent" in dist
    assert "lead_percent" in dist
    assert "additional_percent" in dist
    assert dist["rhythm_percent"] > 0
    assert dist["lead_percent"] > 0


def test_stem_separator_6stems_with_anti_bleed(tmp_path):
    output_dir = str(tmp_path / "separated_6stems")
    mix_wav = str(tmp_path / "full_song_mix.wav")
    create_synthetic_composite_guitar(mix_wav, duration_sec=2.0)

    res = separate_audio_6stems(
        audio_path=mix_wav,
        output_dir=output_dir,
        apply_bleed_gate=True,
        split_guitar_substems=True,
    )

    assert res["status"] == "partial"  # requested heuristic 3-way masks are not source separation
    # Check 6 stems exist
    for stem_name in ["vocals", "drums", "bass", "guitar", "piano", "other"]:
        assert stem_name in res["stems"]
        assert os.path.exists(res["stems"][stem_name])

    # Check guitar sub-stems exist
    assert "guitar_substems" in res
    sub = res["guitar_substems"]
    assert os.path.exists(sub["guitar_rhythm"])
    assert os.path.exists(sub["guitar_lead"])
    assert os.path.exists(sub["guitar_additional"])


def test_multi_guitar_tab_transcription(tmp_path):
    output_dir = str(tmp_path / "multi_guitar_tabs")
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    g_rhythm = str(tmp_path / "g_rhythm.wav")
    g_lead = str(tmp_path / "g_lead.wav")
    g_add = str(tmp_path / "g_add.wav")
    b_wav = str(tmp_path / "bass.wav")
    d_wav = str(tmp_path / "drums.wav")
    s_wav = str(tmp_path / "synth.wav")

    # Rhythm: low C3 (130.81Hz)
    sf.write(g_rhythm, (0.5 * np.sin(2 * np.pi * 130.81 * t)), sr)
    # Lead: high C5 (523.25Hz)
    sf.write(g_lead, (0.4 * np.sin(2 * np.pi * 523.25 * t)), sr)
    # Additional: clean harmonics (659.25Hz)
    sf.write(g_add, (0.3 * np.sin(2 * np.pi * 659.25 * t)), sr)
    # Bass: 65.41 Hz
    sf.write(b_wav, (0.6 * np.sin(2 * np.pi * 65.41 * t)), sr)
    # Drums: click pulses
    d_audio = np.zeros_like(t)
    d_audio[:: sr // 2] = 0.8
    sf.write(d_wav, d_audio, sr)
    # Synth: 261.63 Hz
    sf.write(s_wav, (0.4 * np.sin(2 * np.pi * 261.63 * t)), sr)

    res = transcribe_stems_to_gp5_and_sync_map(
        project_name="Multi_Guitar_Extravaganza",
        bpm=140.0,
        musical_key="C Minor",
        guitar_rhythm_stem=g_rhythm,
        guitar_lead_stem=g_lead,
        guitar_additional_stem=g_add,
        bass_stem=b_wav,
        drum_stem=d_wav,
        synth_stem=s_wav,
        output_dir=output_dir,
    )

    assert res["status"] == "success"
    assert res["multi_guitar_enabled"] is True
    assert os.path.exists(res["gp5_path"])
    assert os.path.exists(res["sync_map_path"])

    # Verify GP5 has 6 tracks
    parsed_gp5 = gp.parse(res["gp5_path"])
    assert len(parsed_gp5.tracks) == 6
    track_names = [t.name for t in parsed_gp5.tracks]
    assert "Rhythm Guitar" in track_names
    assert "Lead Guitar" in track_names
    assert "Additional Guitar" in track_names
    assert "Electric Bass" in track_names
    assert "Drums" in track_names
    assert "Keyboard/Synth" in track_names

    # Verify visual_sync_map.json has specific multi-guitar events and prompts
    with open(res["sync_map_path"], "r", encoding="utf-8") as f:
        data = json.load(f)
    sync_map = SongSyncMap.model_validate(data)

    instruments_in_map = {e.instrument for e in sync_map.events}
    assert "guitar_rhythm" in instruments_in_map
    assert "guitar_lead" in instruments_in_map

    # Check that prompts differentiate rhythm and lead
    for ev in sync_map.events:
        if ev.instrument == "guitar_rhythm":
            assert "rhythm" in ev.nano_banana_keyframe_prompt.lower() or "chug" in ev.nano_banana_keyframe_prompt.lower()
        elif ev.instrument == "guitar_lead":
            assert "lead" in ev.nano_banana_keyframe_prompt.lower() or "solo" in ev.nano_banana_keyframe_prompt.lower()


def test_capcut_multi_guitar_classification_and_assembly(tmp_path):
    footage_dir = str(tmp_path / "footage")
    os.makedirs(footage_dir, exist_ok=True)

    # Helper for dummy mp4
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    def make_video(path):
        out = cv2.VideoWriter(path, fourcc, 30.0, (160, 120))
        for _ in range(30):
            frame = np.zeros((120, 160, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

    rhythm_vid = os.path.join(footage_dir, "guitar_rhythm_chug_01.mp4")
    lead_vid = os.path.join(footage_dir, "guitar_lead_solo_01.mp4")
    drum_vid = os.path.join(footage_dir, "drums_breakdown_01.mp4")
    make_video(rhythm_vid)
    make_video(lead_vid)
    make_video(drum_vid)

    # Test classification
    c_rhythm = classify_footage_file("guitar_rhythm_chug_01.mp4")
    assert c_rhythm["instrument"] == "guitar_rhythm"
    c_lead = classify_footage_file("guitar_lead_solo_01.mp4")
    assert c_lead["instrument"] == "guitar_lead"

    # Test listing
    footage_list = list_and_classify_footage(footage_dir)
    assert len(footage_list["classified_by_instrument"]["guitar_rhythm"]) >= 1
    assert len(footage_list["classified_by_instrument"]["guitar_lead"]) >= 1

    # Test CapCut assembly with multi-guitar sync map
    audio_wav = str(tmp_path / "master.wav")
    sr = 44100
    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    sf.write(audio_wav, 0.5 * np.sin(2 * np.pi * 440.0 * t), sr)

    events = [
        InstrumentEvent(
            start_time_sec=0.0,
            end_time_sec=1.0,
            duration_sec=1.0,
            instrument="guitar_rhythm",
            playing_state="palm_mute_chug",
            nano_banana_keyframe_prompt="Rhythm chug",
            veo_motion_prompt="Violent downpicking",
            is_transient_peak=True,
            recommended_capcut_fx="screen_shake",
        ),
        InstrumentEvent(
            start_time_sec=1.0,
            end_time_sec=2.0,
            duration_sec=1.0,
            instrument="guitar_lead",
            playing_state="lead_melody",
            nano_banana_keyframe_prompt="Melodic solo",
            veo_motion_prompt="High octave sweep",
            is_transient_peak=True,
            recommended_capcut_fx="hard_zoom",
        ),
    ]

    sync_map = SongSyncMap(
        project_name="MultiGuitar_CapCut",
        bpm=140.0,
        musical_key="D Minor",
        master_audio_path=audio_wav,
        gp5_tab_path="output.gp5",
        events=events,
    )
    sync_map_file = str(tmp_path / "sync_map.json")
    with open(sync_map_file, "w", encoding="utf-8") as f:
        f.write(sync_map.model_dump_json(indent=2))

    drafts_root = str(tmp_path / "drafts")
    res = assemble_capcut_music_video(
        draft_name="MultiGuitar_Video_Draft",
        sync_map_json_path=sync_map_file,
        footage_dir=footage_dir,
        capcut_drafts_root=drafts_root,
    )

    assert res["status"] == "success"
    assert res["video_segments_placed"] >= 2
    assert os.path.exists(res["draft_content_json"])
