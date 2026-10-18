import os
import json
import pytest
import numpy as np
import soundfile as sf
import guitarpro as gp

from shared_schemas.sync_map_schema import SongSyncMap
from servers.tab_transcriber_mcp.fretboard_solver import (
    detect_guitar_tuning,
    get_fret_candidates_for_chord,
    viterbi_fretboard_solver,
    classify_playing_state,
    TUNINGS,
)
from servers.tab_transcriber_mcp.gp5_exporter import export_gp5_and_musicxml
from servers.tab_transcriber_mcp.server import transcribe_stems_to_gp5_and_sync_map


def test_auto_tuning_detection():
    # Note <= 48 (C2) -> Drop C
    tuning_c, strings_c = detect_guitar_tuning(48)
    assert tuning_c == "Drop C"
    assert strings_c == [60, 55, 48, 43, 38, 36]

    # 48 < Note <= 50 (D2) -> Drop D
    tuning_d, strings_d = detect_guitar_tuning(50)
    assert tuning_d == "Drop D"
    assert strings_d == [62, 57, 50, 45, 40, 38]

    # Note > 50 -> Standard E
    tuning_e, strings_e = detect_guitar_tuning(52)
    assert tuning_e == "Standard E"
    assert strings_e == [64, 59, 55, 50, 45, 40]


def test_4_fret_hand_box_and_barre_chords():
    # Drop C tuning
    open_strings = TUNINGS["Drop C"]  # [60, 55, 48, 43, 38, 36]

    # Drop C power chord: root C2 (36), G2 (43), C3 (48) -> should produce 1-finger barre 0-0-0 on strings 6, 5, 4
    candidates = get_fret_candidates_for_chord([36, 43, 48], open_strings, tuning_name="Drop C")
    assert len(candidates) > 0
    barre = candidates[0]
    assert barre["is_barre"] is True
    assert barre["strings"] == [6, 5, 4]
    assert barre["frets"] == [0, 0, 0]

    # Power chord on fret 5: F2 (41), C3 (48), F3 (53) in Drop C -> frets 5-5-5
    candidates_5 = get_fret_candidates_for_chord([41, 48, 53], open_strings, tuning_name="Drop C")
    assert candidates_5[0]["is_barre"] is True
    assert candidates_5[0]["frets"] == [5, 5, 5]

    # Check 4-fret hand-box stretch constraint
    # Unnatural chord requiring frets 2 and 9 on non-open strings -> stretch = 7 (> 4) -> must be discarded
    single_candidates = get_fret_candidates_for_chord([42, 63], open_strings, tuning_name="Standard E")
    for cand in single_candidates:
        non_open = [f for f in cand["frets"] if f > 0]
        if non_open:
            assert max(non_open) - min(non_open) <= 4


def test_viterbi_fretboard_solver():
    open_strings = TUNINGS["Drop C"]
    events = [
        {"midi_notes": [36, 43, 48], "duration_sec": 0.2},  # Fret 0-0-0
        {"midi_notes": [36, 43, 48], "duration_sec": 0.2},  # Fret 0-0-0
        {"midi_notes": [39, 46, 51], "duration_sec": 0.2},  # Fret 3-3-3 (Eb)
        {"midi_notes": [41, 48, 53], "duration_sec": 0.5},  # Fret 5-5-5 (F)
    ]
    solved = viterbi_fretboard_solver(events, open_strings, tuning_name="Drop C")
    assert len(solved) == 4
    assert solved[0]["fret_positions"] == [0, 0, 0]
    assert solved[1]["fret_positions"] == [0, 0, 0]
    assert solved[2]["fret_positions"] == [3, 3, 3]
    assert solved[3]["fret_positions"] == [5, 5, 5]


def test_classify_playing_state():
    # Palm mute chug: short duration (< 0.25s), low string (6), low fret (0-3)
    ev_chug = {
        "duration_sec": 0.15,
        "string_numbers": [6, 5, 4],
        "fret_positions": [0, 0, 0],
        "db": -20.0,
    }
    state, is_trans, fx = classify_playing_state(ev_chug, "guitar")
    assert state == "palm_mute_chug"
    assert is_trans is True
    assert fx == "screen_shake"

    # Wide power chord: sustained (> 0.4s), 3+ strings
    ev_wide = {
        "duration_sec": 0.60,
        "string_numbers": [6, 5, 4],
        "fret_positions": [5, 5, 5],
        "db": -15.0,
    }
    state, is_trans, fx = classify_playing_state(ev_wide, "guitar")
    assert state == "wide_power_chord"
    assert is_trans is True
    assert fx == "hard_zoom"

    # Drum breakdown cymbal
    ev_drum = {
        "duration_sec": 0.3,
        "components": ["china_cymbal", "kick"],
        "db": -10.0,
    }
    state, is_trans, fx = classify_playing_state(ev_drum, "drums")
    assert state == "heavy_breakdown_cymbal"
    assert is_trans is True
    assert fx == "screen_shake"


def test_full_pipeline_transcribe(tmp_path):
    output_dir = str(tmp_path / "tabs")
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    # Synthetic stems
    g_wav = str(tmp_path / "g.wav")
    b_wav = str(tmp_path / "b.wav")
    d_wav = str(tmp_path / "d.wav")
    s_wav = str(tmp_path / "s.wav")

    # Guitar: 130.81 Hz (C3)
    sf.write(g_wav, (0.5 * np.sin(2 * np.pi * 130.81 * t)), sr)
    # Bass: 65.41 Hz (C2)
    sf.write(b_wav, (0.6 * np.sin(2 * np.pi * 65.41 * t)), sr)
    # Drums: click pulses
    d_audio = np.zeros_like(t)
    d_audio[:: sr // 2] = 0.8
    sf.write(d_wav, d_audio, sr)
    # Synth: 261.63 Hz (C4)
    sf.write(s_wav, (0.4 * np.sin(2 * np.pi * 261.63 * t)), sr)

    res = transcribe_stems_to_gp5_and_sync_map(
        project_name="Metalcore_Attack",
        bpm=140.0,
        musical_key="C Minor",
        guitar_stem=g_wav,
        bass_stem=b_wav,
        drum_stem=d_wav,
        synth_stem=s_wav,
        output_dir=output_dir,
    )

    assert res["status"] == "success"
    assert os.path.exists(res["gp5_path"])
    assert os.path.exists(res["musicxml_path"])
    assert os.path.exists(res["sync_map_path"])

    # Verify GP5 file can be parsed by guitarpro
    parsed_gp5 = gp.parse(res["gp5_path"])
    assert len(parsed_gp5.tracks) == 4
    assert parsed_gp5.tempo == 140

    # Verify visual_sync_map.json against Pydantic schema
    with open(res["sync_map_path"], "r", encoding="utf-8") as f:
        sync_map_data = json.load(f)
    validated = SongSyncMap.model_validate(sync_map_data)
    assert validated.project_name == "Metalcore_Attack"
    assert validated.bpm == 140.0
    assert len(validated.events) > 0
    # Check that prompts are populated
    for ev in validated.events:
        assert len(ev.nano_banana_keyframe_prompt) > 10
        assert len(ev.veo_motion_prompt) > 10
