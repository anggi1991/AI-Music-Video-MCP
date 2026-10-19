"""Universal MCP Server for Module 2: Tab Transcriber MCP.

Converts separated instrument stems into human-playable Full-Band Tablature (.gp5 & .musicxml)
and AI visual coordinate sync map (visual_sync_map.json), with full Multi-Guitar,
Orchestral Strings & Winds, and Multi-Vocalist support.
"""

import sys
import os
from typing import Dict, Any, Optional, List
from fastmcp import FastMCP

# Ensure the project root and current server dir are in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from .pitch_tracker import analyze_stem_pitches
    from .fretboard_solver import (
        TUNINGS,
        detect_guitar_tuning,
        detect_bass_tuning,
        get_bowed_instrument_tuning,
        viterbi_fretboard_solver,
        classify_playing_state,
        classify_vocal_events,
    )
    from .gp5_exporter import export_gp5_and_musicxml
    from .visual_prompt_mapper import build_song_sync_map
except ImportError:
    from pitch_tracker import analyze_stem_pitches
    from fretboard_solver import (
        TUNINGS,
        detect_guitar_tuning,
        detect_bass_tuning,
        get_bowed_instrument_tuning,
        viterbi_fretboard_solver,
        classify_playing_state,
        classify_vocal_events,
    )
    from gp5_exporter import export_gp5_and_musicxml
    from visual_prompt_mapper import build_song_sync_map

try:
    from servers.daw_studio_mcp.guitar_decomposer import decompose_guitar_stem
    from servers.daw_studio_mcp.vocal_decomposer import decompose_vocal_stem
    from servers.daw_studio_mcp.orchestra_decomposer import decompose_orchestral_stem
except Exception:
    decompose_guitar_stem = None
    decompose_vocal_stem = None
    decompose_orchestral_stem = None

try:
    from .daw_midi_importer import import_verified_daw_midi
except ImportError:
    try:
        from daw_midi_importer import import_verified_daw_midi
    except Exception:
        import_verified_daw_midi = None

mcp = FastMCP("tab-transcriber-mcp")


