import os
import gzip
import json
import xml.etree.ElementTree as ET
import soundfile as sf
import numpy as np
import pytest

from servers.daw_studio_mcp.daw_bridge import (
    find_ableton_executable,
    launch_ableton_project,
    generate_ableton_live_set_als,
    export_ableton_als_session_manifest,
)


def test_find_ableton_executable_runs_safely():
    exe = find_ableton_executable()
    # If installed on Windows system, it should find it or safely return None
    assert exe is None or isinstance(exe, str)
    if exe is not None:
        assert os.path.isfile(exe)


def test_launch_ableton_invalid_path():
    res = launch_ableton_project("non_existent_file.als")
    assert res is False


def test_generate_ableton_live_set_als(tmp_path):
    out_dir = str(tmp_path / "output_audio")
    os.makedirs(out_dir, exist_ok=True)

    # Create dummy stem WAVs
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), False)
    sig = 0.2 * np.sin(2 * np.pi * 440.0 * t)

    stems = {}
    for name in ["vocals", "guitar_lead", "bass", "drums"]:
        path = os.path.join(out_dir, f"{name}.wav")
        sf.write(path, sig, sr)
        stems[name] = path

    als_path = os.path.join(out_dir, "TestSong_session.als")
    res_path = generate_ableton_live_set_als(
        project_name="TestSong",
        bpm=145.0,
        stem_paths=stems,
        output_als_path=als_path,
    )

    assert os.path.isfile(res_path)
    assert os.path.getsize(res_path) > 1000

    # Verify uncompression & XML contents
    with gzip.open(res_path, "rb") as f:
        xml_content = f.read()

    root = ET.fromstring(xml_content)
    assert root.tag == "Ableton"
    ls = root.find("LiveSet")
    assert ls is not None

    # Check BPM
    main_track = ls.find("MainTrack")
    assert main_track is not None
    mixer = main_track.find("DeviceChain/Mixer")
    tempo = mixer.find("Tempo/Manual")
    assert float(tempo.attrib["Value"]) == 145.0

    # Check Tracks
    tracks = ls.find("Tracks")
    audio_tracks = tracks.findall("AudioTrack")
    assert len(audio_tracks) == 4

    track_names = [t.find("Name/EffectiveName").attrib["Value"] for t in audio_tracks]
    assert "Vocals" in track_names
    assert "Guitar Lead" in track_names
    assert "Bass" in track_names
    assert "Drums" in track_names

    # Check arrangement clips
    for t in audio_tracks:
        events = t.find("DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events")
        clips = events.findall("AudioClip")
        assert len(clips) == 1
        clip = clips[0]
        assert clip.find("IsWarped").attrib["Value"] == "false"
        assert float(clip.find("CurrentEnd").attrib["Value"]) > 0


def test_export_ableton_manifest_and_als_combined(tmp_path):
    out_dir = str(tmp_path / "combined_out")
    res = export_ableton_als_session_manifest(
        project_name="Metalcore_ALS_Test",
        bpm=135.0,
        musical_key="D Minor",
        stem_paths={"guitar_rhythm": "dummy_g.wav"},
        output_dir=out_dir,
        generate_als=True,
        launch_ableton=False,
    )

    assert res["status"] == "success"
    assert os.path.exists(res["manifest_path"])
    assert res["als_path"] is not None
    assert os.path.exists(res["als_path"])
    assert res["launched"] is False
    assert res["groups_count"] == 4

    # Verify manifest JSON integrity
    with open(res["manifest_path"], "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["project_name"] == "Metalcore_ALS_Test"
    assert manifest["bpm"] == 135.0
