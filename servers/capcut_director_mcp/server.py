"""Universal MCP Server for Module 3: CapCut Director MCP.

Automates CapCut Desktop by reading visual_sync_map.json and AI video clips (Google Veo),
manipulating draft_content.json with micro speed-ramping, beat-synced cuts, and breakdown FX.
"""

import sys
import os
import json
from typing import Dict, Any, Optional
from fastmcp import FastMCP

# Ensure the project root and current server dir are in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
VENDOR_PYCAPCUT = os.path.join(PROJECT_ROOT, "vendor", "pyCapCut")
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if VENDOR_PYCAPCUT not in sys.path:
    sys.path.insert(0, VENDOR_PYCAPCUT)

import pycapcut as cc
from pycapcut import trange

try:
    from .draft_manager import (
        resolve_capcut_draft_root,
        initialize_capcut_draft,
        finalize_and_save_draft,
    )
    from .beat_cutter import (
        list_and_classify_footage,
        calculate_speed_multiplier,
    )
    from .fx_injector import inject_breakdown_fx
except ImportError:
    from draft_manager import (
        resolve_capcut_draft_root,
        initialize_capcut_draft,
        finalize_and_save_draft,
    )
    from beat_cutter import (
        list_and_classify_footage,
        calculate_speed_multiplier,
    )
    from fx_injector import inject_breakdown_fx

from shared_schemas.sync_map_schema import SongSyncMap

mcp = FastMCP("capcut-director-mcp")


@mcp.tool()
def list_veo_footage_and_classify(footage_dir: str) -> Dict[str, Any]:
    """Scan a folder of Google Veo .mp4 clips, inspect video duration/fps/motion energy,

    and classify them into instrument categories and playing states.
    """
    return list_and_classify_footage(footage_dir)


@mcp.tool()
def assemble_capcut_music_video(
    draft_name: str,
    sync_map_json_path: str,
    footage_dir: str,
    capcut_drafts_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Create and assemble a beat-synchronized CapCut Desktop project timeline

    by matching Veo clips to InstrumentEvents, applying micro speed-ramping,
    transient hard cuts, and breakdown zoom/shake keyframes.
    """
    if not os.path.exists(sync_map_json_path):
        raise FileNotFoundError(f"Sync map JSON not found: {sync_map_json_path}")

    with open(sync_map_json_path, "r", encoding="utf-8") as f:
        sync_map_dict = json.load(f)
    sync_map = SongSyncMap.model_validate(sync_map_dict)

    # 1. Scan and categorize footage clips
    footage_data = list_and_classify_footage(footage_dir)
    clips_by_inst = footage_data.get("classified_by_instrument", {})
    all_clips = footage_data.get("clips", [])

    # 2. Initialize CapCut Draft
    script, draft_dir = initialize_capcut_draft(
        draft_name=draft_name,
        drafts_root=capcut_drafts_root,
        width=1920,
        height=1080,
        fps=30,
    )

    # Add Audio Track 1, Video Track 1 (Primary), Video Track 2 (Overlay / B-roll)
    script.add_track(cc.TrackType.audio, track_name="Master Audio")
    script.add_track(cc.TrackType.video, track_name="Primary Video")
    script.add_track(cc.TrackType.video, track_name="B-Roll Overlay")

    # 3. Place Master Audio on Audio Track 1
    master_audio = sync_map.master_audio_path
    if not os.path.isabs(master_audio):
        master_audio = os.path.abspath(os.path.join(PROJECT_ROOT, master_audio))

    audio_placed = False
    if os.path.exists(master_audio):
        try:
            audio_mat = cc.AudioMaterial(master_audio)
            audio_seg = cc.AudioSegment(
                audio_mat,
                target_timerange=trange(0, audio_mat.duration),
                volume=1.0,
            )
            script.add_segment(audio_seg, track_name="Master Audio")
            audio_placed = True
        except Exception:
            audio_placed = False

    # 4. Place Video Segments for each InstrumentEvent
    placed_segments_count = 0
    injected_fx_count = 0
    clip_index_tracker = {}

    for ev in sync_map.events:
        inst = ev.instrument
        matching_clips = clips_by_inst.get(inst, [])
        if not matching_clips and "guitar" in inst:
            matching_clips = clips_by_inst.get("guitar", [])
        if not matching_clips and "vocal" in inst:
            matching_clips = clips_by_inst.get("vocals", [])
        if not matching_clips and any(k in inst for k in ["violin", "viola", "cello", "contrabass", "strings", "brass", "woodwind", "choir"]):
            matching_clips = clips_by_inst.get("orchestra", []) or clips_by_inst.get("strings_ensemble", [])
        if not matching_clips:
            matching_clips = clips_by_inst.get("broll", [])
        if not matching_clips:
            matching_clips = all_clips

        if not matching_clips:
            continue

        # Round-robin selection of matching clips
        c_idx = clip_index_tracker.get(inst, 0) % len(matching_clips)
        clip_info = matching_clips[c_idx]
        clip_index_tracker[inst] = c_idx + 1

        v_path = clip_info["filepath"]
        if not os.path.exists(v_path):
            continue

        try:
            v_mat = cc.VideoMaterial(v_path)
            start_us = int(ev.start_time_sec * 1_000_000)
            target_dur_us = max(100_000, int(ev.duration_sec * 1_000_000))

            # Micro speed-ramping to match song BPM
            speed = calculate_speed_multiplier(sync_map.bpm, clip_info.get("native_bpm", 120.0))

            # Calculate source duration within bounds of material
            source_dur_us = min(v_mat.duration, int(target_dur_us * speed))
            actual_target_dur = max(33_333, int(source_dur_us / speed))

            v_seg = cc.VideoSegment(
                v_mat,
                target_timerange=trange(start_us, actual_target_dur),
                source_timerange=trange(0, source_dur_us),
                speed=speed,
            )

            # Inject breakdown FX & scale punch keyframes
            is_heavy = ev.playing_state == "heavy_breakdown_cymbal"
            fx_injected = inject_breakdown_fx(
                segment=v_seg,
                fx_type=ev.recommended_capcut_fx,
                is_heavy_breakdown=is_heavy,
                segment_duration_us=actual_target_dur,
            )
            injected_fx_count += fx_injected

            # Attempt placing on Primary Video track, fallback to Overlay on overlap
            try:
                script.add_segment(v_seg, track_name="Primary Video")
                placed_segments_count += 1
            except cc.exceptions.SegmentOverlap:
                try:
                    script.add_segment(v_seg, track_name="B-Roll Overlay")
                    placed_segments_count += 1
                except cc.exceptions.SegmentOverlap:
                    # Both tracks occupied at this timestamp, continue
                    pass
        except Exception:
            continue

    # 5. Finalize and Save Draft
    save_result = finalize_and_save_draft(script, draft_dir)

    return {
        "status": "success",
        "draft_name": draft_name,
        "draft_dir": draft_dir,
        "draft_content_json": save_result["draft_content_json"],
        "draft_info_json": save_result["draft_info_json"],
        "master_audio_placed": audio_placed,
        "video_segments_placed": placed_segments_count,
        "fx_keyframes_injected": injected_fx_count,
        "song_bpm": sync_map.bpm,
        "total_events_in_map": len(sync_map.events),
    }


if __name__ == "__main__":
    mcp.run()
