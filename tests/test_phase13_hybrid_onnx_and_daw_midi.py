import os
import json
import pytest
import numpy as np
import soundfile as sf
import music21
import guitarpro as gp

from servers.tab_transcriber_mcp.pre_cleaner import pre_clean_stem_audio, build_cleaning_board
from servers.tab_transcriber_mcp.pitch_tracker import track_pitches_onnx, analyze_stem_pitches
from servers.tab_transcriber_mcp.daw_midi_importer import import_verified_daw_midi
from servers.daw_studio_mcp.daw_bridge import generate_reaper_project_rpp
from servers.cli_runner import run_action


def test_pre_clean_stem_audio():
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    # Combined signal: 40 Hz (sub-rumble), 440 Hz (guitar A4), 10000 Hz (cymbal hiss)
    sub = 0.5 * np.sin(2 * np.pi * 40.0 * t)
    mid = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    high = 0.5 * np.sin(2 * np.pi * 10000.0 * t)
    signal = (sub + mid + high).astype(np.float32)

    cleaned = pre_clean_stem_audio(signal, sr, instrument="guitar")
    assert cleaned.shape == signal.shape
    # Mid-frequency should remain preserved while sub-rumble and high hiss are attenuated
    assert np.max(np.abs(cleaned)) > 0.1


def test_track_pitches_onnx_accuracy():
    sr = 22050
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    # E5 power chord: E2 (40) and B2 (47)
    e2 = 0.3 * np.sin(2 * np.pi * 82.41 * t)
    b2 = 0.3 * np.sin(2 * np.pi * 123.47 * t)
    chord_sig = (e2 + b2).astype(np.float32)

    events = track_pitches_onnx(chord_sig, sr, instrument="guitar")
    assert len(events) > 0
    # The neural model should identify MIDI notes in octave 2 (40 / 47)
    all_midi = [m for ev in events for m in ev.get("midi_notes", [])]
    assert any(m in (40, 47) for m in all_midi)


def test_import_verified_daw_midi(tmp_path):
    output_dir = str(tmp_path / "tabs")
    midi_path = str(tmp_path / "daw_export.mid")

    # Build multi-track MIDI score representing DAW export (SD3 Tracker drums + Guitar)
    score = music21.stream.Score()
    p_guitar = music21.stream.Part(id="Guitar")
    p_guitar.partName = "Guitar Rhythm"
    p_guitar.append(music21.chord.Chord([40, 47, 52], quarterLength=1.0))
    score.append(p_guitar)

    p_drums = music21.stream.Part(id="Drums")
    p_drums.partName = "Drums"
    p_drums.append(music21.note.Note(36, quarterLength=1.0)) # Kick
    score.append(p_drums)

    score.write("midi", midi_path)

    res = import_verified_daw_midi(
        project_name="DAW_Hybrid_Test",
        midi_path=midi_path,
        tuning_name="Standard E",
        bpm=120.0,
        musical_key="E Minor",
        output_dir=output_dir,
    )

    assert res["status"] == "success"
    assert res["mode"] == "daw_midi_import"
    assert res["tuning"] == "Standard E"
    assert os.path.exists(res["gp5_path"])
    assert os.path.exists(res["musicxml_path"])
    assert os.path.exists(res["sync_map_path"])

    # Verify GP5 file parses and contains the track
    parsed_gp5 = gp.parse(res["gp5_path"])
    assert len(parsed_gp5.tracks) >= 1
    assert parsed_gp5.tempo == 120


def test_reaper_rpp_with_sd3_and_reatune(tmp_path):
    output_rpp = str(tmp_path / "reaper_routed.rpp")
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    dummy_wav = str(tmp_path / "audio.wav")
    sf.write(dummy_wav, 0.5 * np.sin(2 * np.pi * 440.0 * t), sr)

    stems = {
        "guitar_rhythm": dummy_wav,
        "guitar_lead": dummy_wav,
        "bass": dummy_wav,
        "drums": dummy_wav,
        "vocal_lead": dummy_wav,
    }

    res = generate_reaper_project_rpp(
        project_name="Reaper_Routing_Test",
        bpm=130.0,
        stem_paths=stems,
        output_rpp_path=output_rpp,
        auto_use_detected_vst3=True,
    )

    assert res["status"] == "success"
    assert os.path.exists(output_rpp)

    with open(output_rpp, "r", encoding="utf-8") as f:
        content = f.read()

    # ReaTune should be instantiated on melodic tracks
    assert "ReaTune" in content
    # Superior Drummer 3 should be on drums
    assert "Superior Drummer 3" in content
    # Neural DSP should be on guitar bus
    assert "Neural DSP" in content


def test_cli_runner_import_daw_midi(tmp_path):
    output_dir = str(tmp_path / "tabs_cli")
    midi_path = str(tmp_path / "cli_midi.mid")

    score = music21.stream.Score()
    p_g = music21.stream.Part(id="Guitar")
    p_g.partName = "Guitar Rhythm"
    p_g.append(music21.chord.Chord([40, 47, 52], quarterLength=1.0))
    score.append(p_g)
    score.write("midi", midi_path)

    res = run_action(
        "import_daw_midi",
        {
            "project_name": "CLI_MIDI_Test",
            "midi_path": midi_path,
            "tuning": "Standard E",
            "bpm": 128.0,
            "musical_key": "E Minor",
            "output_dir": output_dir,
        },
    )

    assert res["status"] == "success"
    assert os.path.exists(res["gp5_path"])
    assert res["tuning"] == "Standard E"
