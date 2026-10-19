# Universal AI Music & Video Production MCP Suite (`music-video-mcp-suite`)

[![Tests](https://img.shields.io/badge/tests-53%20passed-brightgreen.svg)](#running-all-unit-tests)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-100%25%20Universal%20FastMCP-orange.svg)](https://modelcontextprotocol.io/)
[![Next.js](https://img.shields.io/badge/Next.js-16%20Turbopack-black.svg)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A production-grade, modular suite of **3 Universal Model Context Protocol (MCP) servers** written in Python (`FastMCP`) over `stdio`, paired with a modern **Next.js Studio Web UI** featuring dual-mode execution (Direct Python MCP & Agent CLI Dispatcher).

This system bridges the gap between **AI Music Stems (Suno AI / Udio / Demucs)**, **Advanced Stem Decomposed Sub-Layers (Vocals, Guitars, Bowed Strings)**, **Flagship VST3/VSTi Audio Engineering (Ozone, FabFilter, soothe2, Neural DSP, Superior Drummer 3, Kontakt)**, **Biomechanical Multi-Track Tablature Generation (.gp5 / MusicXML)**, and **Automated Beat-Synced Video Timeline Assembly in CapCut Desktop**.

---

## Key System Capabilities

- **Pretrained Demucs 6-Stem Separation (`htdemucs_6s`):** Discrete isolation for vocals, drums, bass, guitar, piano, and residual other.
- **Dual-Mode Audio-to-MIDI & Tablature Engine:**
  - **Mode 1 (Offline Neural ONNX):** Spotify Basic Pitch neural network inference running directly on `onnxruntime` (no TensorFlow conflicts) for high-accuracy polyphonic guitar chord transcription.
  - **Mode 2 (Hybrid DAW Bridge):** 1-click import of verified `.mid` files exported from **Superior Drummer 3 Tracker**, **REAPER (ReaTune)**, **Ableton Live**, or **Hit'n'Mix RipX DeepAudio**.
- **VST3 Pre-Cleaning Pipeline:** Pre-cleans audio stems before pitch and BPM tracking using installed flagship VST3 plugins (**FabFilter Pro-Q 4**, **oeksound soothe2**, **iZotope RX 11 Guitar De-noise**) or high-order IIR filters (cutting sub-bass rumble < 75 Hz and cymbal sizzle > 5.5 kHz).
- **Acoustic Key & Transient BPM Detection:** Prioritizes isolated drum stem transient envelopes for tempo tracking and pre-cleaned harmonic stems for Krumhansl-Schmuckler key profile detection.
- **Biomechanical Viterbi 4-Fret Fretboard Solver:** Anatomically constrained 4-fret hand-box shortest-path routing, 1-finger barre power chords, and automatic tuning support (Standard E, Drop D, Drop C, Eb Standard, D Standard).
- **Interactive Songsterr Tablature Viewer:** Built-in AlphaTab visual score renderer in Next.js Studio UI supporting multi-track tab playback, solo/mute, zoom, and live cursor tracking.
- **Zero-Setup Multitrack DAW Project Generation:**
  - **REAPER (`.rpp`):** 5 organized folder buses (*VOCAL BUS, GUITAR BUS, BASS & DRUM BUS, ORCHESTRA BUS, VSTi BUS*) with automated routing for **Superior Drummer 3** on drums, **ReaTune** on vocal/bass/lead, and **Neural DSP Archetype** on guitar buses.
  - **Ableton Live (`.als`):** Native compressed Live 12 XML sets with sample-accurate unwarped audio stem layout.
- **Automated CapCut Video Timeline Director:** Optical flow transient cutting, micro speed-ramping to match song BPM, and injection of camera shake, zoom punch, and flash keyframes.

---

## Monorepo Directory Structure

```text
music-video-mcp-suite/
├── PRD.md                                # Master Product Requirements Document (Phases 1-13)
├── start_studio_ui.bat                   # 1-Click launcher to open Web UI on http://localhost:3000
├── mcp_config.json                       # Universal MCP configuration for Claude, Antigravity, Cursor
├── requirements.txt                      # Python dependencies (PyTorch CUDA, librosa, pedalboard, etc.)
├── pytest.ini                            # Pytest configuration
├── README.md                             # Main documentation
├── shared_schemas/
│   ├── __init__.py
│   └── sync_map_schema.py                # Pydantic data contract for dynamic instruments and sync events
├── servers/
│   ├── README.md                         # Architecture and API documentation for MCP servers
│   ├── cli_runner.py                     # CLI bridge between Web UI and Python MCP backend
│   ├── workspace_paths.py                # Path sanitization and workspace directory boundaries
│   ├── daw_studio_mcp/                   # MODULE 1: Stem Separation, Mixing, VST3 Hosting & DAW Bridge
│   │   ├── server.py                     # FastMCP server definition
│   │   ├── vst3_manager.py               # Category A-D VST3 scanner, parameter inspector & role chains
│   │   ├── stem_separator.py             # Pretrained htdemucs_6s source separation
│   │   ├── guitar_decomposer.py          # 3-way guitar sub-stem analysis (Rhythm, Lead, Additional)
│   │   ├── vocal_decomposer.py           # 3-way vocal sub-stem analysis & lip-sync readiness gating
│   │   ├── orchestra_decomposer.py       # Orchestral acoustic detection & selective decomposition
│   │   ├── mashup_engine.py              # Drum transient BPM tracking & cleaned harmonic key detection
│   │   ├── mix_master_engine.py          # Stem gain staging, LUFS balancing & VST3 mastering chains
│   │   └── daw_bridge.py                 # REAPER (.rpp) with SD3/ReaTune & Ableton (.als) set generator
│   ├── tab_transcriber_mcp/              # MODULE 2: Audio-to-Tab, Neural ONNX & DAW MIDI Importer
│   │   ├── server.py                     # FastMCP server definition
│   │   ├── models/
│   │   │   └── nmp.onnx                  # Spotify Basic Pitch neural network model
│   │   ├── pre_cleaner.py                # VST3 pre-cleaning (Pro-Q 4, soothe2, RX 11 de-bleed)
│   │   ├── pitch_tracker.py              # ONNX neural transcription & sub-band drum transient detection
│   │   ├── fretboard_solver.py           # Viterbi 4-fret hand-box, Drop Tunings & Bowed Strings
│   │   ├── gp5_exporter.py               # Multi-track Guitar Pro 5 (.gp5) & MusicXML exporter
│   │   ├── daw_midi_importer.py          # Parser for SD3 Tracker / REAPER / Ableton / RipX MIDI files
│   │   └── visual_prompt_mapper.py       # Nano Banana 2.1 & Google Veo keyframe prompt generator
│   └── capcut_director_mcp/              # MODULE 3: Automated CapCut Timeline & Video Assembler
│       ├── server.py                     # FastMCP server definition
│       ├── draft_manager.py              # pyCapCut wrapper for draft_content.json timelines
│       ├── beat_cutter.py                # Micro speed-ramping, transient hard cuts & multi-angle shots
│       └── fx_injector.py                # Breakdown zoom punch, camera shake & white flash keyframes
├── web-ui/                               # MODULE 4: Next.js Studio Dashboard (Turbopack, Tailwind)
│   ├── README.md                         # Web UI architecture and developer guide
│   ├── package.json
│   ├── tsconfig.json
│   └── src/app/
│       ├── page.tsx                      # Single-page DAW Studio Dashboard with 4 workflow tabs
│       └── api/
│           ├── execute/route.ts          # Dual-Dispatcher (Direct Python MCP vs Agent CLI)
│           ├── tabs/file/route.ts        # Binary stream endpoint for Songsterr .gp5 playback
│           └── workspace/route.ts        # Live workspace filesystem & sync map inspector
├── tests/                                # Comprehensive Pytest Test Suite (Phases 1-13)
│   ├── test_phase1_scaffolding.py
│   ├── test_phase2_daw_studio.py
│   ├── test_phase3_tab_transcriber.py
│   ├── test_phase4_capcut_director.py
│   ├── test_phase5_mcp_config.py
│   ├── test_phase6_multi_guitar_separation.py
│   ├── test_phase7_orchestral_instruments.py
│   ├── test_phase8_vocal_decomposition.py
│   ├── test_phase9_flagship_vst3_and_daw.py
│   ├── test_phase10_studio_ui.py
│   ├── test_phase11_workspace_and_registry.py
│   ├── test_phase12_ableton_project.py
│   └── test_phase13_hybrid_onnx_and_daw_midi.py
└── workspace/                            # Local workspace directory for audio assets
    ├── source_songs/                     # User source tracks (.wav, .mp3, .flac)
    ├── input_stems/                      # Separated stems per project (htdemucs_6s)
    ├── output_audio/                     # Master audio (.wav) and DAW project sessions (.rpp, .als)
    ├── output_tabs/                      # Exported .gp5, .musicxml, and visual_sync_map.json
    └── veo_footage/                      # AI-generated video clips (.mp4)
```

---

## Quick Start: Launching the Studio UI

### Method 1: 1-Click Windows Launcher
Double-click `start_studio_ui.bat` at the repository root:
```bat
start_studio_ui.bat
```
This automatically verifies dependencies, starts the Next.js production/development server on `http://localhost:3000`, and opens your default browser.

### Method 2: Manual Terminal Execution
```bash
# In first terminal (Next.js Web UI):
cd web-ui
npm run dev

# Source songs:
Place your full-song audio files (.wav, .mp3, or .flac) inside workspace/source_songs/
```

---

## Studio Dashboard Workflows

The dashboard provides a unified interface across 4 specialized production tabs:

### Tab 1: Stem Separation & Mashup Splicer
- **Pretrained Demucs 6-Source Separation:** Isolates `vocals.wav`, `drums.wav`, `bass.wav`, `guitar.wav`, `piano.wav`, and `other.wav`.
- **Anti-Bleed Gate:** Adaptive threshold gate eliminating bleed between high-gain guitars and cymbals.
- **Crossfaded Mashup Splicer:** 15ms cosine crossfade splicing with automatic BPM time-stretching and harmonic pitch-shifting.

### Tab 2: VST3 Mixing, Mastering & DAW Projects
- **Category A–D VST3 Discovery:** Automatically scans `C:\Program Files\Common Files\VST3` for 57+ flagship plugins:
  - *Category A (Surgical & Mastering):* FabFilter Pro-Q 4, Pro-MB, Pro-L 2, Saturn 2, iZotope Ozone 12, oeksound soothe2.
  - *Category B (Vocals & Spatial):* FabFilter Pro-C 3, Pro-DS, Valhalla DSP.
  - *Category C (Guitars & Bass):* Neural DSP Archetype (Gojira, Plini, Nolly, Cory Wong, Abasi), Parallax X, Darkglass Ultra.
  - *Category D (Virtual Instruments & Transcribers):* Toontrack Superior Drummer 3, Hit'n'Mix RipX (RipLink), BBC SO / Kontakt.
- **Master Audio Renderer:** Automated gain staging, EQ de-harshing, reference mastering via Matchering 2.0, and EBU R128 true-peak limiting.
- **DAW Export Buttons:** 1-click generation and launching of native **REAPER (.rpp)** and **Ableton Live 12 (.als)** sessions with pre-routed buses and FX chains.

### Tab 3: Full-Band Tablature (.gp5) & Visual Prompt Explorer
- **Hybrid DAW MIDI Importer:** Import verified `.mid` files directly from **Superior Drummer 3 Tracker**, **REAPER ReaTune**, **Ableton**, or **RipX DeepAudio** with 1-click to produce production-accurate tablature.
- **Offline ONNX Neural Transcription:** Transcribe complex guitar chords using Spotify Basic Pitch neural network on pre-cleaned stems without opening a DAW.
- **Interactive Songsterr Tab Viewer:** Web-based AlphaTab renderer displaying guitar tablature, standard musical notation, chord diagrams, and real-time playback cursor.
- **Tuning & Key Selector:** Select Standard E, Drop D, Drop C, Eb Standard, or D Standard with automatic Viterbi fretboard hand-box solving.
- **Prompt Explorer:** Copy Nano Banana 2.1 keyframe prompts and Google Veo motion prompts per timestamp with custom style modifiers.

### Tab 4: Veo Footage Manager & CapCut Auto-Director
- **Footage Inspector:** Scan `workspace/veo_footage/` and verify clips against required musical sync states (e.g. guitar downpicking, blast beats, vocal screams).
- **Automated CapCut Timeline Assembly:** Generates native CapCut Desktop drafts with BPM-aligned transient cuts, optical flow speed-ramping, and breakdown punch/shake effects.

---

## Dual-Mode Audio-to-MIDI Pipeline Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        SOURCE AUDIO / STEMS                            │
│           (workspace/input_stems/<project>/guitar.wav, etc.)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     STEP 1: VST3 PRE-CLEANING                          │
│     (FabFilter Pro-Q 4 / soothe2 / RX 11 Guitar De-noise / IIR)        │
│    - Highpass < 75 Hz (eliminate sub-bass rumble & kick bleed)         │
│    - Lowpass > 5.5 kHz (eliminate cymbal sizzle & hi-hat bleed)        │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼ (Jalur 1: Offline)             ▼ (Jalur 2: Hybrid DAW Bridge)
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│       ONNX NEURAL TRANSCRIPTION      │  │      EXPORT TO DAW SESSION   │
│     (Spotify Basic Pitch nmp.onnx)   │  │  - SD3 Tracker on Drum Track │
│  - 88 MIDI pitch probability matrix  │  │  - ReaTune on Bass/Vocal/Lead│
│  - Handles polyphonic chords cleanly │  │  - Neural DSP on Guitar Bus  │
└───────────────────┬──────────────────┘  └──────────────┬───────────────┘
                    │                                    │
                    │                                    ▼
                    │                     ┌──────────────────────────────┐
                    │                     │    USER EXPORTS VERIFIED     │
                    │                     │      MIDI (.mid) FROM DAW    │
                    │                     │ (SD3 / REAPER / Ableton/RipX)│
                    │                     └──────────────┬───────────────┘
                    │                                    │
                    └─────────────────┬──────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│            STEP 2: BIOMECHANICAL VITERBI 4-FRET SOLVER                 │
│  - Ergonomic 4-fret hand-box stretch constraint                        │
│  - 1-Finger barre power chord detection for Drop tunings               │
│  - Standard E / Drop D / Drop C / Eb Standard / D Standard tunings     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             STEP 3: MULTI-TRACK TABLATURE & SYNC MAP EXPORT            │
│  - Guitar Pro 5 (.gp5) with individual instrument tracks               │
│  - MusicXML (.musicxml) score interchange                              │
│  - visual_sync_map.json with Veo & Nano Banana prompts                 │
│  - Interactive Songsterr viewer in Next.js Studio UI                   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## MCP Server Configuration (`mcp_config.json`)

To use the 3 MCP servers inside Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`), Antigravity Desktop, Cursor, or Codex, reference the pre-configured `mcp_config.json`:

```json
{
  "mcpServers": {
    "daw-studio-mcp": {
      "command": "F:\\AI-Music-Video-MCP\\.venv\\Scripts\\python.exe",
      "args": [
        "F:\\AI-Music-Video-MCP\\servers\\daw_studio_mcp\\server.py"
      ]
    },
    "tab-transcriber-mcp": {
      "command": "F:\\AI-Music-Video-MCP\\.venv\\Scripts\\python.exe",
      "args": [
        "F:\\AI-Music-Video-MCP\\servers\\tab_transcriber_mcp\\server.py"
      ]
    },
    "capcut-director-mcp": {
      "command": "F:\\AI-Music-Video-MCP\\.venv\\Scripts\\python.exe",
      "args": [
        "F:\\AI-Music-Video-MCP\\servers\\capcut_director_mcp\\server.py"
      ]
    }
  }
}
```

### Available Tools:

#### `daw-studio-mcp`
- `separate_audio_stems(audio_path, model_name, output_dir, ...)`: Demucs 6-stem separation.
- `mashup_replace_segment(base_stem, donor_stem, ...)`: Splicing with time-stretch & pitch-shift.
- `auto_mix_and_master(stems_dir, genre_profile, target_lufs, ...)`: Flagship VST3 mix & master.
- `generate_reaper_project(project_name, stem_paths, ...)`: Generates `.rpp` with SD3, ReaTune, and Neural DSP.
- `export_ableton_live_set(project_name, stem_paths, ...)`: Generates native `.als` project for Ableton Live 12.

#### `tab-transcriber-mcp`
- `transcribe_stems_to_gp5_and_sync_map(project_name, bpm, musical_key, ...)`: Offline ONNX neural transcription, Viterbi 4-fret solver, `.gp5`, `.musicxml`, and `visual_sync_map.json`.
- `import_daw_midi(project_name, midi_path, tuning_name, bpm, ...)`: Imports verified `.mid` from SD3 Tracker, REAPER, Ableton, or RipX to generate tablature.

#### `capcut-director-mcp`
- `list_and_classify_footage(footage_dir)`: Scans and tags AI video clips.
- `assemble_capcut_music_video(project_name, sync_map_path, ...)`: Builds beat-synced timeline in CapCut Desktop.

---

## Running All Unit Tests

Run the complete test suite across all 13 phases:

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected result:
```text
======================= 53 passed, 5 warnings in ~65s =======================
```

---

## Hardware Acceleration (NVIDIA CUDA Setup)

To utilize GPU acceleration on NVIDIA RTX cards (~15-30s for Demucs 6-stem separation instead of ~7-8 minutes on CPU):

```powershell
.\.venv\Scripts\pip install --upgrade --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 --default-timeout=1000
```

Verify GPU detection:
```powershell
.\.venv\Scripts\python.exe -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```
Output:
```text
CUDA Available: True
Device: NVIDIA GeForce RTX 3070
```

---

## Honest Production Quality & Limitations Disclosure

1. **Source Separation:** Pretrained `htdemucs_6s` is genuine neural source separation. Experimental sub-stem routines (e.g. 3-way guitar or vocal decomposition) use mathematical STFT/Mid-Side masks and are labeled experimental; they must not be presented as isolated performers.
2. **Audio-to-MIDI Transcription:** Pitch and onset tracking via ONNX Basic Pitch provides an automated draft. Performance-level pitch accuracy and complex polyphonic voicings should always be verified or imported via the Hybrid DAW Bridge (**Superior Drummer 3 Tracker** for drums, **ReaTune** for solo instruments, or **RipX DeepAudio** for multi-part audio).
3. **DAW Automation:** REAPER and Ableton files are constructed from verified physical stem paths; no placeholder audio or phantom notes are invented.
