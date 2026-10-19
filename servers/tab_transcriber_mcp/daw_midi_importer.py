"""Module for importing verified MIDI (.mid) exported from DAWs (SD3 Tracker, REAPER, Ableton, RipX).

Parses polyphonic notes, drum hits, and multi-track arrangements, executes the biomechanical
Viterbi 4-fret solver, and produces production-grade Guitar Pro 5 (.gp5), MusicXML, and visual sync map.
"""

import os
import json
from typing import Dict, Any, List, Optional
import music21

try:
    from .fretboard_solver import (
        TUNINGS,
        BASS_TUNINGS,
        detect_guitar_tuning,
        detect_bass_tuning,
        viterbi_fretboard_solver,
        classify_playing_state,
        classify_vocal_events,
    )
    from .gp5_exporter import export_gp5_and_musicxml
    from .visual_prompt_mapper import build_song_sync_map
except ImportError:
    from fretboard_solver import (
        TUNINGS,
        BASS_TUNINGS,
        detect_guitar_tuning,
        detect_bass_tuning,
        viterbi_fretboard_solver,
        classify_playing_state,
        classify_vocal_events,
    )
    from gp5_exporter import export_gp5_and_musicxml
    from visual_prompt_mapper import build_song_sync_map


def _map_gm_drum_note_to_component(midi_note: int) -> str:
    """Map General MIDI drum note numbers to sync map components."""
    if midi_note in (35, 36):
        return "kick"
    elif midi_note in (38, 40):
        return "snare"
    elif midi_note in (42, 44):
        return "hi_hat"
    elif midi_note == 46:
        return "hi_hat_open"
    elif midi_note in (49, 55, 57):
        return "crash_cymbal"
    elif midi_note in (51, 53, 59):
        return "ride_cymbal"
    elif midi_note == 52:
        return "china_cymbal"
    elif midi_note in (41, 43, 45, 47, 48, 50):
        return "tom"
    return "percussion"


