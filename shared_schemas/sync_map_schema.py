from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union

KnownInstruments = Literal[
    # Vocals (Phase 8)
    "vocals", "vocal_lead", "vocal_co_lead", "vocal_backing",
    # Band & Guitar Variants (Phases 1-6)
    "guitar", "guitar_rhythm", "guitar_lead", "guitar_additional", "acoustic_guitar",
    "bass", "drums", "keyboard", "synth",
    # Solo Bowed Strings (Phase 7)
    "violin", "viola", "cello", "contrabass",
    # Orchestral Sections & Ensembles (Phase 7)
    "strings_ensemble", "brass", "woodwinds", "flute", "saxophone",
    "choir", "harp", "percussion_orchestral"
]

KnownPlayingStates = Literal[
    # Vocal States (Phase 8)
    "vocal_clean_melodic", "vocal_aggressive_scream", "vocal_rap_flow",
    "vocal_spoken_whisper", "vocal_backing_harmony", "vocal_gang_shout",
    # Rock / Band States (Phases 1-6)
    "palm_mute_chug", "stutter_mute", "wide_power_chord", "lead_melody",
    "arpeggio_fast", "sustained_pad", "blast_beat", "heavy_breakdown_cymbal",
    # Bowed String & Orchestral States (Phase 7)
    "bowed_legato", "bowed_tremolo", "spiccato_fast", "pizzicato_plucked",
    "brass_swell_blare", "woodwind_expressive_solo", "choir_epic_chant",
    "idle"
]

class InstrumentEvent(BaseModel):
    start_time_sec: float
    end_time_sec: float
    duration_sec: float
    instrument: Union[KnownInstruments, str]
    playing_state: Union[KnownPlayingStates, str]
    # Musical & Tablature Data (For Humans & Visual Accuracy)
    tuning: Optional[str] = "Drop C"
    string_numbers: Optional[List[int]] = None      # e.g., [6, 5, 4]
    fret_positions: Optional[List[int]] = None      # e.g., [5, 5, 5]
    hand_box_anchor_fret: Optional[int] = None      # Left hand anchor fret (0 to 22)
    drum_components: Optional[List[str]] = None     # e.g., ["kick_double", "china_cymbal", "snare"]
    # AI Video Generation Prompts
    nano_banana_keyframe_prompt: str
    veo_motion_prompt: str
    # CapCut Editing Directives
    is_transient_peak: bool = False
    recommended_capcut_fx: Optional[Literal["none", "screen_shake", "white_flash", "hard_zoom"]] = "none"

class SongSyncMap(BaseModel):
    project_name: str
    bpm: float
    musical_key: str
    time_signature: str = "4/4"
    master_audio_path: str
    gp5_tab_path: str
    events: List[InstrumentEvent] = Field(default_factory=list)
