Dokumen **Product Requirements Document (PRD)** di bawah ini telah diperbarui secara menyeluruh (*Comprehensive Master PRD*). Seluruh ekspansi fitur mutakhir dari **Fase 6 hingga Fase 10** (meliputi *6-Stem & 3-Way Sub-Decomposition*, *Orchestral/Strings Instrument Decomposer*, *3-Way Vocal Separation with Lip-Sync Gating*, *Flagship VST3 & VSTi Arsenal Integration A–D*, hingga *Next.js Studio UI & Custom Prompt Dispatcher*) kini telah terintegrasi di dalamnya.

Kamu bisa langsung menyalin seluruh isi di bawah ini, menyimpannya sebagai file **`PRD.md`** di *root folder* proyek `F:\AI-Music-Video-MCP\`, atau menjadikannya panduan referensi utama untuk agen AI berikutnya.

---

```markdown
# PRODUCT REQUIREMENTS DOCUMENT (PRD) - MASTER VERSION (PHASE 1 to PHASE 11)
## Project Name: Universal AI Music & Video Production MCP Suite (`music-video-mcp-suite`)
**Target Environments:** Claude Code Desktop, Antigravity Desktop, Claude Desktop, Cursor, OpenAI Codex, & Next.js Studio UI (100% Universal Model Context Protocol - `stdio` / `FastMCP` & Direct Python CLI Execution)

---

## 1. EXECUTIVE SUMMARY & AGENT DIRECTIVES
**To the AI Coding Agent (Claude Code / Antigravity / Codex):**
You are tasked with maintaining, upgrading, and operating a modular, production-ready suite of **3 Universal MCP Servers** written in Python (`FastMCP`) paired with a **Next.js Studio Web UI**. This system bridges the gap between **AI Music Stems (Suno AI / Udio)**, **Advanced Stem Decomposed Sub-Layers (3-Way Vocals, 3-Way Guitars, Orchestral Bowed Strings)**, **DAW Audio Engineering & Flagship VST3/VSTi Hosting (Ozone, FabFilter, Soothe2, Neural DSP, Superior Drummer 3, Kontakt)**, **Multi-Track Tablature Generation (`.gp5` / `MusicXML`)**, and **Automated Beat-Synced Video Assembly in CapCut Desktop** (using Google Veo & Nano Banana 2.1).

### Core Rules for Agent Execution:
1. **ATM Strategy (Adopt, Adapt, Modify):** Do NOT reinvent complex DSP, VST-hosting, or CapCut schemas. Leverage proven open-source libraries (`demucs`, `basic-pitch`, `pyguitarpro`, `librosa`, `pedalboard`, `matchering`, `pyCapCut`, `music21`, `opencv-python-headless`).
2. **Universal MCP Compliance:** All tools must be exposed via standard `FastMCP` decorators (`@mcp.tool()`) over `stdio` so identical servers run seamlessly in Claude Code, Antigravity, Cursor, and Codex.
3. **No Mock/Placeholder Logic:** Use a source-separation model for instrument isolation. M/S, STFT masks, pitch salience, and noise gates are processing heuristics and must never be labeled as isolated instruments or performers.
4. **Step-by-Step Execution & Verification:** Ensure modularity and maintain 100% passing rate across all unit test suites (`pytest tests/ -v`).

---

## 2. SYSTEM ARCHITECTURE & MONOREPO DIRECTORY STRUCTURE

