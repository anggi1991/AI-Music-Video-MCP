"""Multi-Track Guitar Pro 5 (.gp5) and MusicXML Exporter.

Supports Band, Multi-Guitar, Bowed Strings (Violin, Viola, Cello, Contrabass),
Orchestral Ensembles (Brass, Woodwinds, Choir), and Multi-Vocal melodic tracks.
"""

import os
import xml.etree.ElementTree as ET
import math
from typing import List, Dict, Any, Optional
import numpy as np
import guitarpro as gp
from music21 import stream, metadata, note as m21_note, chord as m21_chord, meter as m21_meter, tempo as m21_tempo

try:
    from .fretboard_solver import TUNINGS, BASS_TUNINGS, BOWED_TUNINGS
except ImportError:
    from fretboard_solver import TUNINGS, BASS_TUNINGS, BOWED_TUNINGS

# General MIDI (GM) Program Numbers
GM_PROGRAMS = {
    "acoustic_guitar": 25,
    "guitar": 29,             # Overdriven Guitar
    "guitar_rhythm": 30,      # Distortion Guitar
    "guitar_lead": 29,        # Overdriven Guitar
    "guitar_additional": 27,  # Clean Electric
    "bass": 33,               # Electric Bass (finger)
    "violin": 40,
    "viola": 41,
    "cello": 42,
    "contrabass": 43,
    "strings_ensemble": 48,
    "harp": 46,
    "choir": 52,
    "vocal_lead": 53,         # Voice Oohs
    "vocal_co_lead": 54,      # Synth Voice
    "vocal_backing": 52,      # Choir Aahs
    "vocals": 53,
    "brass": 61,              # Brass Section
    "woodwinds": 73,          # Flute
    "flute": 73,
    "saxophone": 66,
    "keyboard": 0,            # Acoustic Grand Piano
    "synth": 80,              # Lead 1 (square)
}


def duration_sec_to_gp_value(sec: float, bpm: float) -> int:
    """Convert note duration in seconds to closest standard Guitar Pro duration value.

    (1 = whole, 2 = half, 4 = quarter, 8 = eighth, 16 = sixteenth, 32 = thirty-second)
    """
    quarter_sec = 60.0 / bpm
    ratio = sec / quarter_sec
    if ratio >= 3.0:
        return 1
    elif ratio >= 1.5:
        return 2
    elif ratio >= 0.75:
        return 4
    elif ratio >= 0.35:
        return 8
    elif ratio >= 0.18:
        return 16
    else:
        return 32


