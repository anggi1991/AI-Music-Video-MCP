"""Generates Nano Banana 2.1 keyframe prompts, Veo motion prompts, and validates visual_sync_map.json.

Supports Rock/Metal band, Multi-Guitar, Bowed Strings (Violin, Viola, Cello),
Orchestral sections (Brass, Woodwinds, Choir), and Multi-Vocalist roles.
"""

from typing import List, Dict, Any, Optional
from shared_schemas.sync_map_schema import InstrumentEvent, SongSyncMap


def generate_nano_banana_prompt(
    instrument: str,
    playing_state: str,
    tuning: str,
    string_nums: List[int],
    fret_pos: List[int],
    anchor_fret: int,
    drum_components: List[str],
) -> str:
    """Generate anatomically accurate Nano Banana 2.1 keyframe generation prompt."""
    inst = instrument.lower().strip()

    # 1. Vocals
    if inst in ("vocal_lead", "vocals"):
        if playing_state == "vocal_aggressive_scream":
            return (
                "Hyper-realistic 8k cinematic shot of intense lead vocalist screaming into Shure SM7B microphone, "
                "neck veins bulging, mouth wide open with emotional raw grit, stage strobe backlighting, sweat flying."
            )
        elif playing_state == "vocal_rap_flow":
            return (
                "Dynamic cinematic close-up of charismatic frontman delivering rapid rap flow into wireless handheld microphone, "
                "expressive hand gestures, sharp urban stage lighting, shallow depth of field, 8k resolution."
            )
        elif playing_state == "vocal_spoken_whisper":
            return (
                "Intimate cinematic profile shot of singer whispering softly into studio condenser microphone with pop filter, "
                "moody dark blue rim lighting, atmospheric dust motes, cinematic 85mm lens."
            )
        else:
            return (
                "Epic cinematic shot of lead singer holding vintage stage microphone, eyes closed in deep melodic passion, "
                "golden arena spotlight cutting through concert haze, highly detailed photorealistic portrait."
            )

    elif inst == "vocal_co_lead":
        if playing_state == "vocal_aggressive_scream":
            return (
                "Aggressive close-up of secondary co-lead vocalist screaming in unison with stage pyrotechnics, "
                "ferocious facial expression, holding microphone with both hands, dramatic high-contrast red lighting."
            )
        else:
            return (
                "Cinematic shot of secondary co-lead vocalist harmonizing into stage mic, energetic posture leaning forward, "
                "concert crowd silhouettes in background, vibrant neon stadium lights."
            )

    elif inst == "vocal_backing":
        if playing_state == "vocal_gang_shout":
            return (
                "Energetic wide shot of backing vocalists leaning into shared microphone doing explosive gang shout, "
                "fists raised, concert arena smoke, intense flash lighting."
            )
        else:
            return (
                "Cinematic shot of backing vocalists singing harmony parts at studio microphone stands, "
                "warm amber studio wash lighting, professional headphones on."
            )

    # 2. Guitars
    elif inst in ("guitar", "guitar_rhythm"):
        if playing_state == "palm_mute_chug":
            return (
                f"Hyper-realistic 8k cinematic macro shot of rhythm guitarist hands in {tuning} tuning. "
                f"Left hand anchored at fret {anchor_fret}, pressing string {string_nums} at fret {fret_pos}. "
                f"Right hand firmly anchored on the bridge saddles in tight palm-mute posture with carbon pick, "
                f"stage smoke, dramatic rim lighting, sweat droplets on guitar body, 35mm lens."
            )
        elif playing_state == "wide_power_chord":
            return (
                f"Epic cinematic wide-angle shot of rhythm guitarist fretboard in {tuning} tuning. "
                f"Left hand barred across frets {fret_pos} on strings {string_nums} in tight 4-fret hand box, "
                f"right hand executing wide downstroke strum across strings, "
                f"stadium concert lighting, neon lens flare, photorealistic."
            )
        else:
            return (
                f"Cinematic close-up of rhythm guitarist hands holding electric guitar in {tuning} tuning, "
                f"left hand positioned at fret {anchor_fret}, right hand relaxed over low strings, dark industrial backdrop."
            )

    elif inst == "guitar_lead":
        high_fret = max(fret_pos) if fret_pos else 14
        return (
            f"Breathtaking 8k macro close-up of lead guitarist executing screaming solo at fret {high_fret} in {tuning} tuning. "
            f"Fingers arched in precise classical shred posture, dramatic index-finger vibrato bending string {string_nums}, "
            f"intense spotlight from above cutting through arena concert haze, motion blur on pick, ultra-sharp detail."
        )

    elif inst == "guitar_additional":
        return (
            f"Atmospheric cinematic shot of secondary guitarist playing ambient textured chords in {tuning} tuning, "
            f"soft pastel stage lighting, delicate fingerpicking across upper frets, ethereal reverb haze, 8k resolution."
        )

    # 3. Bowed Strings (Violin, Viola, Cello, Contrabass)
    elif "violin" in inst:
        pos_desc = "high position near the bridge" if anchor_fret > 5 else "1st position near the scroll"
        bow_desc = "rapid aggressive tremolo bow stroke" if playing_state == "bowed_tremolo" else "smooth sweeping legato bow stroke"
        return (
            f"Magnificent 8k macro photo of virtuoso violin soloist performing on acoustic violin. "
            f"Left hand arched on un-fretted ebony fingerboard in {pos_desc}, right hand executing {bow_desc} with horsehair bow, "
            f"rosin dust suspended in dramatic shaft of stage spotlight, warm polished spruce wood grain."
        )

    elif "cello" in inst or "contrabass" in inst:
        bow_desc = "furious spiccato bouncing bow" if "spiccato" in playing_state else "deep resonant legato bow stroke"
        return (
            f"Cinematic low-angle medium shot of cellist seated with antique cello, left hand clamped on thick steel strings, "
            f"right hand driving horsehair bow across strings in {bow_desc}, vibrating body cavity, dark dramatic theater stage."
        )

    elif "strings" in inst:
        return (
            "Panoramic cinematic shot of orchestral string section playing in unison, violins and cellos bowing together, "
            "warm concert hall acoustic paneling, soft golden stage glow, photorealistic 8k cinema."
        )

    # 4. Orchestral Winds & Brass
    elif "brass" in inst:
        return (
            "Dramatic close-up of orchestral brass section players blowing into gleaming brass French horns and trumpets, "
            "cheeks puffed in powerful swell, stage backlights glinting off polished lacquer metal, atmospheric haze."
        )

    elif "woodwind" in inst or "flute" in inst:
        return (
            "Delicate cinematic portrait of concert flutist holding silver flute, embouchure blowing focused air stream, "
            "graceful finger placement over tone holes, ethereal blue stage illumination, 85mm lens."
        )

    elif "choir" in inst:
        return (
            "Awe-inspiring wide shot of mixed choir ensemble singing epic choral arrangement, robes, "
            "mouths open in harmonious vocal chant, dramatic cathedral light rays streaming from above."
        )

    # 5. Bass & Drums
    elif inst == "bass":
        return (
            f"Close-up high-contrast photo of heavy bass player's fingers aggressively plucking thick bass strings, "
            f"left hand clamped on fret {anchor_fret} in {tuning} tuning, vibrating low string motion blur, "
            f"neon green and purple rim lighting, 8k resolution."
        )

    elif inst == "drums":
        comp_str = ", ".join(drum_components) if drum_components else "heavy snare and kick"
        if playing_state == "heavy_breakdown_cymbal":
            return (
                f"Dramatic freeze-frame action shot of a metalcore drummer striking a raw unlathed china cymbal, "
                f"drumsticks at maximum velocity impact with water splash from cymbal bell, double bass pedal engaged, "
                f"high-speed photography, strobe lighting, cinematic smoke."
            )
        elif playing_state == "blast_beat":
            return (
                f"Dynamic motion shot of drummer performing high-speed blast beat on snare and kick drum, "
                f"intense facial expression, twin wooden drumsticks vibrating with speed blur, sweat flying, "
                f"concert stage backlighting, 8k cinema."
            )
        else:
            return (
                f"Cinematic drum kit shot showing drummer hitting {comp_str}, sharp focus on sticks hitting drumheads, "
                f"warm amber stage wash lighting, photorealistic."
            )

    elif inst in ("keyboard", "synth"):
        return (
            "Cinematic shot of synthesizer keys being played with both hands, neon blue synthwave LED backlighting, "
            "analog synthesizer knobs and sliders in background, moody cyberpunk aesthetic."
        )

    return f"Cinematic performance shot of musician playing {instrument} on dark stage with dramatic spotlights, 8k resolution."


