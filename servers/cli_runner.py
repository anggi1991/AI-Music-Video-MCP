"""CLI Runner Bridge between Next.js Web UI and Python MCP Backend.

Executes actions from Next.js API Routes:
- scan_vst3
- separate_stems
- mashup
- mix_master
- transcribe_tabs
- create_reaper_rpp
- create_ableton
- classify_footage
- assemble_capcut
- run_full_pipeline
"""

import sys
import os
import json
import argparse
from typing import Dict, Any

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from servers.daw_studio_mcp.vst3_manager import (
    scan_installed_vst3_plugins,
    inspect_vst3_parameters,
    build_flagship_role_chain,
)
from servers.daw_studio_mcp.stem_separator import separate_audio_6stems
from servers.workspace_paths import project_stems_dir, resolve_source_song
from servers.daw_studio_mcp.model_registry import get_model_metadata
from servers.daw_studio_mcp.guitar_decomposer import decompose_guitar_stem
from servers.daw_studio_mcp.vocal_decomposer import decompose_vocal_stem
from servers.daw_studio_mcp.orchestra_decomposer import decompose_orchestral_stem, detect_active_instruments_in_stem
from servers.daw_studio_mcp.mashup_engine import analyze_audio_metadata, mashup_replace_segment
from servers.daw_studio_mcp.mix_master_engine import auto_mix_and_master_stems
from servers.daw_studio_mcp.daw_bridge import (
    generate_reaper_project_rpp,
    export_ableton_als_session_manifest,
)
from servers.tab_transcriber_mcp.server import transcribe_stems_to_gp5_and_sync_map
from servers.capcut_director_mcp.beat_cutter import list_and_classify_footage
from servers.capcut_director_mcp.server import assemble_capcut_music_video


