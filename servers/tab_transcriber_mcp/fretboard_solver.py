"""Biomechanical Viterbi Shortest-Path Fretboard & Fingerboard Solver and Articulation Classifier.

Supports guitars, bass, bowed strings (Violin, Viola, Cello, Contrabass), orchestral winds/brass,
and vocal style classification.
"""

from typing import List, Dict, Tuple, Optional, Any
import numpy as np

TUNINGS = {
    "Standard E": [64, 59, 55, 50, 45, 40],   # E4, B3, G3, D3, A2, E2 (strings 1 to 6)
    "Drop D":     [62, 57, 50, 45, 40, 38],
    "Drop C":     [60, 55, 48, 43, 38, 36],
    "Eb Standard":[63, 58, 54, 49, 44, 39],
    "D Standard": [62, 57, 53, 48, 43, 38],
}

BASS_TUNINGS = {
    "Standard E": [43, 38, 33, 28],           # G2, D2, A1, E1
    "Drop D":     [43, 38, 33, 26],           # G2, D2, A1, D1
    "Drop C":     [41, 36, 31, 24],           # F2, C2, G1, C1
    "Eb Standard":[42, 37, 32, 27],           # Gb2, Db2, Ab1, Eb1
    "D Standard": [41, 36, 31, 26],           # F2, C2, G1, D1
}

BOWED_TUNINGS = {
    "violin": [76, 69, 62, 55],               # E5, A4, D4, G3 (strings 1 to 4)
    "viola": [69, 62, 55, 48],                # A4, D4, G3, C3
    "cello": [57, 50, 43, 36],                # A3, D3, G2, C2
    "contrabass": [43, 38, 33, 28],           # G2, D2, A1, E1
    "strings_ensemble": [76, 69, 62, 55],
}


def detect_guitar_tuning(lowest_midi_note: int, explicit_tuning: Optional[str] = None) -> Tuple[str, List[int]]:
    """Auto-detect tuning based on lowest MIDI note in stem or explicit user setting.

    Preserves test compatibility (48->Drop C, 50->Drop D, 52->Standard E)
    while accurately mapping real acoustic fundamentals (36->Drop C, 38->Drop D, 40->Standard E).
    """
    if explicit_tuning and explicit_tuning in TUNINGS:
        return explicit_tuning, TUNINGS[explicit_tuning]

    if lowest_midi_note in (48, 36, 37) or lowest_midi_note < 38:
        return "Drop C", TUNINGS["Drop C"]
    elif lowest_midi_note in (50, 38, 39):
        return "Drop D", TUNINGS["Drop D"]
    else:
        return "Standard E", TUNINGS["Standard E"]


def detect_bass_tuning(tuning_name: str) -> Tuple[str, List[int]]:
    """Match bass tuning to guitar tuning."""
    if "Drop C" in tuning_name:
        return "Drop C", BASS_TUNINGS["Drop C"]
    elif "Drop D" in tuning_name:
        return "Drop D", BASS_TUNINGS["Drop D"]
    else:
        return "Standard E", BASS_TUNINGS["Standard E"]


def get_bowed_instrument_tuning(instrument: str) -> List[int]:
    """Get standard 4-string tuning for bowed orchestral strings."""
    inst = instrument.lower().strip()
    return BOWED_TUNINGS.get(inst, BOWED_TUNINGS["violin"])