def generate_veo_motion_prompt(
    instrument: str,
    playing_state: str,
    bpm: float,
    drum_components: List[str],
) -> str:
    """Generate tempo-locked Google Veo motion prompt."""
    inst = instrument.lower().strip()

    # 1. Vocals
    if inst in ("vocal_lead", "vocals"):
        if playing_state == "vocal_aggressive_scream":
            return (
                f"Explosive push-in camera rushing straight into lead vocalist screaming intensely at {bpm} BPM breakdown, "
                f"violent head movement, stage lights flashing furiously in synchronization."
            )
        elif playing_state == "vocal_rap_flow":
            return (
                f"Dynamic handheld Steadicam pacing around frontman rapping with rapid tempo cadence at {bpm} BPM, "
                f"rhythmic arm pumps, energetic stage motion."
            )
        else:
            return f"Smooth gliding camera push towards lead singer delivering passionate melody locked to {bpm} BPM groove."

    elif inst == "vocal_co_lead":
        return (
            f"Whip-pan transition switching rapidly between lead and co-lead vocalist during aggressive vocal duel at {bpm} BPM, "
            f"strobe lighting pulsing with every vocal phrase."
        )

    elif inst == "vocal_backing":
        return (
            f"Wide lateral dolly shot tracking backing vocalists singing harmony in unison at {bpm} BPM tempo, "
            f"dynamic concert wash lighting."
        )

    # 2. Guitars
    elif inst in ("guitar", "guitar_rhythm"):
        if playing_state == "palm_mute_chug":
            return (
                f"Fast camera orbit tracking rhythm guitarist downpicking violently at exact {bpm} BPM tempo, "
                f"rhythmic wrist convulsions perfectly synchronized to heavy kick drum blasts, dramatic smoke swirling."
            )
        elif playing_state == "stutter_mute":
            return (
                f"Abrupt freeze-motion stutter cut on rhythm guitarist, rhythmic stop-and-go headbang synced to {bpm} BPM breakdown."
            )
        elif playing_state == "wide_power_chord":
            return (
                f"Slow-motion camera push into rhythm guitarist hitting sustained power chord at {bpm} BPM, "
                f"hair whip, sparks showering in background, guitar headstock shaking from low frequency vibration."
            )
        else:
            return f"Energetic handheld camera tracking rhythm guitarist playing heavy riff locked to {bpm} BPM groove."

    elif inst == "guitar_lead":
        return (
            f"Dramatic 360-degree crane swoop revolving around lead guitarist shredding melodic guitar solo at {bpm} BPM, "
            f"fingers flying across upper frets with speed blur, arena spotlight flare, cinematic slow-motion acceleration."
        )

    elif inst == "guitar_additional":
        return (
            f"Gentle slow-motion floating camera drifting past guitarist playing ambient clean guitar texture at {bpm} BPM, "
            f"ethereal volumetric lighting, cinematic depth."
        )

    # 3. Bowed Strings
    elif "violin" in inst:
        return (
            f"Fluid high-speed camera sweep tracking violin soloist's bow sawing furiously across strings at {bpm} BPM, "
            f"rosin dust floating in spotlight, sweeping arc motion."
        )

    elif "cello" in inst or "contrabass" in inst:
        return (
            f"Slow rotational camera dolly around cellist driving heavy low-frequency bow stroke at {bpm} BPM tempo, "
            f"vibrating body resonance."
        )

    elif "strings" in inst:
        return (
            f"Panoramic crane glide rising above orchestral string ensemble bowing in synchronized rhythm at {bpm} BPM."
        )

    # 4. Brass & Choir
    elif "brass" in inst:
        return f"Dynamic camera zoom into brass bell flare swelling with brassy energy at {bpm} BPM impact."

    elif "choir" in inst:
        return f"Majestic ascending camera crane shot soaring over cathedral choir singing massive choral swell at {bpm} BPM."

    # 5. Bass & Drums
    elif inst == "bass":
        return (
            f"Low-angle camera dolly tracking bassist headbanging to {bpm} BPM groove, aggressive finger plucking motion blur."
        )

    elif inst == "drums":
        if playing_state == "heavy_breakdown_cymbal":
            return (
                f"Explosive slow-motion crash zoom into drummer smashing china cymbal at {bpm} BPM breakdown drop, "
                f"camera shake on impact, stage pyro firing in sync."
            )
        elif playing_state == "blast_beat":
            return (
                f"Hyper-speed camera whip panning between double bass drum pedals and snare at {bpm} BPM blast beat tempo."
            )
        else:
            return f"Medium tracking shot of drummer maintaining solid {bpm} BPM groove, smooth camera movement."

    elif inst in ("keyboard", "synth"):
        return f"Gliding Steadicam movement across synthesizer keyboard, neon synthwave lights pulsing to {bpm} BPM tempo."

    return f"Dynamic cinematic camera movement following musical performance at {bpm} BPM."