```text
music-video-mcp-suite/
├── PRD.md
├── mcp_config.json                 # Unified config for Claude, Codex, Antigravity
├── requirements.txt                # Shared Python dependencies
├── README.md                       # Setup & usage documentation
├── start_studio_ui.bat             # One-click launcher for Next.js Studio UI
├── shared_schemas/
│   ├── __init__.py
│   └── sync_map_schema.py          # Pydantic models for dynamic instruments & sync contract
├── servers/
│   ├── cli_runner.py               # CLI bridge for Next.js Studio UI direct execution
│   ├── daw_studio_mcp/             # MODULE 1: Audio Separation, Mixing, VST3 Hosting & DAW Export
│   │   ├── server.py
│   │   ├── stem_separator.py       # 6-source Demucs htdemucs_6s; no silent DSP fallback
│   │   ├── guitar_decomposer.py    # M/S + STFT Soft-Masking 3-Way Guitar Sub-Stem (Rhythm, Lead, Add.)
│   │   ├── vocal_decomposer.py     # 3-Way Vocal Sub-Stem (Lead, Co-Lead/Scream, Backing) + Lip-Sync Gate
│   │   ├── orchestra_decomposer.py # Timbre & Envelope Detection for Violin, Cello, Brass, Choir, etc.
│   │   ├── mashup_engine.py        # BPM Time-Stretch, Key Detection & Pitch-Shift
│   │   ├── mix_master_engine.py    # Flagship VST3/VSTi chain runner (Ozone, FabFilter, Soothe2)
│   │   ├── vst3_manager.py         # VST3 Scanner & Parameter Inspector (Categories A-D)
│   │   └── daw_bridge.py           # REAPER (.rpp) & Ableton Project Generator with MIDI-to-VSTi
│   ├── tab_transcriber_mcp/        # MODULE 2: Audio-to-Tab (.gp5) & Visual Coordinate Generator
│   │   ├── server.py
│   │   ├── pitch_tracker.py        # Polyphonic pitch & drum frequency-band onset detection
│   │   ├── fretboard_solver.py     # Viterbi 4-fret hand-box, Drop Tunings & Bowed String Tunings
│   │   ├── gp5_exporter.py         # Multi-Track PyGuitarPro (.gp5) & MusicXML with Unique MIDI Channels
│   │   └── visual_prompt_mapper.py # Generates Nano Banana 2.1 & Veo keyframe prompts per timestamp
│   └── capcut_director_mcp/        # MODULE 3: Automated CapCut Timeline & Beat-Sync Assembler
│       ├── server.py
│       ├── draft_manager.py        # Wrapper around pyCapCut draft_content.json
│       ├── beat_cutter.py          # Optical flow BPM speed-ramping & transient hard-cutting
│       └── fx_injector.py          # Injects breakdown scale punch, shake, and flash keyframes
├── web-ui/                         # MODULE 4: Next.js Studio UI Dashboard
│   ├── src/app/
│   │   ├── api/                    # Dual-mode API routes (Direct Python vs. Agent CLI Dispatcher)
│   │   └── page.tsx                # Single-Page DAW Studio Dashboard with Prompt Playground
│   └── package.json
└── workspace/                      # Default working directory for user assets
    ├── input_stems/                # Demucs sources: vocals, drums, bass, guitar, piano, other
    ├── output_audio/               # Master WAVs, REAPER sessions (.rpp)
    ├── output_tabs/                # .gp5, .musicxml, visual_sync_map.json
    └── veo_footage/                # AI-generated video clips (.mp4)

```

---

## 3. SHARED DATA CONTRACT (`shared_schemas/sync_map_schema.py`)

To support dynamic instrumentation (Rock/Metal bands, Bowed Strings, Orchestral Sections, Choirs) without validation blocks, schemas use open `Union` types:

```python
from pydantic import BaseModel
from typing import List, Optional, Literal, Union

KnownInstruments = Literal[
    "vocals", "vocal_lead", "vocal_co_lead", "vocal_backing",
    "guitar", "guitar_rhythm", "guitar_lead", "guitar_additional", "acoustic_guitar",
    "bass", "drums", "keyboard", "synth",
    "violin", "viola", "cello", "contrabass",
    "strings_ensemble", "brass", "woodwinds", "flute", "saxophone",
    "choir", "harp", "percussion_orchestral"
]

KnownPlayingStates = Literal[
    "vocal_clean_melodic", "vocal_aggressive_scream", "vocal_rap_flow", "vocal_spoken_whisper", "vocal_backing_harmony", "vocal_gang_shout",
    "palm_mute_chug", "stutter_mute", "wide_power_chord", "lead_melody", "arpeggio_fast", "sustained_pad", "blast_beat", "heavy_breakdown_cymbal",
    "bowed_legato", "bowed_tremolo", "spiccato_fast", "pizzicato_plucked",
    "brass_swell_blare", "woodwind_expressive_solo", "choir_epic_chant", "idle"
]

class InstrumentEvent(BaseModel):
    start_time_sec: float
    end_time_sec: float
    duration_sec: float
    instrument: Union[KnownInstruments, str]
    playing_state: Union[KnownPlayingStates, str]
    tuning: Optional[str] = "Drop C"
    string_numbers: Optional[List[int]] = None
    fret_positions: Optional[List[int]] = None
    hand_box_anchor_fret: Optional[int] = None
    drum_components: Optional[List[str]] = None
    nano_banana_keyframe_prompt: str
    veo_motion_prompt: str
    is_transient_peak: bool = False
    recommended_capcut_fx: Optional[Literal["none", "screen_shake", "white_flash", "hard_zoom"]] = "none"

class SongSyncMap(BaseModel):
    project_name: str
    bpm: float
    musical_key: str
    time_signature: str = "4/4"
    master_audio_path: str
    gp5_tab_path: str
    events: List[InstrumentEvent]

```