def import_verified_daw_midi(
    project_name: str,
    midi_path: str,
    tuning_name: Optional[str] = None,
    bpm: Optional[float] = None,
    musical_key: Optional[str] = None,
    output_dir: str = "workspace/output_tabs",
    master_audio_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse DAW-exported MIDI and generate authentic GP5 tablature and visual sync map."""
    if not os.path.exists(midi_path):
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")

    os.makedirs(output_dir, exist_ok=True)
    score = music21.converter.parse(midi_path)

    # 1. Determine BPM
    detected_bpm = 120.0
    tempos = score.flatten().getElementsByClass(music21.tempo.MetronomeMark)
    if tempos:
        detected_bpm = float(tempos[0].getQuarterBPM())
    final_bpm = float(bpm) if bpm and bpm > 0 else detected_bpm
    sec_per_quarter = 60.0 / final_bpm

    # 2. Categorize parts into instrument event lists
    drum_events: List[Dict[str, Any]] = []
    guitar_rhythm_events: List[Dict[str, Any]] = []
    guitar_lead_events: List[Dict[str, Any]] = []
    bass_events: List[Dict[str, Any]] = []
    vocal_events: List[Dict[str, Any]] = []
    extra_tracks_map: Dict[str, List[Dict[str, Any]]] = {}

    all_tonal_midi: List[int] = []

    for part in score.parts:
        part_name = str(part.partName or part.id or "").lower()
        is_drum_part = any(k in part_name for k in ["drum", "sd3", "superior", "ezdrummer", "percuss"])
        is_bass_part = "bass" in part_name
        is_vocal_part = any(k in part_name for k in ["vocal", "sing", "voice", "lead vox"])
        is_lead_guitar = any(k in part_name for k in ["lead", "solo"])
        is_rhythm_guitar = any(k in part_name for k in ["rhythm", "chug", "riff"])

        for el in part.flatten().notes:
            start_t = float(el.offset) * sec_per_quarter
            dur_t = max(0.08, float(el.quarterLength) * sec_per_quarter)
            end_t = start_t + dur_t

            if is_drum_part:
                pitches = [el.pitch.midi] if el.isNote else [p.midi for p in el.pitches]
                comps = [_map_gm_drum_note_to_component(p) for p in pitches]
                drum_events.append({
                    "start_time_sec": round(start_t, 3),
                    "end_time_sec": round(end_t, 3),
                    "duration_sec": round(dur_t, 3),
                    "components": comps,
                    "midi_notes": sorted(pitches),
                    "energy": 0.85,
                })
            else:
                pitches = [el.pitch.midi] if el.isNote else [p.midi for p in el.pitches]
                pitches = sorted(list(set(pitches)))
                all_tonal_midi.extend(pitches)

                ev = {
                    "start_time_sec": round(start_t, 3),
                    "end_time_sec": round(end_t, 3),
                    "duration_sec": round(dur_t, 3),
                    "root_midi": pitches[0],
                    "midi_notes": pitches,
                    "rms": 0.5,
                    "db": -12.0,
                }

                if is_bass_part:
                    bass_events.append(ev)
                elif is_vocal_part:
                    vocal_events.append(ev)
                elif is_lead_guitar:
                    guitar_lead_events.append(ev)
                elif is_rhythm_guitar:
                    guitar_rhythm_events.append(ev)
                else:
                    # Default: treat as guitar rhythm
                    guitar_rhythm_events.append(ev)

    # If only 1 track existed and was placed in rhythm, check if it's actually drums or bass
    if len(score.parts) == 1 and guitar_rhythm_events:
        avg_pitch = sum(all_tonal_midi) / len(all_tonal_midi) if all_tonal_midi else 50
        if any(ev.get("root_midi") in (36, 38, 42) for ev in guitar_rhythm_events) and avg_pitch < 45:
            # Likely a single-track drum MIDI (e.g. from SD3 Tracker)
            for ev in guitar_rhythm_events:
                drum_events.append({
                    "start_time_sec": ev["start_time_sec"],
                    "end_time_sec": ev["end_time_sec"],
                    "duration_sec": ev["duration_sec"],
                    "components": [_map_gm_drum_note_to_component(m) for m in ev["midi_notes"]],
                    "midi_notes": ev["midi_notes"],
                    "energy": 0.85,
                })
            guitar_rhythm_events = []

    # 3. Determine Guitar & Bass Tuning
    if tuning_name and tuning_name in TUNINGS:
        active_tuning_name = tuning_name
        open_strings = TUNINGS[tuning_name]
    else:
        lowest_note = min(all_tonal_midi) if all_tonal_midi else 40
        active_tuning_name, open_strings = detect_guitar_tuning(lowest_note)

    _, bass_open_strings = detect_bass_tuning(active_tuning_name)

    # 4. Determine Musical Key if not provided
    if not musical_key:
        # Estimate from tonal notes
        if all_tonal_midi:
            from servers.daw_studio_mcp.mashup_engine import NOTE_NAMES
            pitch_counts = [0] * 12
            for p in all_tonal_midi:
                pitch_counts[p % 12] += 1
            root_idx = int(pitch_counts.index(max(pitch_counts)))
            musical_key = f"{NOTE_NAMES[root_idx]} Minor"
        else:
            musical_key = "E Minor"

    # 5. Solve fretboard positions
    if guitar_rhythm_events:
        guitar_rhythm_events = viterbi_fretboard_solver(guitar_rhythm_events, open_strings, active_tuning_name)
        for ev in guitar_rhythm_events:
            state, is_trans, fx = classify_playing_state(ev, "guitar")
            ev["playing_state"] = state
            ev["is_transition"] = is_trans
            ev["suggested_fx"] = fx

    if guitar_lead_events:
        guitar_lead_events = viterbi_fretboard_solver(guitar_lead_events, open_strings, active_tuning_name)
        for ev in guitar_lead_events:
            state, is_trans, fx = classify_playing_state(ev, "guitar")
            ev["playing_state"] = state
            ev["is_transition"] = is_trans
            ev["suggested_fx"] = fx

    if bass_events:
        bass_events = viterbi_fretboard_solver(bass_events, bass_open_strings, active_tuning_name)
        for ev in bass_events:
            state, is_trans, fx = classify_playing_state(ev, "bass")
            ev["playing_state"] = state
            ev["is_transition"] = is_trans
            ev["suggested_fx"] = fx

    if drum_events:
        for ev in drum_events:
            state, is_trans, fx = classify_playing_state(ev, "drums")
            ev["playing_state"] = state
            ev["is_transition"] = is_trans
            ev["suggested_fx"] = fx

    # 6. Export to GP5 & MusicXML
    gp5_file = os.path.join(output_dir, f"{project_name}.gp5")
    musicxml_file = os.path.join(output_dir, f"{project_name}.musicxml")
    sync_map_file = os.path.join(output_dir, "visual_sync_map.json")

    export_res = export_gp5_and_musicxml(
        project_name=project_name,
        bpm=final_bpm,
        tuning_name=active_tuning_name,
        guitar_events=guitar_rhythm_events,
        guitar_rhythm_events=guitar_rhythm_events,
        guitar_lead_events=guitar_lead_events,
        guitar_additional_events=[],
        vocal_lead_events=vocal_events,
        vocal_co_lead_events=[],
        vocal_backing_events=[],
        extra_instrument_events=extra_tracks_map,
        bass_events=bass_events,
        drum_events=drum_events,
        synth_events=[],
        output_gp5_path=gp5_file,
        output_musicxml_path=musicxml_file,
    )

    # 7. Build Song Sync Map
    sync_map_res = build_song_sync_map(
        project_name=project_name,
        bpm=final_bpm,
        musical_key=musical_key,
        tuning_name=active_tuning_name,
        master_audio_path=master_audio_path or "",
        gp5_tab_path=gp5_file,
        guitar_events=guitar_rhythm_events,
        guitar_rhythm_events=guitar_rhythm_events,
        guitar_lead_events=guitar_lead_events,
        guitar_additional_events=[],
        vocal_lead_events=vocal_events,
        vocal_co_lead_events=[],
        vocal_backing_events=[],
        extra_instrument_events=extra_tracks_map,
        bass_events=bass_events,
        drum_events=drum_events,
        synth_events=[],
        output_sync_map_path=sync_map_file,
    )

    total_events = (
        len(guitar_rhythm_events)
        + len(guitar_lead_events)
        + len(bass_events)
        + len(drum_events)
        + len(vocal_events)
    )

    return {
        "status": "success",
        "mode": "daw_midi_import",
        "source_midi_path": midi_path,
        "project_name": project_name,
        "bpm": round(final_bpm, 2),
        "musical_key": musical_key,
        "tuning": active_tuning_name,
        "gp5_path": gp5_file,
        "musicxml_path": musicxml_file,
        "sync_map_path": sync_map_file,
        "total_events": total_events,
        "tracks_count": export_res.get("tracks_count", 0),
        "track_names": export_res.get("track_names", []),
    }
