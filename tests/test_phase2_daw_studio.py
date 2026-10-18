import os
import tempfile
import numpy as np
import soundfile as sf
import pytest

from servers.daw_studio_mcp.mashup_engine import (
    analyze_audio_metadata,
    mashup_replace_segment,
    calculate_pitch_shift,
)
from servers.daw_studio_mcp.mix_master_engine import auto_mix_and_master_stems


def create_synthetic_wav(
    filepath: str,
    duration_sec: float = 3.0,
    sr: int = 44100,
    freq: float = 440.0,
    bpm: float = 120.0,
):
    """Generate a rhythmic synthetic audio file with beat pulses and harmonic content."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # Harmonic tone
    tone = 0.4 * np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * (freq * 1.5) * t)

    # Add rhythmic pulses at given BPM
    beat_period = 60.0 / bpm
    pulse = np.zeros_like(t)
    num_beats = int(duration_sec / beat_period)
    for b in range(num_beats):
        idx = int(b * beat_period * sr)
        pulse_len = min(int(0.05 * sr), len(t) - idx)
        pulse[idx : idx + pulse_len] += 0.5 * np.hanning(pulse_len)

    audio = tone + pulse
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.8
    # Stereo
    stereo = np.column_stack([audio, audio])
    sf.write(filepath, stereo, sr)


def test_calculate_pitch_shift():
    # C (0) to G (7) -> (0 - 7) % 12 = 5 -> +5 semitones
    assert calculate_pitch_shift(0, 7) == 5
    # C (0) to D (2) -> (0 - 2) % 12 = 10 -> 10 - 12 = -2 semitones
    assert calculate_pitch_shift(0, 2) == -2
    # Same root -> 0 semitones
    assert calculate_pitch_shift(5, 5) == 0


def test_analyze_audio_metadata(tmp_path):
    test_wav = str(tmp_path / "test_120bpm.wav")
    create_synthetic_wav(test_wav, duration_sec=4.0, bpm=120.0, freq=261.63)  # C4

    meta = analyze_audio_metadata(test_wav)
    assert "bpm" in meta
    assert meta["duration_sec"] == pytest.approx(4.0, rel=0.1)
    assert "musical_key" in meta
    assert "integrated_lufs" in meta
    assert meta["onset_count"] > 0
    assert len(meta["onset_timestamps_sec"]) > 0


def test_mashup_replace_segment(tmp_path):
    base_wav = str(tmp_path / "base_stem.wav")
    donor_wav = str(tmp_path / "donor_stem.wav")
    output_wav = str(tmp_path / "merged_stem.wav")

    create_synthetic_wav(base_wav, duration_sec=4.0, bpm=120.0, freq=261.63)  # C4
    create_synthetic_wav(donor_wav, duration_sec=4.0, bpm=140.0, freq=329.63)  # E4

    result = mashup_replace_segment(
        base_stem_path=base_wav,
        donor_stem_path=donor_wav,
        base_replace_start=1.0,
        base_replace_end=2.5,
        donor_extract_start=0.5,
        donor_extract_end=2.0,
        output_path=output_wav,
    )

    assert result["status"] == "success"
    assert os.path.exists(output_wav)
    assert result["stretch_ratio"] > 0
    assert "pitch_semitones" in result

    # Check that output audio is valid
    data, sr = sf.read(output_wav)
    assert len(data) > 0
    assert not np.isnan(data).any()


def test_auto_mix_and_master_stems(tmp_path):
    guitar_wav = str(tmp_path / "guitar.wav")
    bass_wav = str(tmp_path / "bass.wav")
    drums_wav = str(tmp_path / "drums.wav")
    master_wav = str(tmp_path / "master.wav")

    create_synthetic_wav(guitar_wav, duration_sec=3.0, freq=330.0)
    create_synthetic_wav(bass_wav, duration_sec=3.0, freq=110.0)
    create_synthetic_wav(drums_wav, duration_sec=3.0, freq=60.0)

    stems = {
        "guitar": guitar_wav,
        "bass": bass_wav,
        "drums": drums_wav,
    }

    result = auto_mix_and_master_stems(
        stem_paths=stems,
        genre_profile="metalcore",
        target_lufs=-12.0,
        reference_track_path=None,
        output_master_path=master_wav,
    )

    assert result["status"] == "success"
    assert os.path.exists(master_wav)
    assert result["final_lufs"] == pytest.approx(-12.0, abs=2.5)

    # Check output wave
    master_data, sr = sf.read(master_wav)
    assert len(master_data) > 0
    assert not np.isnan(master_data).any()
    assert np.max(np.abs(master_data)) <= 1.0  # True peak limiter held