def build_song_sync_map(
    project_name: str,
    bpm: float,
    musical_key: str,
    tuning_name: str,
    master_audio_path: str,
    gp5_tab_path: str,
    guitar_events: Optional[List[Dict[str, Any]]] = None,
    bass_events: Optional[List[Dict[str, Any]]] = None,
    drum_events: Optional[List[Dict[str, Any]]] = None,
    synth_events: Optional[List[Dict[str, Any]]] = None,
    output_sync_map_path: str = "visual_sync_map.json",
    guitar_rhythm_events: Optional[List[Dict[str, Any]]] = None,
    guitar_lead_events: Optional[List[Dict[str, Any]]] = None,
    guitar_additional_events: Optional[List[Dict[str, Any]]] = None,
    vocal_lead_events: Optional[List[Dict[str, Any]]] = None,
    vocal_co_lead_events: Optional[List[Dict[str, Any]]] = None,
    vocal_backing_events: Optional[List[Dict[str, Any]]] = None,
    extra_instrument_events: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> SongSyncMap:
    """Assemble all instrument events into validated SongSyncMap and save to JSON."""
    all_instrument_events: List[InstrumentEvent] = []

    def process_generic_list(ev_list: List[Dict[str, Any]], inst_label: str):
        for ev in ev_list:
            state = ev.get("playing_state", "idle")
            str_nums = ev.get("string_numbers", None)
            frets = ev.get("fret_positions", None)
            anchor = ev.get("hand_box_anchor_fret", None)
            drum_comp = ev.get("drum_components", None)

            nb_prompt = generate_nano_banana_prompt(
                instrument=inst_label,
                playing_state=state,
                tuning=tuning_name,
                string_nums=str_nums or [],
                fret_pos=frets or [],
                anchor_fret=anchor or 0,
                drum_components=drum_comp or [],
            )
            veo_prompt = generate_veo_motion_prompt(
                instrument=inst_label,
                playing_state=state,
                bpm=bpm,
                drum_components=drum_comp or [],
            )

            all_instrument_events.append(InstrumentEvent(
                start_time_sec=ev["start_time_sec"],
                end_time_sec=ev["end_time_sec"],
                duration_sec=ev["duration_sec"],
                instrument=inst_label,
                playing_state=state,
                tuning=tuning_name,
                string_numbers=str_nums,
                fret_positions=frets,
                hand_box_anchor_fret=anchor,
                drum_components=drum_comp,
                nano_banana_keyframe_prompt=nb_prompt,
                veo_motion_prompt=veo_prompt,
                is_transient_peak=ev.get("is_transient_peak", False),
                recommended_capcut_fx=ev.get("recommended_capcut_fx", "none"),
            ))

    # 1. Vocals
    if vocal_lead_events:
        process_generic_list(vocal_lead_events, "vocal_lead")
    if vocal_co_lead_events:
        process_generic_list(vocal_co_lead_events, "vocal_co_lead")
    if vocal_backing_events:
        process_generic_list(vocal_backing_events, "vocal_backing")

    # 2. Guitars
    if guitar_rhythm_events or guitar_lead_events or guitar_additional_events:
        if guitar_rhythm_events:
            process_generic_list(guitar_rhythm_events, "guitar_rhythm")
        if guitar_lead_events:
            process_generic_list(guitar_lead_events, "guitar_lead")
        if guitar_additional_events:
            process_generic_list(guitar_additional_events, "guitar_additional")
    elif guitar_events:
        process_generic_list(guitar_events, "guitar")

    # 3. Bowed Strings & Orchestral
    if extra_instrument_events:
        for inst_label, ev_list in extra_instrument_events.items():
            process_generic_list(ev_list, inst_label)

    # 4. Bass
    if bass_events:
        process_generic_list(bass_events, "bass")

    # 5. Drums
    if drum_events:
        for ev in drum_events:
            state = ev.get("playing_state", "heavy_breakdown_cymbal")
            components = ev.get("components", ["kick", "snare"])

            nb_prompt = generate_nano_banana_prompt(
                instrument="drums",
                playing_state=state,
                tuning=tuning_name,
                string_nums=[],
                fret_pos=[],
                anchor_fret=0,
                drum_components=components,
            )
            veo_prompt = generate_veo_motion_prompt(
                instrument="drums",
                playing_state=state,
                bpm=bpm,
                drum_components=components,
            )

            all_instrument_events.append(InstrumentEvent(
                start_time_sec=ev["start_time_sec"],
                end_time_sec=ev["end_time_sec"],
                duration_sec=ev["duration_sec"],
                instrument="drums",
                playing_state=state,
                tuning=tuning_name,
                string_numbers=None,
                fret_positions=None,
                hand_box_anchor_fret=None,
                drum_components=components,
                nano_banana_keyframe_prompt=nb_prompt,
                veo_motion_prompt=veo_prompt,
                is_transient_peak=ev.get("is_transient_peak", True),
                recommended_capcut_fx=ev.get("recommended_capcut_fx", "screen_shake"),
            ))

    # 6. Synth / Keyboard
    if synth_events:
        process_generic_list(synth_events, "keyboard")

    # Sort all events chronologically
    all_instrument_events.sort(key=lambda x: (x.start_time_sec, str(x.instrument)))

    sync_map = SongSyncMap(
        project_name=project_name,
        bpm=bpm,
        musical_key=musical_key,
        time_signature="4/4",
        master_audio_path=master_audio_path,
        gp5_tab_path=gp5_tab_path,
        events=all_instrument_events,
    )

    with open(output_sync_map_path, "w", encoding="utf-8") as f:
        f.write(sync_map.model_dump_json(indent=2))

    return sync_map