---

## 4. MODULE 1 SPECIFICATION: `daw-studio-mcp` (Phases 6–9)

**Role:** Handles pretrained `htdemucs_6s` source separation, experimental guitar/vocal/orchestral analysis, Frankenstein mashups, VST3 discovery, and REAPER/Ableton project generation. Experimental DSP masks are not source separation and must not be presented as isolated performers or instruments.

### 4.1. Core Engines:

1. **`stem_separator.py` & `guitar_decomposer.py` & `vocal_decomposer.py` & `orchestra_decomposer.py`:**
* Runs the pretrained six-source Demucs model. Its labels are `vocals`, `drums`, `bass`, `guitar`, `piano`, and `other`; extra gate processing is optional and can suppress quiet content.
* Current guitar, vocal, and orchestral sub-decomposers produce experimental heuristic masks only. They do not identify separate performers/instruments or guarantee lip-sync readiness.


2. **`vst3_manager.py` & `mix_master_engine.py`:**
* Scans `C:\Program Files\Common Files\VST3` for 57+ installed plugins and categorizes them into Category A (Mastering/Surgical: Ozone, FabFilter Pro-Q/L/MB/Saturn, Soothe2), Category B (Vocals/Spatial: Nectar, Pro-C/DS, Valhalla), Category C (Guitars: Neural DSP Gojira/Parallax), and Category D (VSTi: Superior Drummer 3, Kontakt, BBC SO).
* Automatically builds role-specific VST3 chains and applies integrated True-Peak LUFS normalization.


3. **`daw_bridge.py`:**
* Generates a REAPER session skeleton from existing audio, markers from `visual_sync_map.json`, and a guitar DI recording track. Only installed plugins are referenced. VSTi tracks require installed instruments and real transcribed MIDI; no fallback notes or unsupported plugin claims are allowed.



---

## 5. MODULE 2 SPECIFICATION: `tab-transcriber-mcp` (Phases 3 & 7–8)

**Role:** Produces automatic tablature drafts (`.gp5` / `MusicXML`) and a timed `visual_sync_map.json`; pitch/onset output requires human review.

### 5.1. Key Capabilities:

1. **Viterbi Fretboard & Bowed String Solver (`fretboard_solver.py`):**
* Automatically detects Drop C, Drop D, or Standard E for guitars, and standard 4-string tunings for Violin (`E5, A4, D4, G3`), Viola, and Cello. Enforces the 4-fret hand box constraint and 1-finger barre power chord preferences.


2. **Multi-Track GP5 Exporter (`gp5_exporter.py`):**
* Allocates unique MIDI channel pairs (`channel = c_num * 2`) and General MIDI program numbers (Guitar=25/30, Violin=40, Cello=42, Choir=52, Voice=53) to prevent instrument clashes in Guitar Pro 5.



---

## 6. MODULE 3 SPECIFICATION: `capcut-director-mcp` (Phase 4)

**Role:** Automates CapCut Desktop drafting (`draft_content.json`) by synchronizing Google Veo and lip-sync video clips against `visual_sync_map.json`.

* Applies optical-flow micro speed-ramping, hard transient cuts, and breakdown scale-punch/shake keyframe injections (`fx_injector.py`).

---

## 7. MODULE 4 SPECIFICATION: Next.js Studio UI & Dual-Dispatcher (Phase 10)

