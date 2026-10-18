import json
import pytest
from shared_schemas.sync_map_schema import InstrumentEvent, SongSyncMap

def test_instrument_event_model():
    event = InstrumentEvent(
        start_time_sec=0.0,
        end_time_sec=1.5,
        duration_sec=1.5,
        instrument="guitar",
        playing_state="palm_mute_chug",
        tuning="Drop C",
        string_numbers=[6, 5, 4],
        fret_positions=[0, 0, 0],
        hand_box_anchor_fret=0,
        nano_banana_keyframe_prompt="Tight palm mute at fret 0",
        veo_motion_prompt="Heavy downpicking in sync with kick",
        is_transient_peak=True,
        recommended_capcut_fx="screen_shake"
    )
    assert event.instrument == "guitar"
    assert event.playing_state == "palm_mute_chug"
    assert event.duration_sec == 1.5
    assert event.is_transient_peak is True

def test_song_sync_map_validation():
    event = InstrumentEvent(
        start_time_sec=0.0,
        end_time_sec=2.0,
        duration_sec=2.0,
        instrument="drums",
        playing_state="heavy_breakdown_cymbal",
        drum_components=["kick_double", "china_cymbal"],
        nano_banana_keyframe_prompt="Drummer striking china cymbal",
        veo_motion_prompt="Explosive cymbal strike with double kick",
        is_transient_peak=True,
        recommended_capcut_fx="white_flash"
    )
    sync_map = SongSyncMap(
        project_name="Cybernetic_Breakdown",
        bpm=140.0,
        musical_key="C Minor",
        time_signature="4/4",
        master_audio_path="workspace/output_audio/master.wav",
        gp5_tab_path="workspace/output_tabs/song.gp5",
        events=[event]
    )

    # Serialize to JSON and parse back
    raw_json = sync_map.model_dump_json()
    parsed = SongSyncMap.model_validate_json(raw_json)
    assert parsed.project_name == "Cybernetic_Breakdown"
    assert len(parsed.events) == 1
    assert parsed.events[0].drum_components == ["kick_double", "china_cymbal"]