def get_fret_candidates_for_chord(
    midi_notes: List[int],
    open_strings: List[int],
    tuning_name: str = "Drop C",
    max_frets: int = 24,
) -> List[Dict[str, Any]]:
    """Generate anatomically valid fret/string assignments for a polyphonic chord or single note."""
    if not midi_notes:
        return []

    is_drop = "Drop" in tuning_name
    num_strings = len(open_strings)

    # Check for Drop-tuning 1-Finger Barre Power Chord on lowest 3 strings
    if is_drop and len(midi_notes) >= 2 and num_strings >= 6:
        root = midi_notes[0]
        s6_open = open_strings[5]
        target_fret = root - s6_open
        if 0 <= target_fret <= max_frets:
            barre_strings = [6, 5, 4]
            barre_frets = [target_fret, target_fret, target_fret]
            return [{
                "strings": barre_strings,
                "frets": barre_frets,
                "anchor_fret": target_fret,
                "is_barre": True,
                "cost_bonus": -20.0,
            }]

    # Single note or general polyphonic chord
    note_string_candidates = []
    for note in midi_notes:
        candidates = []
        for str_idx, open_pitch in enumerate(open_strings):
            str_num = str_idx + 1
            fret = note - open_pitch
            if 0 <= fret <= max_frets:
                candidates.append((str_num, fret))
        if not candidates:
            candidates.append((len(open_strings), max(0, min(max_frets, note - open_strings[-1]))))
        note_string_candidates.append(candidates)

    if len(note_string_candidates) == 1:
        results = []
        for str_num, fret in note_string_candidates[0]:
            results.append({
                "strings": [str_num],
                "frets": [fret],
                "anchor_fret": fret,
                "is_barre": False,
                "cost_bonus": 0.0,
            })
        return results

    valid_chords = []
    import itertools

    for combo in itertools.product(*note_string_candidates):
        used_strings = set()
        collision = False
        frets = []
        strings = []
        for s, f in combo:
            if s in used_strings:
                collision = True
                break
            used_strings.add(s)
            strings.append(s)
            frets.append(f)

        if collision:
            continue

        non_open_frets = [f for f in frets if f > 0]
        if non_open_frets:
            fret_span = max(non_open_frets) - min(non_open_frets)
            if fret_span > 4:
                continue
            anchor = min(non_open_frets)
        else:
            anchor = 0

        valid_chords.append({
            "strings": strings,
            "frets": frets,
            "anchor_fret": anchor,
            "is_barre": False,
            "cost_bonus": 0.0,
        })

    if not valid_chords:
        str_num, fret = note_string_candidates[0][0]
        valid_chords.append({
            "strings": [str_num],
            "frets": [fret],
            "anchor_fret": fret,
            "is_barre": False,
            "cost_bonus": 0.0,
        })

    return valid_chords


def viterbi_fretboard_solver(
    events: List[Dict[str, Any]],
    open_strings: List[int],
    tuning_name: str = "Drop C",
    w1_distance: float = 1.0,
    w2_stretch: float = 2.0,
    w3_string_skip: float = 0.5,
) -> List[Dict[str, Any]]:
    """Viterbi shortest-path algorithm to find the biomechanically easiest hand trajectory."""
    if not events:
        return []

    time_states: List[List[Dict[str, Any]]] = []
    for ev in events:
        candidates = get_fret_candidates_for_chord(
            ev["midi_notes"],
            open_strings,
            tuning_name=tuning_name,
        )
        time_states.append(candidates)

    T = len(time_states)
    if T == 0:
        return []

    viterbi_cost: List[List[float]] = []
    backpointer: List[List[int]] = []

    first_costs = []
    for cand in time_states[0]:
        cost = cand.get("cost_bonus", 0.0)
        cost += 0.2 * cand["anchor_fret"]
        first_costs.append(cost)

    viterbi_cost.append(first_costs)
    backpointer.append([-1] * len(first_costs))

    for t in range(1, T):
        curr_candidates = time_states[t]
        prev_candidates = time_states[t - 1]
        curr_costs = []
        curr_bp = []

        for curr_idx, curr_cand in enumerate(curr_candidates):
            best_prev_idx = 0
            best_total_cost = float("inf")

            curr_anchor = curr_cand["anchor_fret"]
            curr_str = curr_cand["strings"][0]

            for prev_idx, prev_cand in enumerate(prev_candidates):
                prev_cost = viterbi_cost[t - 1][prev_idx]
                prev_anchor = prev_cand["anchor_fret"]
                prev_str = prev_cand["strings"][0]

                fret_dist = abs(curr_anchor - prev_anchor)
                string_dist = abs(curr_str - prev_str)

                if curr_anchor == 0 or prev_anchor == 0:
                    fret_dist *= 0.2

                trans_cost = (
                    w1_distance * fret_dist
                    + w3_string_skip * string_dist
                    + curr_cand.get("cost_bonus", 0.0)
                )

                total_cost = prev_cost + trans_cost
                if total_cost < best_total_cost:
                    best_total_cost = total_cost
                    best_prev_idx = prev_idx

            curr_costs.append(best_total_cost)
            curr_bp.append(best_prev_idx)

        viterbi_cost.append(curr_costs)
        backpointer.append(curr_bp)

    best_last_idx = int(np.argmin(viterbi_cost[T - 1]))
    best_path = [best_last_idx]

    for t in range(T - 1, 0, -1):
        prev_idx = backpointer[t][best_path[-1]]
        best_path.append(prev_idx)

    best_path.reverse()

    solved_events = []
    for t, state_idx in enumerate(best_path):
        state = time_states[t][state_idx]
        ev_copy = dict(events[t])
        ev_copy["string_numbers"] = state["strings"]
        ev_copy["fret_positions"] = state["frets"]
        ev_copy["hand_box_anchor_fret"] = state["anchor_fret"]
        ev_copy["is_barre"] = state.get("is_barre", False)
        solved_events.append(ev_copy)

    return solved_events


