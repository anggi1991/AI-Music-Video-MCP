import os
import json
import pytest
import cv2
import numpy as np
import soundfile as sf

from shared_schemas.sync_map_schema import InstrumentEvent, SongSyncMap
from servers.capcut_director_mcp.draft_manager import (
    resolve_capcut_draft_root,
    initialize_capcut_draft,
    finalize_and_save_draft,
)
from servers.capcut_director_mcp.beat_cutter import (
    calculate_speed_multiplier,
    classify_footage_file,
    list_and_classify_footage,
)
from servers.capcut_director_mcp.fx_injector import inject_breakdown_fx
from servers.capcut_director_mcp.server import assemble_capcut_music_video


def create_dummy_mp4(filepath: str, duration_sec: float = 2.0, fps: float = 30.0):
    """Create a lightweight synthetic MP4 video file with OpenCV."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(filepath, fourcc, fps, (320, 240))
    total_frames = int(duration_sec * fps)
    for i in range(total_frames):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Add visual movement across frames for optical flow
        x_pos = int((i * 10) % 300)
        cv2.rectangle(frame, (x_pos, 50), (x_pos + 40, 150), (255, 255, 255), -1)
        out.write(frame)
    out.release()


def test_speed_multiplier_math():
    # Song 140, Clip 120 -> 140 / 120 = 1.1667 (in range)
    assert calculate_speed_multiplier(140.0, 120.0) == pytest.approx(1.1667, rel=0.01)
    # Clamp maximum: 200 / 100 = 2.0 -> clamped to 1.50
    assert calculate_speed_multiplier(200.0, 100.0) == 1.50
    # Clamp minimum: 60 / 120 = 0.50 -> clamped to 0.75
    assert calculate_speed_multiplier(60.0, 120.0) == 0.75


def test_footage_file_classification():
    assert classify_footage_file("guitar_chug_01.mp4") == {
        "instrument": "guitar",
        "playing_state": "palm_mute_chug",
    }
    assert classify_footage_file("drums_breakdown_cymbal_02.mp4") == {
        "instrument": "drums",
        "playing_state": "heavy_breakdown_cymbal",
    }
    assert classify_footage_file("bass_groove_01.mp4") == {
        "instrument": "bass",
        "playing_state": "palm_mute_chug",
    }
    assert classify_footage_file("synth_arpeggio_01.mp4") == {
        "instrument": "keyboard",
        "playing_state": "sustained_pad",
    }
    assert classify_footage_file("broll_cyberpunk_01.mp4") == {
        "instrument": "broll",
        "playing_state": "idle",
    }


def test_list_and_classify_footage(tmp_path):
    footage_dir = str(tmp_path / "veo_footage")
    os.makedirs(footage_dir, exist_ok=True)

    g_clip = os.path.join(footage_dir, "guitar_chug_01.mp4")
    d_clip = os.path.join(footage_dir, "drums_breakdown_01.mp4")
    create_dummy_mp4(g_clip, duration_sec=1.5)
    create_dummy_mp4(d_clip, duration_sec=1.5)

    res = list_and_classify_footage(footage_dir)
    assert res["total_clips"] == 2
    assert len(res["classified_by_instrument"]["guitar"]) == 1
    assert len(res["classified_by_instrument"]["drums"]) == 1
    assert res["clips"][0]["fps"] > 0
    assert res["clips"][0]["duration_sec"] > 0


def test_assemble_capcut_music_video(tmp_path):
    drafts_root = str(tmp_path / "capcut_drafts")
    footage_dir = str(tmp_path / "veo_footage")
    os.makedirs(drafts_root, exist_ok=True)
    os.makedirs(footage_dir, exist_ok=True)

    # 1. Create synthetic clips
    g_clip = os.path.join(footage_dir, "guitar_chug_01.mp4")
    d_clip = os.path.join(footage_dir, "drums_breakdown_01.mp4")
    b_clip = os.path.join(footage_dir, "broll_stage_01.mp4")
    create_dummy_mp4(g_clip, duration_sec=2.0)
    create_dummy_mp4(d_clip, duration_sec=2.0)
    create_dummy_mp4(b_clip, duration_sec=2.0)

    # 2. Create synthetic audio
    audio_wav = str(tmp_path / "master.wav")
    sr = 44100
    t = np.linspace(0, 3.0, sr * 3, endpoint=False)
    sf.write(audio_wav, 0.5 * np.sin(2 * np.pi * 440.0 * t), sr)

    # 3. Create visual_sync_map.json
    events = [
        InstrumentEvent(
            start_time_sec=0.0,
            end_time_sec=1.0,
            duration_sec=1.0,
            instrument="guitar",
            playing_state="palm_mute_chug",
            tuning="Drop C",
            string_numbers=[6, 5, 4],
            fret_positions=[0, 0, 0],
            hand_box_anchor_fret=0,
            nano_banana_keyframe_prompt="Tight guitar chug at fret 0",
            veo_motion_prompt="Violent downpicking at 140 BPM",
            is_transient_peak=True,
            recommended_capcut_fx="screen_shake",
        ),
        InstrumentEvent(
            start_time_sec=1.0,
            end_time_sec=2.0,
            duration_sec=1.0,
            instrument="drums",
            playing_state="heavy_breakdown_cymbal",
            tuning="Drop C",
            drum_components=["kick_double", "china_cymbal"],
            nano_banana_keyframe_prompt="Heavy china cymbal strike",
            veo_motion_prompt="Slow motion breakdown cymbal smash",
            is_transient_peak=True,
            recommended_capcut_fx="hard_zoom",
        ),
    ]

    sync_map = SongSyncMap(
        project_name="Cybernetic_Warfare",
        bpm=140.0,
        musical_key="C Minor",
        master_audio_path=audio_wav,
        gp5_tab_path="workspace/output_tabs/song.gp5",
        events=events,
    )
    sync_map_path = str(tmp_path / "visual_sync_map.json")
    with open(sync_map_path, "w", encoding="utf-8") as f:
        f.write(sync_map.model_dump_json(indent=2))

    # 4. Assemble CapCut Music Video
    result = assemble_capcut_music_video(
        draft_name="Cybernetic_Warfare_Draft",
        sync_map_json_path=sync_map_path,
        footage_dir=footage_dir,
        capcut_drafts_root=drafts_root,
    )

    assert result["status"] == "success"
    assert result["video_segments_placed"] >= 1
    assert result["fx_keyframes_injected"] > 0
    assert os.path.exists(result["draft_content_json"])
    assert os.path.exists(result["draft_info_json"])

    # 5. Parse generated draft_content.json and verify CapCut structure
    with open(result["draft_content_json"], "r", encoding="utf-8") as f:
        draft_content = json.load(f)

    assert "tracks" in draft_content
    assert len(draft_content["tracks"]) >= 2  # Audio track + Video track
    assert "materials" in draft_content
    assert len(draft_content["materials"]["videos"]) >= 1