**Role:** Visual control center (`http://localhost:3000`) launched via `start_studio_ui.bat`.

1. **Dual-Mode Backend:**
* **Mode A (`Direct Python MCP Engine`):** Instantly executes Python MCP routines via `servers/cli_runner.py`.
* **Mode B (`Agent CLI Dispatcher`):** Dynamically builds and dispatches structured master prompts to `Claude Code`, `Antigravity`, or `OpenAI Codex`.


2. **Interactive UI Tabs:**
* **Tab 1:** Stem Separation & Mashup Splicer with anti-bleed toggles.
* **Tab 2:** Flagship VST3 Mix & DAW Project generator (`.rpp` / Ableton manifest).
* **Tab 3:** Tablature (`.gp5`) & Visual Prompt Explorer with 1-click Nano Banana 2.1 & Veo prompt copiers and custom modifiers.
* **Tab 4:** Veo Footage Manager & CapCut Auto-Director.


3. **Editable Prompt Playground Workspace:**
* Two-way synced textarea at the bottom of the UI that auto-compiles user toggle states into agent prompts, while allowing free manual text overrides.



---

## 8. STEP-BY-STEP AGENT EXECUTION SUMMARY

1. **Environment:** Python 3.12+ virtual environment with all shared libraries (`fastmcp`, `demucs`, `pedalboard`, `librosa`, `pyguitarpro`, `basic-pitch`, etc.).
2. **Verification:** Run unit test suite via `.venv\Scripts\python.exe -m pytest tests/ -v` (Target: 33/33 tests passing).
3. **Studio UI Launch:** Execute `start_studio_ui.bat` at root to open the Next.js local dashboard.

```

```

## Operational Acceptance Rules

- The production 6-source separator is the pretrained Demucs `htdemucs_6s` model. Its labels are `drums`, `bass`, `other`, `vocals`, `guitar`, and `piano`; do not rename `piano` to `synth`.
- If the model package, weights, or inference fails, stop and return an error before writing outputs. Frequency filters, Mid/Side, HPSS, and noise gates may be offered only as experimental processing; they cannot claim instrument isolation.
- The current 3-way guitar, 3-way vocal, and orchestral DSP routines are heuristic estimates, not validated source separation. Disable them by default, identify their outputs as experimental, and exclude them from downstream mastering/transcription unless a suitable pretrained model is added and its results are validated.
- A generated REAPER project, tablature, sync map, or video timeline must not be described as complete merely because a file was written. Identify the input stems and processing method, and report unavailable or unverified capabilities explicitly.

## Phase 11: Measured Task-Based Separation, Source Isolation, and Preview

- `workspace/source_songs/` is the only source-song catalog. The Web UI scans this folder (including its subfolders) for `.wav`, `.mp3`, and `.flac` files; generated stems, exports, and model caches are never source candidates. The CLI independently enforces this boundary for stem separation and the full pipeline.
- Outputs are written under `workspace/input_stems/<project_name>/`. Project names default to the selected source filename and are sanitized before use.
- `servers/daw_studio_mcp/model_registry.py` records task type, expected output labels, license notes, verification state, and caveats. `htdemucs_6s` is the active default and returns the model's six source labels. These are estimates, not bleed-free multitracks.
- The cascaded backend is visible as unavailable until task-specific pretrained weights, licenses, and output mappings have been configured and verified. No vocal-role, guitar-role, or orchestral model is silently substituted.
- Existing `guitar_decomposer.py`, `vocal_decomposer.py`, and `orchestra_decomposer.py` remain optional and disabled by default. Their outputs are labeled `Experimental Heuristic DSP Mask (Not Source Separation)` and keep their experimental status in result metadata.
- Inference runs one model at a time. CUDA telemetry records the measured device, duration, peak allocated memory, and peak reserved memory. CUDA out-of-memory returns a structured error with smaller-segment and CPU fallback suggestions; no static VRAM ceiling is promised.
- Tab 1 previews generated WAV stems through a range-capable local audio endpoint. The endpoint only serves files rooted under `workspace/input_stems/`.
- Verification covers workspace source-path isolation, model metadata, VRAM telemetry formatting, Python unit tests, and the production Next.js build/typecheck.
