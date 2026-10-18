import os

import pytest

from servers.daw_studio_mcp.model_registry import MODEL_REGISTRY, get_model_metadata
from servers.daw_studio_mcp.stem_separator import capture_cuda_telemetry
from servers.workspace_paths import project_stems_dir, resolve_source_song


def test_source_song_allowlist_is_confined_to_source_songs(tmp_path):
    workspace = tmp_path / "workspace"
    source_dir = workspace / "source_songs"
    source_dir.mkdir(parents=True)
    valid = source_dir / "my_song.wav"
    valid.write_bytes(b"source")
    (workspace / "input_stems").mkdir()
    stem = workspace / "input_stems" / "vocals.wav"
    stem.write_bytes(b"generated")

    assert resolve_source_song(str(tmp_path), str(valid)) == os.path.realpath(valid)
    with pytest.raises(ValueError, match="workspace/source_songs"):
        resolve_source_song(str(tmp_path), str(stem))


def test_source_song_allowlist_rejects_unsupported_extensions(tmp_path):
    source_dir = tmp_path / "workspace" / "source_songs"
    source_dir.mkdir(parents=True)
    unsupported = source_dir / "song.ogg"
    unsupported.write_bytes(b"audio")
    with pytest.raises(ValueError):
        resolve_source_song(str(tmp_path), str(unsupported))


def test_model_registry_has_honest_output_metadata():
    meta = get_model_metadata("htdemucs_6s")
    assert meta is not None
    assert set(meta) >= {"model_id", "task_type", "expected_output_labels", "license_info", "verification_status", "caveats"}
    assert set(meta["expected_output_labels"]) == {"vocals", "drums", "bass", "guitar", "piano", "other"}
    assert meta["verification_status"] == "verified_pretrained"
    assert any("not bleed-free" in note for note in meta["caveats"])
    meta["caveats"].append("mutated")
    assert "mutated" not in MODEL_REGISTRY["htdemucs_6s"]["caveats"]
    assert get_model_metadata("experimental_dsp_masks")["verification_status"] == "experimental_heuristic"


def test_vram_telemetry_records_measured_allocator_values():
    class FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def max_memory_allocated():
            return 512 * 1024 * 1024

        @staticmethod
        def max_memory_reserved():
            return 768 * 1024 * 1024

    class FakeTorch:
        cuda = FakeCuda()

    result = capture_cuda_telemetry(FakeTorch, {"duration_sec": 4.5})
    assert result == {
        "duration_sec": 4.5,
        "device": "cuda",
        "peak_allocated_mb": 512.0,
        "peak_reserved_mb": 768.0,
    }


def test_project_output_path_is_sanitized_and_scoped(tmp_path):
    output = project_stems_dir(str(tmp_path), "../../Song: Name")
    assert os.path.commonpath([str(tmp_path), output]) == str(tmp_path)
    assert os.path.basename(output) == "Song_Name"