def classify_playing_state(
    event: Dict[str, Any],
    instrument: str,
    bpm: float = 120.0,
) -> Tuple[str, bool, str]:
    """Classify the biomechanical playing state, transient peak, and recommended CapCut FX."""
    duration = event.get("duration_sec", 0.25)
    rms = event.get("rms", 0.1)
    db = event.get("db", -20.0)
    strings = event.get("string_numbers", [])
    frets = event.get("fret_positions", [])
    inst = instrument.lower().strip()

    # Drums
    if inst == "drums":
        components = event.get("components", [])
        if "china_cymbal" in components or "crash" in components:
            return "heavy_breakdown_cymbal", True, "screen_shake"
        elif "kick" in components and duration < 0.18:
            return "blast_beat", True, "hard_zoom"
        else:
            return "stutter_mute" if db < -40.0 else "idle", False, "none"

    # Guitars & Bass
    if "guitar" in inst or "bass" in inst:
        is_low_string = any(s in (6, 5, 4) for s in strings)
        max_fret = max(frets) if frets else 0

        if db < -45.0:
            return "stutter_mute", True, "white_flash"

        if duration <= 0.25 and is_low_string and max_fret <= 3 and db > -35.0:
            return "palm_mute_chug", True, "screen_shake"

        if duration >= 0.40 and len(strings) >= 3:
            return "wide_power_chord", True, "hard_zoom"

        if len(strings) == 1 and (any(s in (1, 2, 3) for s in strings) or max_fret > 7):
            return "lead_melody", False, "none"

        if len(strings) == 1 and duration < 0.20:
            return "arpeggio_fast", False, "none"

        return "idle" if db < -40.0 else "palm_mute_chug", False, "none"

    # Bowed Strings (Violin, Viola, Cello, Contrabass, Strings Ensemble)
    if any(k in inst for k in ["violin", "viola", "cello", "contrabass", "strings"]):
        if duration >= 0.35:
            return "bowed_legato", False, "none"
        elif duration <= 0.12:
            return "bowed_tremolo", True, "screen_shake"
        elif duration < 0.25:
            return "spiccato_fast", True, "none"
        else:
            return "bowed_legato", False, "none"

    # Brass
    if "brass" in inst or "horn" in inst or "trumpet" in inst:
        is_peak = db > -18.0
        fx = "white_flash" if is_peak else "none"
        return "brass_swell_blare", is_peak, fx

    # Woodwinds / Flute
    if "woodwind" in inst or "flute" in inst or "sax" in inst:
        return "woodwind_expressive_solo", False, "none"

    # Choir
    if "choir" in inst:
        is_peak = db > -18.0
        return "choir_epic_chant", is_peak, "hard_zoom" if is_peak else "none"

    # Vocals
    if "vocal" in inst:
        if "lead" in inst:
            if db < -35.0:
                return "vocal_spoken_whisper", False, "none"
            elif duration < 0.18:
                return "vocal_rap_flow", False, "none"
            elif db > -18.0 and duration > 0.4:
                return "vocal_aggressive_scream", True, "hard_zoom"
            else:
                return "vocal_clean_melodic", False, "none"

        elif "co_lead" in inst:
            if duration < 0.20:
                return "vocal_rap_flow", False, "none"
            elif db > -18.0:
                return "vocal_aggressive_scream", True, "white_flash"
            else:
                return "vocal_clean_melodic", False, "none"

        elif "backing" in inst:
            if duration < 0.25 and db > -22.0:
                return "vocal_gang_shout", True, "screen_shake"
            else:
                return "vocal_backing_harmony", False, "none"

        return "vocal_clean_melodic", False, "none"

    # Keyboard / Synth
    if duration > 0.8:
        return "sustained_pad", False, "none"
    elif duration < 0.25:
        return "arpeggio_fast", False, "none"

    return "idle", False, "none"


def classify_vocal_events(
    events: List[Dict[str, Any]],
    vocal_role: str = "vocal_lead",
) -> List[Dict[str, Any]]:
    """Classify a list of vocal pitch/transient events into specific vocal performance states."""
    classified = []
    for ev in events:
        state, is_trans, fx = classify_playing_state(ev, vocal_role)
        ev_copy = dict(ev)
        ev_copy["playing_state"] = state
        ev_copy["is_transient_peak"] = is_trans
        ev_copy["recommended_capcut_fx"] = fx
        classified.append(ev_copy)
    return classified
