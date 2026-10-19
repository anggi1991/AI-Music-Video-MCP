"""Universal MCP Server for Module 1: DAW Studio MCP.

Handles audio analysis, stem mashup, time-stretching, pitch-shifting, mixing, and mastering.
"""

import sys
import os
from typing import Dict, Optional, Any, List
from fastmcp import FastMCP

# Ensure the project root and current server dir are in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from .mashup_engine import analyze_audio_metadata as _analyze_audio_metadata
    from .mashup_engine import mashup_replace_segment as _mashup_replace_segment
    from .mix_master_engine import auto_mix_and_master_stems as _auto_mix_and_master_stems
    from .stem_separator import separate_audio_6stems as _separate_audio_6stems
    from .guitar_decomposer import decompose_guitar_stem as _decompose_guitar_stem
    from .vocal_decomposer import decompose_vocal_stem as _decompose_vocal_stem
    from .orchestra_decomposer import (
        decompose_orchestral_stem as _decompose_orchestral_stem,
        detect_active_instruments_in_stem as _detect_active_instruments_in_stem,
    )
    from .vst3_manager import (
        scan_installed_vst3_plugins as _scan_installed_vst3_plugins,
        inspect_vst3_parameters as _inspect_vst3_parameters,
    )
    from .stem_polisher import polish_stems_batch as _polish_stems_batch
    from .daw_bridge import (
        DAWBridge,
        generate_reaper_project_rpp as _generate_reaper_project_rpp,
        export_ableton_als_session_manifest as _export_ableton_als_session_manifest,
    )
except ImportError:
    from mashup_engine import analyze_audio_metadata as _analyze_audio_metadata
    from mashup_engine import mashup_replace_segment as _mashup_replace_segment
    from mix_master_engine import auto_mix_and_master_stems as _auto_mix_and_master_stems
    from stem_separator import separate_audio_6stems as _separate_audio_6stems
    from guitar_decomposer import decompose_guitar_stem as _decompose_guitar_stem
    from vocal_decomposer import decompose_vocal_stem as _decompose_vocal_stem
    from orchestra_decomposer import (
        decompose_orchestral_stem as _decompose_orchestral_stem,
        detect_active_instruments_in_stem as _detect_active_instruments_in_stem,
    )
    from vst3_manager import (
        scan_installed_vst3_plugins as _scan_installed_vst3_plugins,
        inspect_vst3_parameters as _inspect_vst3_parameters,
    )
    from stem_polisher import polish_stems_batch as _polish_stems_batch
    from daw_bridge import (
        DAWBridge,
        generate_reaper_project_rpp as _generate_reaper_project_rpp,
        export_ableton_als_session_manifest as _export_ableton_als_session_manifest,
    )

mcp = FastMCP("daw-studio-mcp")
daw_bridge = DAWBridge()


@mcp.tool()
def analyze_audio_metadata(audio_path: str) -> Dict[str, Any]:
    """Detect exact BPM, Musical Key (Root + Major/Minor using Krumhansl-Schmuckler profile),

    duration, integrated LUFS, and transient onset timestamps.
    """
    return _analyze_audio_metadata(audio_path)


@mcp.tool()
def mashup_replace_segment(
    base_stem_path: str,
    donor_stem_path: str,
    base_replace_start: float,
    base_replace_end: float,
    donor_extract_start: float,
    donor_extract_end: float,
    output_path: str,
) -> Dict[str, Any]:
    """Replace a segment in base stem with a time-stretched and pitch-shifted segment from donor stem.

    Uses equal-power 15ms cosine crossfade at splice boundaries to prevent clicks.
    """
    return _mashup_replace_segment(
        base_stem_path=base_stem_path,
        donor_stem_path=donor_stem_path,
        base_replace_start=base_replace_start,
        base_replace_end=base_replace_end,
        donor_extract_start=donor_extract_start,
        donor_extract_end=donor_extract_end,
        output_path=output_path,
    )