def export_gp5_and_musicxml(
    project_name: str,
    bpm: float,
    tuning_name: str,
    guitar_events: Optional[List[Dict[str, Any]]] = None,
    bass_events: Optional[List[Dict[str, Any]]] = None,
    drum_events: Optional[List[Dict[str, Any]]] = None,
    synth_events: Optional[List[Dict[str, Any]]] = None,
    output_gp5_path: str = "song.gp5",
    output_musicxml_path: Optional[str] = None,
    guitar_rhythm_events: Optional[List[Dict[str, Any]]] = None,
    guitar_lead_events: Optional[List[Dict[str, Any]]] = None,
    guitar_additional_events: Optional[List[Dict[str, Any]]] = None,
    vocal_lead_events: Optional[List[Dict[str, Any]]] = None,
    vocal_co_lead_events: Optional[List[Dict[str, Any]]] = None,
    vocal_backing_events: Optional[List[Dict[str, Any]]] = None,
    extra_instrument_events: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Export Multi-Track Guitar Pro 5 (.gp5) file and MusicXML file.

    Supports Band, Multi-Guitar, Bowed Strings, Orchestral, and Multi-Vocal tracks.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_gp5_path)), exist_ok=True)

    guitar_events = guitar_events or []
    bass_events = bass_events or []
    drum_events = drum_events or []
    synth_events = synth_events or []
    guitar_rhythm_events = guitar_rhythm_events or []
    guitar_lead_events = guitar_lead_events or []
    guitar_additional_events = guitar_additional_events or []
    vocal_lead_events = vocal_lead_events or []
    vocal_co_lead_events = vocal_co_lead_events or []
    vocal_backing_events = vocal_backing_events or []
    extra_instrument_events = extra_instrument_events or {}

    has_multi_guitar = bool(guitar_rhythm_events or guitar_lead_events or guitar_additional_events)
    has_vocals = bool(vocal_lead_events or vocal_co_lead_events or vocal_backing_events)

    # 1. Initialize Guitar Pro 5 Song
    song = gp.Song()
    song.tracks.clear()
    song.measureHeaders.clear()
    song.title = project_name
    song.tempo = int(round(bpm))

    # Collect all events to determine total duration
    all_events = (
        guitar_events
        + guitar_rhythm_events
        + guitar_lead_events
        + guitar_additional_events
        + vocal_lead_events
        + vocal_co_lead_events
        + vocal_backing_events
        + bass_events
        + drum_events
        + synth_events
    )
    for extra_evs in extra_instrument_events.values():
        all_events.extend(extra_evs)

    max_time = max([e.get("end_time_sec", 0.0) for e in all_events], default=4.0)
    bar_duration = (60.0 / bpm) * 4.0  # 4/4 bar
    num_measures = max(1, int(np.ceil(max_time / bar_duration)))

    # Add measure headers
    for m_idx in range(num_measures):
        header = gp.MeasureHeader()
        header.number = m_idx + 1
        header.timeSignature.numerator = 4
        header.timeSignature.denominator.value = 4
        song.measureHeaders.append(header)

    guitar_tuning = TUNINGS.get(tuning_name, TUNINGS["Drop C"])
    bass_tuning = BASS_TUNINGS.get(tuning_name, BASS_TUNINGS["Drop C"])

    channel_counter = [0]

    def create_fretted_track(name: str, tuning_vals: List[int], program: int) -> gp.Track:
        t = gp.Track(song)
        t.name = name
        t.strings = [
            gp.GuitarString(number=i + 1, value=val) for i, val in enumerate(tuning_vals)
        ]
        slot = channel_counter[0]
        c_num = slot * 2
        if c_num in (8, 9, 10):
            slot += 2
            c_num = slot * 2
        channel_counter[0] = slot + 1

        ch = gp.MidiChannel()
        ch.channel = c_num % 64
        ch.effectChannel = (c_num + 1) % 64
        ch.instrument = program
        t.channel = ch
        return t

    def create_drum_track() -> gp.Track:
        t = gp.Track(song)
        t.name = "Drums"
        t.isPercussionTrack = True
        ch = gp.MidiChannel()
        ch.channel = 9
        ch.effectChannel = 9
        ch.instrument = 0
        t.channel = ch
        return t

    tracks_to_process = []

    # 1. Vocals (if present)
    if vocal_lead_events:
        tracks_to_process.append((
            create_fretted_track("Lead Vocals", [64, 59, 55, 50, 45, 40], GM_PROGRAMS["vocal_lead"]),
            vocal_lead_events,
            "vocal"
        ))
    if vocal_co_lead_events:
        tracks_to_process.append((
            create_fretted_track("Co-Lead Vocals", [64, 59, 55, 50, 45, 40], GM_PROGRAMS["vocal_co_lead"]),
            vocal_co_lead_events,
            "vocal"
        ))
    if vocal_backing_events:
        tracks_to_process.append((
            create_fretted_track("Backing Vocals", [64, 59, 55, 50, 45, 40], GM_PROGRAMS["vocal_backing"]),
            vocal_backing_events,
            "vocal"
        ))

    # 2. Guitars
    if has_multi_guitar:
        tracks_to_process.append((
            create_fretted_track("Rhythm Guitar", guitar_tuning, GM_PROGRAMS["guitar_rhythm"]),
            guitar_rhythm_events,
            "guitar"
        ))
        tracks_to_process.append((
            create_fretted_track("Lead Guitar", guitar_tuning, GM_PROGRAMS["guitar_lead"]),
            guitar_lead_events,
            "guitar"
        ))
        tracks_to_process.append((
            create_fretted_track("Additional Guitar", guitar_tuning, GM_PROGRAMS["guitar_additional"]),
            guitar_additional_events,
            "guitar"
        ))
    elif guitar_events:
        tracks_to_process.append((
            create_fretted_track("Electric Guitar", guitar_tuning, GM_PROGRAMS["guitar"]),
            guitar_events,
            "guitar"
        ))

    # 3. Bowed Strings & Orchestral (extra_instrument_events)
    for inst_name, events in extra_instrument_events.items():
        if not events:
            continue
        key_inst = inst_name.lower()
        if key_inst in BOWED_TUNINGS:
            bowed_tun = BOWED_TUNINGS[key_inst]
            prog = GM_PROGRAMS.get(key_inst, 40)
            tracks_to_process.append((
                create_fretted_track(inst_name.capitalize(), bowed_tun, prog),
                events,
                "bowed"
            ))
        else:
            prog = GM_PROGRAMS.get(key_inst, 0)
            tracks_to_process.append((
                create_fretted_track(inst_name.capitalize(), [64, 59, 55, 50, 45, 40], prog),
                events,
                "orchestral"
            ))

    # 4. Bass
    if bass_events:
        tracks_to_process.append((
            create_fretted_track("Electric Bass", bass_tuning, GM_PROGRAMS["bass"]),
            bass_events,
            "bass"
        ))

    # 5. Drums
    if drum_events:
        tracks_to_process.append((
            create_drum_track(),
            drum_events,
            "drums"
        ))

    # 6. Keyboard / Synth
    if synth_events:
        tracks_to_process.append((
            create_fretted_track("Keyboard/Synth", [64, 59, 55, 50, 45, 40], GM_PROGRAMS["synth"]),
            synth_events,
            "synth"
        ))

    # Ensure at least 1 track exists
    if not tracks_to_process:
        tracks_to_process.append((
            create_fretted_track("Electric Guitar", guitar_tuning, GM_PROGRAMS["guitar"]),
            [],
            "guitar"
        ))

    # Place events on the beat nearest their measured onset. The previous
    # implementation advanced one beat per detected event, stretching songs
    # with many onsets far beyond the source duration.
    for track, events, inst_type in tracks_to_process:
        # Track(song) pre-populates measures from the existing headers. Clear
        # those before building the explicit timeline or GP5 doubles every bar.
        track.measures.clear()
        events_by_beat: Dict[int, List[Dict[str, Any]]] = {}
        quarter_sec = 60.0 / bpm
        for ev in events:
            beat_index = max(0, int(round(float(ev.get("start_time_sec", 0.0)) / quarter_sec)))
            if beat_index < num_measures * 4:
                # A single source can produce several onset candidates inside
                # one quarter note. The current GP5 export grid cannot encode
                # their separate timing, so retain the earliest candidate in
                # each cell rather than stacking unrelated notes as a chord.
                events_by_beat.setdefault(beat_index, [ev])

        for m_idx in range(num_measures):
            m_header = song.measureHeaders[m_idx]
            measure = gp.Measure(track, m_header)
            voice = measure.voices[0]

            for beat_i in range(4):
                beat = gp.Beat(voice)
                beat.duration.value = 4

                beat_index = m_idx * 4 + beat_i
                beat_events = events_by_beat.get(beat_index, [])
                if beat_events:
                    # Keep a quarter-note grid so the GP5 timeline remains
                    # bounded to the source duration; onset spacing is
                    # quantized to the nearest quarter note.
                    used_strings = set()
                    if inst_type in ("guitar", "bass", "bowed"):
                        for ev in beat_events:
                            str_nums = ev.get("string_numbers", [len(track.strings)])
                            frets = ev.get("fret_positions", [0])
                            is_pm = ev.get("playing_state") == "palm_mute_chug"
                            for s_num, fret_val in zip(str_nums, frets):
                                s_int = int(s_num)
                                if 1 <= s_int <= len(track.strings) and s_int not in used_strings:
                                    used_strings.add(s_int)
                                    note = gp.Note(beat)
                                    note.value = max(0, min(24, int(fret_val)))
                                    note.string = s_int
                                    note.type = gp.NoteType.normal
                                    if is_pm:
                                        note.effect.palmMute = True
                                    beat.notes.append(note)

                    elif inst_type == "drums":
                        COMPONENT_MAP = {
                            "kick": (36, 6),
                            "bass_drum": (36, 6),
                            "snare": (38, 3),
                            "hihat": (42, 1),
                            "hi_hat": (42, 1),
                            "cymbal": (49, 1),
                            "crash": (49, 1),
                            "china": (52, 1),
                            "china_cymbal": (52, 1),
                            "tom": (45, 4),
                        }
                        for ev in beat_events:
                            drum_items = []
                            m_notes = ev.get("midi_notes", [])
                            if m_notes:
                                for mn in m_notes:
                                    s_val = 6 if mn in (35, 36) else (3 if mn in (38, 40) else (1 if mn in (42, 44, 46, 49, 51, 52) else 4))
                                    drum_items.append((int(mn), s_val))
                            elif ev.get("drum_components"):
                                for c in ev["drum_components"]:
                                    drum_items.append(COMPONENT_MAP.get(c, (38, 3)))
                            if not drum_items:
                                drum_items = [(38, 3)]

                            for m_note, s_num in drum_items:
                                if s_num not in used_strings and 1 <= s_num <= len(track.strings):
                                    used_strings.add(s_num)
                                    note = gp.Note(beat)
                                    note.value = int(m_note)
                                    note.string = int(s_num)
                                    note.type = gp.NoteType.normal
                                    beat.notes.append(note)

                    elif inst_type in ("synth", "vocal", "orchestral"):
                        for ev in beat_events:
                            midi_notes = ev.get("midi_notes") or ([ev["root_midi"]] if "root_midi" in ev else [])
                            if not midi_notes:
                                midi_notes = [60]
                            for idx_note, m_note in enumerate(midi_notes[:4]):
                                s_int = min(len(track.strings), idx_note + 1)
                                if s_int not in used_strings:
                                    used_strings.add(s_int)
                                    note = gp.Note(beat)
                                    note.value = max(0, min(24, (int(m_note) - 60) % 24))
                                    note.string = s_int
                                    note.type = gp.NoteType.normal
                                    beat.notes.append(note)

                    if beat.notes:
                        beat.status = gp.BeatStatus.normal
                    else:
                        beat.status = gp.BeatStatus.rest
                        note = gp.Note(beat)
                        note.value = 0
                        note.string = 1
                        note.type = gp.NoteType.rest
                        beat.notes.append(note)
                else:
                    beat.status = gp.BeatStatus.rest
                    note = gp.Note(beat)
                    note.value = 0
                    note.string = 1
                    note.type = gp.NoteType.rest
                    beat.notes.append(note)
                voice.beats.append(beat)

            track.measures.append(measure)

        song.tracks.append(track)

    # Write GP5 file
    gp.write(song, output_gp5_path)

    # 2. Export MusicXML
    if output_musicxml_path is None:
        base, _ = os.path.splitext(output_gp5_path)
        output_musicxml_path = f"{base}.musicxml"

    VALID_QLS = [0.25, 0.5, 1.0, 2.0, 4.0]
    score = stream.Score()
    score.metadata = metadata.Metadata()
    score.metadata.title = project_name

    for track, events, inst_type in tracks_to_process[:8]:
        if inst_type == "drums":
            continue
        part = stream.Part()
        part.id = track.name
        part.append(m21_meter.TimeSignature("4/4"))
        part.append(m21_tempo.MetronomeMark(number=int(bpm)))

        quarter_sec = 60.0 / bpm
        for ev in events:
            midi_notes = ev.get("midi_notes") or ([ev["root_midi"]] if "root_midi" in ev else [])
            if not midi_notes:
                str_nums = ev.get("string_numbers", [])
                frets = ev.get("fret_positions", [])
                if str_nums and frets and track.strings:
                    calc_midi = []
                    for s_num, fret_val in zip(str_nums, frets):
                        s_idx = int(s_num) - 1
                        if 0 <= s_idx < len(track.strings):
                            open_val = track.strings[s_idx].value
                            calc_midi.append(open_val + int(fret_val))
                    midi_notes = calc_midi
            if not midi_notes:
                continue
            ql_raw = max(0.25, min(4.0, ev.get("duration_sec", 0.5) / (60.0 / bpm)))
            ql = min(VALID_QLS, key=lambda x: abs(x - ql_raw))
            offset = max(0.0, float(ev.get("start_time_sec", 0.0)) / quarter_sec)
            if len(midi_notes) == 1:
                n = m21_note.Note(midi_notes[0], quarterLength=ql)
                part.insert(offset, n)
            elif len(midi_notes) > 1:
                c = m21_chord.Chord(midi_notes, quarterLength=ql)
                part.insert(offset, c)

        # Keep empty parts too, so a valid MusicXML draft is still emitted when
        # automatic pitch tracking finds no confident notes in a short stem.
        score.append(part)

    try:
        score.write("musicxml", fp=output_musicxml_path)
    except Exception as exc:
        # Preserve an honest, valid empty draft when no notes were detected or
        # music21 cannot serialize an otherwise empty score.
        if not os.path.exists(output_musicxml_path):
            root = ET.Element("score-partwise", version="3.1")
            work = ET.SubElement(root, "work")
            ET.SubElement(work, "work-title").text = project_name
            part_list = ET.SubElement(root, "part-list")
            score_part = ET.SubElement(part_list, "score-part", {"id": "P1"})
            ET.SubElement(score_part, "part-name").text = "Automatic transcription draft"
            part = ET.SubElement(root, "part", {"id": "P1"})
            measure = ET.SubElement(part, "measure", {"number": "1"})
            attributes = ET.SubElement(measure, "attributes")
            ET.SubElement(attributes, "divisions").text = "1"
            time = ET.SubElement(attributes, "time")
            ET.SubElement(time, "beats").text = "4"
            ET.SubElement(time, "beat-type").text = "4"
            note_el = ET.SubElement(measure, "note")
            ET.SubElement(note_el, "rest")
            ET.SubElement(note_el, "duration").text = "4"
            ET.SubElement(note_el, "voice").text = "1"
            ET.SubElement(note_el, "type").text = "whole"
            ET.indent(root, space="  ")
            ET.ElementTree(root).write(output_musicxml_path, encoding="utf-8", xml_declaration=True)

    return {
        "gp5_path": output_gp5_path,
        "musicxml_path": output_musicxml_path,
        "measures_count": num_measures,
        "tracks_count": len(song.tracks),
        "track_names": [t.name for t in song.tracks],
    }