@mcp.tool()
def transcribe_stems_to_gp5_and_sync_map(
    project_name: str,
    bpm: float,
    musical_key: str,
    guitar_stem: Optional[str] = None,
    bass_stem: str = "",
    drum_stem: str = "",
    synth_stem: str = "",
    output_dir: str = "workspace/output_tabs",
    guitar_rhythm_stem: Optional[str] = None,
    guitar_lead_stem: Optional[str] = None,
    guitar_additional_stem: Optional[str] = None,
    auto_decompose_guitar: bool = False,
    vocal_lead_stem: Optional[str] = None,
    vocal_co_lead_stem: Optional[str] = None,
    vocal_backing_stem: Optional[str] = None,
    vocals_stem: Optional[str] = None,
    auto_decompose_vocals: bool = False,
    extra_instrument_stems: Optional[Dict[str, str]] = None,
    other_stem: Optional[str] = None,
    auto_decompose_orchestra: bool = False,
    master_audio_path: Optional[str] = None,
    tuning_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Transcribe audio stems into multi-track Guitar Pro 5 (.gp5), MusicXML, and visual_sync_map.json.

    Supports rock/metal rhythm & lead guitars, orchestral strings (violin, cello), brass, woodwinds, and multi-vocalists.
    """
    os.makedirs(output_dir, exist_ok=True)
    extra_instrument_stems = dict(extra_instrument_stems or {})

    # 1. Auto-decomposition for guitar
    if auto_decompose_guitar and guitar_stem and os.path.exists(guitar_stem) and decompose_guitar_stem:
        decomp_dir = os.path.join(output_dir, "decomposed_guitars")
        decomp_res = decompose_guitar_stem(guitar_stem, decomp_dir)
        guitar_rhythm_stem = decomp_res["guitar_rhythm_path"]
        guitar_lead_stem = decomp_res["guitar_lead_path"]
        guitar_additional_stem = decomp_res["guitar_additional_path"]

    # 2. Auto-decomposition for vocals
    if auto_decompose_vocals and vocals_stem and os.path.exists(vocals_stem) and decompose_vocal_stem:
        v_decomp_dir = os.path.join(output_dir, "decomposed_vocals")
        v_decomp_res = decompose_vocal_stem(vocals_stem, v_decomp_dir)
        vocal_lead_stem = v_decomp_res["vocal_lead_path"]
        vocal_co_lead_stem = v_decomp_res["vocal_co_lead_path"]
        vocal_backing_stem = v_decomp_res["vocal_backing_path"]

    # 3. Auto-decomposition for orchestra from other.wav
    if auto_decompose_orchestra and other_stem and os.path.exists(other_stem) and decompose_orchestral_stem:
        o_decomp_dir = os.path.join(output_dir, "decomposed_orchestra")
        o_decomp_res = decompose_orchestral_stem(other_stem, o_decomp_dir, auto_detect_only=True)
        for inst_name, path in o_decomp_res.get("exported_stems", {}).items():
            extra_instrument_stems[inst_name] = path

    has_multi_guitar = bool(guitar_rhythm_stem or guitar_lead_stem or guitar_additional_stem)

    # 4. Track pitches from core stems with in-memory memoization
    stem_analysis_cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_or_analyze(path: Optional[str], inst_type: str) -> List[Dict[str, Any]]:
        if not path or not os.path.exists(path):
            return []
        ckey = f"{path}::{inst_type}"
        if ckey not in stem_analysis_cache:
            stem_analysis_cache[ckey] = analyze_stem_pitches(path, inst_type)
        return stem_analysis_cache[ckey]

    raw_bass = get_or_analyze(bass_stem, "bass")
    raw_drums = get_or_analyze(drum_stem, "drums")
    raw_synth = get_or_analyze(synth_stem, "synth")

    # 5. Guitar Tuning Detection
    if tuning_name and tuning_name in TUNINGS:
        open_strings = TUNINGS[tuning_name]
    else:
        ref_stem = guitar_rhythm_stem or guitar_stem or guitar_lead_stem
        if ref_stem and os.path.exists(ref_stem):
            raw_ref = get_or_analyze(ref_stem, "guitar")
            lowest_note = min([ev.get("root_midi", 48) for ev in raw_ref], default=48)
        else:
            lowest_note = 48
        tuning_name, open_strings = detect_guitar_tuning(lowest_note)

    _, bass_open_strings = detect_bass_tuning(tuning_name)

    # Helper for fretted guitar tracks
    def solve_and_classify_fretted(stem_path: Optional[str], inst_label: str):
        if not stem_path or not os.path.exists(stem_path):
            return []
        raw = get_or_analyze(stem_path, "guitar")
        solved = viterbi_fretboard_solver(raw, open_strings, tuning_name=tuning_name)
        classified = []
        for ev in solved:
            state, is_trans, fx = classify_playing_state(ev, inst_label, bpm=bpm)
            ev_copy = dict(ev)
            ev_copy["playing_state"] = state
            ev_copy["is_transient_peak"] = is_trans
            ev_copy["recommended_capcut_fx"] = fx
            classified.append(ev_copy)
        return classified

    classified_rhythm = []
    classified_lead = []
    classified_additional = []
    classified_guitar = []

    if has_multi_guitar:
        classified_rhythm = solve_and_classify_fretted(guitar_rhythm_stem, "guitar_rhythm")
        classified_lead = solve_and_classify_fretted(guitar_lead_stem, "guitar_lead")
        classified_additional = solve_and_classify_fretted(guitar_additional_stem, "guitar_additional")
    elif guitar_stem and os.path.exists(guitar_stem):
        classified_guitar = solve_and_classify_fretted(guitar_stem, "guitar")

    # 6. Vocals processing
    def process_vocal_track(v_path: Optional[str], role: str):
        if not v_path or not os.path.exists(v_path):
            return []
        raw = analyze_stem_pitches(v_path, "vocals")
        classified = classify_vocal_events(raw, role)
        return classified

    classified_vocal_lead = process_vocal_track(vocal_lead_stem, "vocal_lead")
    classified_vocal_co_lead = process_vocal_track(vocal_co_lead_stem, "vocal_co_lead")
    classified_vocal_backing = process_vocal_track(vocal_backing_stem, "vocal_backing")

    # 7. Bowed Strings & Orchestral processing
    extra_classified: Dict[str, List[Dict[str, Any]]] = {}
    for inst_name, path in extra_instrument_stems.items():
        if not os.path.exists(path):
            continue
        key_inst = inst_name.lower().strip()
        raw = analyze_stem_pitches(path, key_inst)
        if any(b in key_inst for b in ["violin", "viola", "cello", "contrabass", "strings"]):
            bowed_tun = get_bowed_instrument_tuning(key_inst)
            solved = viterbi_fretboard_solver(raw, bowed_tun, tuning_name="Bowed")
            classified = []
            for ev in solved:
                state, is_trans, fx = classify_playing_state(ev, key_inst, bpm=bpm)
                ev_copy = dict(ev)
                ev_copy["playing_state"] = state
                ev_copy["is_transient_peak"] = is_trans
                ev_copy["recommended_capcut_fx"] = fx
                classified.append(ev_copy)
            extra_classified[inst_name] = classified
        else:
            classified = []
            for ev in raw:
                state, is_trans, fx = classify_playing_state(ev, key_inst, bpm=bpm)
                ev_copy = dict(ev)
                ev_copy["playing_state"] = state
                ev_copy["is_transient_peak"] = is_trans
                ev_copy["recommended_capcut_fx"] = fx
                classified.append(ev_copy)
            extra_classified[inst_name] = classified

    # 8. Solve Bass
    solved_bass = viterbi_fretboard_solver(raw_bass, bass_open_strings, tuning_name=tuning_name)
    classified_bass = []
    for ev in solved_bass:
        state, is_trans, fx = classify_playing_state(ev, "bass", bpm=bpm)
        ev_copy = dict(ev)
        ev_copy["playing_state"] = state
        ev_copy["is_transient_peak"] = is_trans
        ev_copy["recommended_capcut_fx"] = fx
        classified_bass.append(ev_copy)

    # 9. Classify Drums & Synth
    classified_drums = []
    for ev in raw_drums:
        state, is_trans, fx = classify_playing_state(ev, "drums", bpm=bpm)
        ev_copy = dict(ev)
        ev_copy["playing_state"] = state
        ev_copy["is_transient_peak"] = is_trans
        ev_copy["recommended_capcut_fx"] = fx
        classified_drums.append(ev_copy)

    classified_synth = []
    for ev in raw_synth:
        state, is_trans, fx = classify_playing_state(ev, "keyboard", bpm=bpm)
        ev_copy = dict(ev)
        ev_copy["playing_state"] = state
        ev_copy["is_transient_peak"] = is_trans
        ev_copy["recommended_capcut_fx"] = fx
        classified_synth.append(ev_copy)

    # 10. Export .gp5 and .musicxml
    gp5_file = os.path.join(output_dir, f"{project_name}.gp5")
    musicxml_file = os.path.join(output_dir, f"{project_name}.musicxml")
    export_result = export_gp5_and_musicxml(
        project_name=project_name,
        bpm=bpm,
        tuning_name=tuning_name,
        guitar_events=classified_guitar,
        guitar_rhythm_events=classified_rhythm,
        guitar_lead_events=classified_lead,
        guitar_additional_events=classified_additional,
        vocal_lead_events=classified_vocal_lead,
        vocal_co_lead_events=classified_vocal_co_lead,
        vocal_backing_events=classified_vocal_backing,
        extra_instrument_events=extra_classified,
        bass_events=classified_bass,
        drum_events=classified_drums,
        synth_events=classified_synth,
        output_gp5_path=gp5_file,
        output_musicxml_path=musicxml_file,
    )

    # 11. Build and validate visual_sync_map.json
    sync_map_file = os.path.join(output_dir, "visual_sync_map.json")
    sync_map = build_song_sync_map(
        project_name=project_name,
        bpm=bpm,
        musical_key=musical_key,
        tuning_name=tuning_name,
        master_audio_path=master_audio_path or "",
        gp5_tab_path=gp5_file,
        guitar_events=classified_guitar,
        guitar_rhythm_events=classified_rhythm,
        guitar_lead_events=classified_lead,
        guitar_additional_events=classified_additional,
        vocal_lead_events=classified_vocal_lead,
        vocal_co_lead_events=classified_vocal_co_lead,
        vocal_backing_events=classified_vocal_backing,
        extra_instrument_events=extra_classified,
        bass_events=classified_bass,
        drum_events=classified_drums,
        synth_events=classified_synth,
        output_sync_map_path=sync_map_file,
    )

    return {
        "status": "success",
        "project_name": project_name,
        "bpm": bpm,
        "musical_key": musical_key,
        "tuning": tuning_name,
        "multi_guitar_enabled": has_multi_guitar,
        "gp5_path": gp5_file,
        "musicxml_path": musicxml_file,
        "sync_map_path": sync_map_file,
        "total_events": len(sync_map.events),
        "tracks_count": export_result.get("tracks_count", 0),
        "track_names": export_result.get("track_names", []),
        "vocal_tracks_count": len([x for x in [classified_vocal_lead, classified_vocal_co_lead, classified_vocal_backing] if x]),
        "orchestral_tracks_count": len(extra_classified),
        "transcription_quality": "automatic_draft",
        "limitations": [
            "Pitch and onset tracking is algorithmic and requires human review; performance-level accuracy is not verified.",
            "A combined Demucs vocal stem is not split into lead, co-lead, or backing singers.",
            "A combined Demucs guitar stem is not split into rhythm, lead, or additional performances.",
        ],
    }


if __name__ == "__main__":
    mcp.run()


@mcp.tool()
def import_daw_midi(
    project_name: str,
    midi_path: str,
    tuning_name: Optional[str] = "Standard E",
    bpm: Optional[float] = None,
    musical_key: Optional[str] = None,
    output_dir: str = "workspace/output_tabs",
    master_audio_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Import verified polyphonic and multi-track MIDI (.mid) from DAW (SD3 Tracker, REAPER, Ableton, RipX).

    Executes anatomical Viterbi 4-fret solver, applies drop or standard tunings,
    and updates .gp5, .musicxml, and visual_sync_map.json with 100% DAW MIDI accuracy.
    """
    if import_verified_daw_midi is None:
        raise RuntimeError("daw_midi_importer module is not available.")
    return import_verified_daw_midi(
        project_name=project_name,
        midi_path=midi_path,
        tuning_name=tuning_name,
        bpm=bpm,
        musical_key=musical_key,
        output_dir=output_dir,
        master_audio_path=master_audio_path,
    )