@mcp.tool()
def auto_mix_and_master_stems(
    stem_paths: Dict[str, str],
    genre_profile: str = "metalcore",
    target_lufs: float = -9.0,
    reference_track_path: Optional[str] = None,
    output_master_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Mix separated audio stems using Spotify's pedalboard genre DSP chains and master

    to target LUFS or match a reference track using matchering.
    """
    return _auto_mix_and_master_stems(
        stem_paths=stem_paths,
        genre_profile=genre_profile,
        target_lufs=target_lufs,
        reference_track_path=reference_track_path,
        output_master_path=output_master_path,
    )


@mcp.tool()
def separate_audio_6stems(
    audio_path: str,
    output_dir: str = "workspace/input_stems",
    model_name: str = "htdemucs_6s",
    apply_bleed_gate: bool = False,
    split_guitar_substems: bool = False,
    split_vocal_substems: bool = False,
    split_orchestral_substems: bool = False,
    segment_sec: Optional[float] = None,
    auto_polish_stems: bool = False,
) -> Dict[str, Any]:
    """Separate with pretrained htdemucs_6s; optional DSP sub-stems are experimental masks."""
    return _separate_audio_6stems(
        audio_path=audio_path,
        output_dir=output_dir,
        model_name=model_name,
        apply_bleed_gate=apply_bleed_gate,
        split_guitar_substems=split_guitar_substems,
        split_vocal_substems=split_vocal_substems,
        split_orchestral_substems=split_orchestral_substems,
        segment_sec=segment_sec,
        auto_polish_stems=auto_polish_stems,
    )


@mcp.tool()
def decompose_guitar_stem(
    guitar_stem_path: str,
    output_dir: str = "workspace/input_stems",
) -> Dict[str, Any]:
    """Create experimental frequency/spatial guitar masks; outputs are not isolated performances."""
    return _decompose_guitar_stem(
        guitar_stem_path=guitar_stem_path,
        output_dir=output_dir,
    )


@mcp.tool()
def decompose_single_vocal_stem(
    vocal_stem_path: str,
    output_dir: str = "workspace/input_stems",
    enable_lip_sync_gate: bool = True,
    gate_threshold_db: float = -40.0,
) -> Dict[str, Any]:
    """Create experimental vocal masks; outputs do not identify separate singers or guarantee lip-sync readiness."""
    return _decompose_vocal_stem(
        vocal_stem_path=vocal_stem_path,
        output_dir=output_dir,
        enable_lip_sync_gate=enable_lip_sync_gate,
        gate_threshold_db=gate_threshold_db,
    )


@mcp.tool()
def detect_and_decompose_orchestra(
    stem_path: str,
    output_dir: str = "workspace/input_stems",
    auto_detect_only: bool = True,
    min_confidence: float = 0.25,
) -> Dict[str, Any]:
    """Estimate orchestral timbre from other.wav and write broad filtered mixtures, not isolated sources."""
    return _decompose_orchestral_stem(
        other_stem_path=stem_path,
        output_dir=output_dir,
        auto_detect_only=auto_detect_only,
        min_confidence=min_confidence,
    )


@mcp.tool()
def scan_system_vst3_plugins(custom_search_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """Scan system and custom folders for installed VST3/VSTi plugins (Categories A-D)."""
    return _scan_installed_vst3_plugins(custom_search_paths=custom_search_paths)


@mcp.tool()
def inspect_vst3_plugin_params(vst3_path: str) -> Dict[str, Any]:
    """Inspect parameters and instrument status of a specific VST3 plugin via pedalboard."""
    return _inspect_vst3_parameters(vst3_path=vst3_path)


@mcp.tool()
def create_reaper_daw_project(
    project_name: str,
    bpm: float,
    stem_paths: Dict[str, str],
    time_signature: str = "4/4",
    sync_map_json_path: Optional[str] = None,
    include_vsti_midi_tracks: bool = False,
    vst3_assignments: Optional[Dict[str, Any]] = None,
    output_rpp_path: str = r"F:\AI-Music-Video-MCP\workspace\output_audio\session.rpp",
) -> Dict[str, Any]:
    """Generate a REAPER session skeleton; uses existing stems/plugins and never fabricates MIDI notes."""
    return _generate_reaper_project_rpp(
        project_name=project_name,
        bpm=bpm,
        time_signature=time_signature,
        stem_paths=stem_paths,
        sync_map_json_path=sync_map_json_path,
        include_vsti_midi_tracks=include_vsti_midi_tracks,
        vst3_assignments=vst3_assignments,
        output_rpp_path=output_rpp_path,
    )


@mcp.tool()
def create_ableton_session_manifest(
    project_name: str,
    bpm: float,
    musical_key: str,
    stem_paths: Dict[str, str],
    sync_map_json_path: Optional[str] = None,
    vst3_assignments: Optional[Dict[str, Any]] = None,
    output_dir: str = r"F:\AI-Music-Video-MCP\workspace\output_audio",
) -> Dict[str, Any]:
    """Generate an Ableton Live Session Manifest JSON detailing track groups, routing, and VST3 assignments."""
    return _export_ableton_als_session_manifest(
        project_name=project_name,
        bpm=bpm,
        musical_key=musical_key,
        stem_paths=stem_paths,
        sync_map_json_path=sync_map_json_path,
        vst3_assignments=vst3_assignments,
        output_dir=output_dir,
    )


@mcp.tool()
def trigger_daw_transport(action: str = "play") -> Dict[str, Any]:
    """Trigger transport control in a connected DAW (play, stop, record via OSC)."""
    if action == "play":
        return daw_bridge.play()
    elif action == "stop":
        return daw_bridge.stop()
    elif action == "record":
        return daw_bridge.record()
    else:
        return {"status": "error", "message": f"Unknown transport action: {action}"}


if __name__ == "__main__":
    mcp.run()


@mcp.tool()
def auto_polish_audio_stems(
    stems_dict: Dict[str, str],
    output_dir: Optional[str] = None,
    enable_vst3: bool = True,
) -> Dict[str, Any]:
    """Sequentially polish stems using dynamic VST3 discovery with native Pedalboard DSP fallback."""
    return _polish_stems_batch(
        stems_dict=stems_dict,
        output_dir=output_dir,
        enable_vst3=enable_vst3,
    )