def clean_p(val: Any) -> Any:
    """Recursively strip leading/trailing quotes and whitespace from path strings."""
    if isinstance(val, str):
        cleaned = val.strip().strip('"').strip("'")
        return cleaned
    elif isinstance(val, dict):
        return {k: clean_p(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [clean_p(x) for x in val]
    return val


def run_action(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the requested backend action and return the result dictionary."""
    params = clean_p(params)
    if action == "scan_vst3":
        custom_paths = params.get("custom_paths")
        return scan_installed_vst3_plugins(custom_paths)

    elif action == "inspect_vst3":
        vst_path = params.get("vst3_path", "")
        return inspect_vst3_parameters(vst_path)

    elif action == "analyze_audio":
        audio_path = params.get("audio_path", "")
        return analyze_audio_metadata(audio_path)

    elif action == "separate_stems":
        audio_path = resolve_source_song(PROJECT_ROOT, params.get("audio_path", ""))
        raw_project = str(params.get("project_name") or os.path.splitext(os.path.basename(audio_path))[0])
        output_dir = project_stems_dir(PROJECT_ROOT, raw_project, os.path.splitext(os.path.basename(audio_path))[0])
        model_name = params.get("model_name", "htdemucs_6s")
        if model_name == "cascaded_separation":
            return {
                "status": "error",
                "error": {
                    "code": "CASCADE_NOT_CONFIGURED",
                    "message": "No verified cascade stages are configured yet; no audio was processed.",
                },
                "model_metadata": get_model_metadata("cascaded_separation"),
            }
        return separate_audio_6stems(
            audio_path=audio_path,
            output_dir=output_dir,
            model_name=model_name,
            apply_bleed_gate=params.get("apply_bleed_gate", False),
            split_guitar_substems=params.get("split_guitar_substems", False),
            split_vocal_substems=params.get("split_vocal_substems", False),
            split_orchestral_substems=params.get("split_orchestral_substems", False),
            allow_dsp_fallback=params.get("allow_dsp_fallback", False),
            segment_sec=params.get("segment_sec"),
        )

    elif action == "decompose_guitar":
        return decompose_guitar_stem(
            guitar_stem_path=params.get("guitar_stem_path", ""),
            output_dir=params.get("output_dir", os.path.join(PROJECT_ROOT, "workspace", "input_stems")),
        )

    elif action == "decompose_vocals":
        return decompose_vocal_stem(
            vocal_stem_path=params.get("vocal_stem_path", ""),
            output_dir=params.get("output_dir", os.path.join(PROJECT_ROOT, "workspace", "input_stems")),
            enable_lip_sync_gate=params.get("enable_lip_sync_gate", True),
            gate_threshold_db=float(params.get("gate_threshold_db", -40.0)),
        )

    elif action == "decompose_orchestra":
        return decompose_orchestral_stem(
            other_stem_path=params.get("other_stem_path", ""),
            output_dir=params.get("output_dir", os.path.join(PROJECT_ROOT, "workspace", "input_stems")),
            auto_detect_only=params.get("auto_detect_only", True),
            min_confidence=float(params.get("min_confidence", 0.25)),
        )

    elif action == "mashup":
        return mashup_replace_segment(
            base_stem_path=params.get("base_stem_path", ""),
            donor_stem_path=params.get("donor_stem_path", ""),
            base_replace_start=float(params.get("base_replace_start", 0.0)),
            base_replace_end=float(params.get("base_replace_end", 2.0)),
            donor_extract_start=float(params.get("donor_extract_start", 0.0)),
            donor_extract_end=float(params.get("donor_extract_end", 2.0)),
            output_path=params.get("output_path", os.path.join(PROJECT_ROOT, "workspace", "output_audio", "mashup_stem.wav")),
        )

    elif action == "mix_master":
        stems = params.get("stem_paths", {})
        if isinstance(stems, str):
            stems = json.loads(stems)
        return auto_mix_and_master_stems(
            stem_paths=stems,
            genre_profile=params.get("genre_profile", "metalcore"),
            target_lufs=float(params.get("target_lufs", -9.0)),
            reference_track_path=params.get("reference_track_path"),
            output_master_path=params.get("output_master_path"),
            auto_use_detected_vst3=params.get("auto_use_detected_vst3", True),
        )

    elif action == "transcribe_tabs":
        extra_stems = params.get("extra_instrument_stems", {})
        if isinstance(extra_stems, str):
            extra_stems = json.loads(extra_stems)
        return transcribe_stems_to_gp5_and_sync_map(
            project_name=params.get("project_name", "Song"),
            bpm=float(params.get("bpm", 140.0)),
            musical_key=params.get("musical_key", "C Minor"),
            guitar_stem=params.get("guitar_stem"),
            bass_stem=params.get("bass_stem", ""),
            drum_stem=params.get("drum_stem", ""),
            synth_stem=params.get("synth_stem", ""),
            output_dir=params.get("output_dir", os.path.join(PROJECT_ROOT, "workspace", "output_tabs")),
            guitar_rhythm_stem=params.get("guitar_rhythm_stem"),
            guitar_lead_stem=params.get("guitar_lead_stem"),
            guitar_additional_stem=params.get("guitar_additional_stem"),
            vocal_lead_stem=params.get("vocal_lead_stem"),
            vocal_co_lead_stem=params.get("vocal_co_lead_stem"),
            vocal_backing_stem=params.get("vocal_backing_stem"),
            extra_instrument_stems=extra_stems,
            master_audio_path=params.get("master_audio_path", params.get("audio_path")),
        )

    elif action == "create_reaper_rpp":
        stems = params.get("stem_paths", {})
        if isinstance(stems, str):
            stems = json.loads(stems)
        project_name = params.get("project_name", "Studio_Project")
        if not stems and project_name:
            stem_dir = os.path.join(PROJECT_ROOT, "workspace", "input_stems", project_name)
            if os.path.isdir(stem_dir):
                for f in os.listdir(stem_dir):
                    if f.endswith(".wav"):
                        key = os.path.splitext(f)[0]
                        stems[key] = os.path.join(stem_dir, f)
        res = generate_reaper_project_rpp(
            project_name=project_name,
            bpm=float(params.get("bpm", 140.0)),
            time_signature=params.get("time_signature", "4/4"),
            stem_paths=stems,
            sync_map_json_path=params.get("sync_map_json_path"),
            include_vsti_midi_tracks=params.get("include_vsti_midi_tracks", False),
            output_rpp_path=params.get("output_rpp_path", os.path.join(PROJECT_ROOT, "workspace", "output_audio", f"{project_name}_session.rpp")),
        )
        if params.get("launch_reaper", False) and res.get("rpp_path") and os.path.isfile(res["rpp_path"]):
            try:
                os.startfile(os.path.abspath(res["rpp_path"]))
                res["launched"] = True
            except Exception:
                res["launched"] = False
        return res

    elif action == "create_ableton":
        stems = params.get("stem_paths", {})
        if isinstance(stems, str):
            stems = json.loads(stems)
        project_name = params.get("project_name", "Studio_Project")
        if not stems and project_name:
            stem_dir = os.path.join(PROJECT_ROOT, "workspace", "input_stems", project_name)
            if os.path.isdir(stem_dir):
                for f in os.listdir(stem_dir):
                    if f.endswith(".wav"):
                        key = os.path.splitext(f)[0]
                        stems[key] = os.path.join(stem_dir, f)
        return export_ableton_als_session_manifest(
            project_name=project_name,
            bpm=float(params.get("bpm", 140.0)),
            musical_key=params.get("musical_key", "C Minor"),
            stem_paths=stems,
            sync_map_json_path=params.get("sync_map_json_path"),
            output_dir=params.get("output_dir", os.path.join(PROJECT_ROOT, "workspace", "output_audio")),
            generate_als=bool(params.get("generate_als", True)),
            launch_ableton=bool(params.get("launch_ableton", False)),
        )

    elif action == "classify_footage":
        footage_dir = params.get("footage_dir", os.path.join(PROJECT_ROOT, "workspace", "veo_footage"))
        return list_and_classify_footage(footage_dir)

    elif action == "assemble_capcut":
        return assemble_capcut_music_video(
            draft_name=params.get("draft_name", "AI_Music_Video_Draft"),
            sync_map_json_path=params.get("sync_map_json_path", os.path.join(PROJECT_ROOT, "workspace", "output_tabs", "visual_sync_map.json")),
            footage_dir=params.get("footage_dir", os.path.join(PROJECT_ROOT, "workspace", "veo_footage")),
            capcut_drafts_root=params.get("capcut_drafts_root"),
        )

    elif action == "run_full_pipeline":
        # Comprehensive 1-click end-to-end execution
        audio_path = resolve_source_song(PROJECT_ROOT, params.get("audio_path", ""))

        project_name = params.get("project_name") or os.path.splitext(os.path.basename(audio_path))[0]
        stems_dir = project_stems_dir(PROJECT_ROOT, project_name, os.path.splitext(os.path.basename(audio_path))[0])
        tabs_dir = os.path.join(PROJECT_ROOT, "workspace", "output_tabs")
        audio_out_dir = os.path.join(PROJECT_ROOT, "workspace", "output_audio")
        footage_dir = params.get("footage_dir", os.path.join(PROJECT_ROOT, "workspace", "veo_footage"))

        meta = analyze_audio_metadata(audio_path)
        bpm = meta["bpm"]
        musical_key = meta["musical_key"]

        # 1. Stem separation
        sep_res = separate_audio_6stems(
            audio_path=audio_path,
            output_dir=stems_dir,
            apply_bleed_gate=params.get("apply_bleed_gate", False),
            split_guitar_substems=params.get("split_guitar_substems", False),
            split_vocal_substems=params.get("split_vocal_substems", False),
            split_orchestral_substems=params.get("split_orchestral_substems", False),
            allow_dsp_fallback=params.get("allow_dsp_fallback", False),
        )

        all_stems = dict(sep_res.get("stems", {}))
        # The current guitar/vocal/orchestra sub-decomposers use heuristic
        # masks. Keep those experimental renders out of mastering and
        # transcription, where their instrument labels would be misleading.

        # 2. Mix & Master
        master_out = os.path.join(audio_out_dir, f"{project_name}_master.wav")
        mix_res = auto_mix_and_master_stems(
            stem_paths=all_stems,
            genre_profile=params.get("genre_profile", "metalcore"),
            target_lufs=float(params.get("target_lufs", -9.0)),
            output_master_path=master_out,
            auto_use_detected_vst3=params.get("auto_use_detected_vst3", True),
        )

        # 3. Transcribe Tabs & Sync Map
        tab_res = transcribe_stems_to_gp5_and_sync_map(
            project_name=project_name,
            bpm=bpm,
            musical_key=musical_key,
            guitar_rhythm_stem=all_stems.get("guitar_rhythm"),
            guitar_lead_stem=all_stems.get("guitar_lead"),
            guitar_additional_stem=all_stems.get("guitar_additional"),
            guitar_stem=all_stems.get("guitar"),
            vocal_lead_stem=all_stems.get("vocal_lead"),
            vocal_co_lead_stem=all_stems.get("vocal_co_lead"),
            vocal_backing_stem=all_stems.get("vocal_backing"),
            bass_stem=all_stems.get("bass", ""),
            drum_stem=all_stems.get("drums", ""),
            synth_stem=all_stems.get("synth", ""),
            output_dir=tabs_dir,
            master_audio_path=audio_path,
        )

        # 4. Generate REAPER .rpp & Ableton manifest
        rpp_out = os.path.join(audio_out_dir, f"{project_name}_session.rpp")
        rpp_res = generate_reaper_project_rpp(
            project_name=project_name,
            bpm=bpm,
            stem_paths=all_stems,
            sync_map_json_path=tab_res["sync_map_path"],
            include_vsti_midi_tracks=False,
            output_rpp_path=rpp_out,
        )

        # 5. CapCut Assembly
        capcut_res = assemble_capcut_music_video(
            draft_name=project_name,
            sync_map_json_path=tab_res["sync_map_path"],
            footage_dir=footage_dir,
        )

        pipeline_warnings = []
        if sep_res.get("status") != "success":
            pipeline_warnings.extend(sep_res.get("warnings", ["Stem separation completed with limitations."]))
        if tab_res.get("transcription_quality") == "automatic_draft":
            pipeline_warnings.append("Tablature and sync events are automatic drafts and need human review.")
        if capcut_res.get("status") not in (None, "success", "created"):
            pipeline_warnings.append("CapCut output did not report a fully successful assembly.")

        return {
            "status": "partial" if pipeline_warnings else "success",
            "warnings": pipeline_warnings,
            "project_name": project_name,
            "bpm": bpm,
            "musical_key": musical_key,
            "separation": sep_res,
            "mix_master": mix_res,
            "tablature": tab_res,
            "reaper_project": rpp_res,
            "capcut_draft": capcut_res,
        }

    else:
        raise ValueError(f"Unknown action: {action}")


def main():
    parser = argparse.ArgumentParser(description="CLI Runner for AI Music & Video MCP Backend")
    parser.add_argument("action", nargs="?", default="scan_vst3", help="Action to execute")
    parser.add_argument("--params", help="JSON string containing action parameters")
    parser.add_argument("--json-input", help="Direct full JSON input containing action and params")
    args = parser.parse_args()

    action = args.action
    params: Dict[str, Any] = {}

    if args.json_input:
        try:
            data = json.loads(args.json_input)
            action = data.get("action", action)
            params = data.get("params", {})
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"Malformed JSON input: {e}"}))
            sys.exit(1)
    elif args.params:
        try:
            params = json.loads(args.params)
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"Malformed params: {e}"}))
            sys.exit(1)

    try:
        result = run_action(action, params)
        print(json.dumps(result, indent=2))
    except Exception as e:
        import traceback
        err_payload = {
            "status": "error",
            "action": action,
            "error_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
        print(json.dumps(err_payload, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
