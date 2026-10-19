# AI Music Video Production - MCP Servers Architecture

This directory contains the Python-based backend architecture for the **Universal AI Music & Video Production MCP Suite**. All servers are built using `FastMCP` over `stdio` and are 100% compliant with standard Model Context Protocol clients (Claude Desktop, Antigravity Desktop, Cursor, OpenAI Codex), as well as direct CLI execution via `cli_runner.py`.

---

## Architecture Overview

```text
servers/
├── cli_runner.py               # Unified CLI dispatcher for Next.js Web UI & automation
├── workspace_paths.py          # Workspace filesystem scoping & path sanitization
│
├── daw_studio_mcp/             # MODULE 1: Audio Separation, Mixing, VST3 Hosting & DAW Bridge
│   ├── server.py               # FastMCP Server definition & exported tools
│   ├── vst3_manager.py         # Category A-D VST3 scanner (FabFilter, Ozone, soothe2, Neural DSP)
│   ├── stem_separator.py       # Pretrained Demucs htdemucs_6s 6-source separation
│   ├── guitar_decomposer.py    # Experimental 3-way guitar decomposition (Rhythm, Lead, Add.)
│   ├── vocal_decomposer.py     # Experimental 3-way vocal decomposition with lip-sync gating
│   ├── orchestra_decomposer.py # Timbre & envelope detection for strings, brass, winds
│   ├── mashup_engine.py        # Drum transient BPM tracking & cleaned harmonic key detection
│   ├── mix_master_engine.py    # Gain staging, LUFS balancing & VST3 mastering chain runner
│   └── daw_bridge.py           # REAPER (.rpp) with SD3/ReaTune & Ableton (.als) session generator
│
├── tab_transcriber_mcp/        # MODULE 2: Audio-to-Tab, Neural ONNX & DAW MIDI Importer
│   ├── server.py               # FastMCP Server definition & exported tools
│   ├── models/nmp.onnx         # Spotify Basic Pitch ONNX neural network model
│   ├── pre_cleaner.py          # VST3 pre-cleaning (Pro-Q 4, soothe2, RX 11 de-bleed)
│   ├── pitch_tracker.py        # ONNX neural transcription & sub-band drum transient detection
│   ├── fretboard_solver.py     # Viterbi 4-fret hand-box, Drop Tunings & Bowed Strings
│   ├── gp5_exporter.py         # Multi-track Guitar Pro 5 (.gp5) & MusicXML exporter
│   ├── daw_midi_importer.py    # MIDI importer for SD3 Tracker, REAPER, Ableton & RipX
│   └── visual_prompt_mapper.py # Nano Banana 2.1 & Google Veo keyframe prompt generator
│
└── capcut_director_mcp/        # MODULE 3: Automated CapCut Timeline & Video Assembler
    ├── server.py               # FastMCP Server definition & exported tools
    ├── draft_manager.py        # Wrapper around CapCut Desktop draft_content.json timelines
    ├── beat_cutter.py          # Micro speed-ramping, transient hard cuts & multi-angle shots
    └── fx_injector.py          # Breakdown zoom punch, camera shake & white flash keyframes
```

---

## 1. `daw_studio_mcp` (Module 1)

**Role:** Handles neural source separation, stem audio engineering, VST3 plugin hosting, and multitrack DAW project generation.

### Exported MCP Tools:
- `separate_audio_stems(audio_path, model_name, output_dir, segment_sec)`:
  Runs pretrained Demucs (`htdemucs_6s`) to extract `vocals`, `drums`, `bass`, `guitar`, `piano`, and `other`.
- `mashup_replace_segment(base_stem, donor_stem, base_range, donor_range, output_path)`:
  Splices audio segments with automatic BPM time-stretching, harmonic pitch-shifting, and 15ms cosine crossfades.
- `auto_mix_and_master(stems_dir, genre_profile, target_lufs, reference_audio)`:
  Executes automated stem gain staging, dynamic resonance de-harshing, reference mastering via Matchering 2.0, and True-Peak limiting at `-0.5 dBTP`.
- `generate_reaper_project(project_name, stem_paths, bpm, musical_key, ...)`:
  Generates a REAPER `.rpp` session with 5 organized bus folders, automatically routing **Superior Drummer 3** on drums, **ReaTune** on bass/vocal/lead, and **Neural DSP Archetype** on guitar buses.
- `export_ableton_live_set(project_name, stem_paths, bpm, ...)`:
  Generates a native compressed Ableton Live 12 Set (`.als`) with unwarped audio tracks mapped to stems.

---

## 2. `tab_transcriber_mcp` (Module 2)

**Role:** Converts audio stems into human-playable multi-track tablature (`.gp5`, `.musicxml`) and video sync coordinates (`visual_sync_map.json`).

### Key Components:
- **VST3 Pre-Cleaner (`pre_cleaner.py`):**
  Uses `pedalboard` to route audio through FabFilter Pro-Q 4, soothe2, or RX 11 Guitar De-noise. Removes sub-rumble < 75 Hz and cymbal sizzle > 5.5 kHz to prevent false notes.
- **Offline ONNX Neural Transcriber (`pitch_tracker.py`):**
  Uses Spotify Basic Pitch (`nmp.onnx`) running on `onnxruntime` (CPU/GPU) without TensorFlow. Detects 88 MIDI pitches across full polyphony.
- **Hybrid DAW MIDI Importer (`daw_midi_importer.py`):**
  Parses `.mid` files exported from **Superior Drummer 3 Tracker**, **REAPER ReaTune**, **Ableton**, or **Hit'n'Mix RipX DeepAudio** using `music21`, running the Viterbi solver on the exact verified notes.
- **Biomechanical Viterbi Solver (`fretboard_solver.py`):**
  Constrains fret assignments to an ergonomic 4-fret hand-box, optimizes transitions using dynamic programming, and handles 1-finger barre power chords for Drop tunings.

### Exported MCP Tools:
- `transcribe_stems_to_gp5_and_sync_map(project_name, bpm, musical_key, tuning_name, ...)`:
  Executes pre-cleaning, ONNX transcription, Viterbi solving, and exports `.gp5`, `.musicxml`, and `visual_sync_map.json`.
- `import_daw_midi(project_name, midi_path, tuning_name, bpm, musical_key, ...)`:
  Imports DAW MIDI and maps it to Guitar Pro 5 and video prompts with 100% accuracy.

---

## 3. `capcut_director_mcp` (Module 3)

**Role:** Automates video timeline editing in CapCut Desktop based on the acoustic coordinates from `visual_sync_map.json`.

### Key Components:
- **`draft_manager.py`:** Locates and parses CapCut Desktop draft folders (`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`).
- **`beat_cutter.py`:** Slices Veo video clips on transient drum/guitar hits and applies micro speed-ramping to match clip motion to song tempo.
- **`fx_injector.py`:** Injects camera shake, hard zoom punch, and white flash keyframes during heavy breakdowns and guitar transitions.

### Exported MCP Tools:
- `list_and_classify_footage(footage_dir)`: Scans footage and identifies motion tags.
- `assemble_capcut_music_video(project_name, sync_map_path, footage_dir, ...)`: Generates a complete CapCut draft project.

---

## 4. CLI Runner (`cli_runner.py`)

A universal command-line bridge allowing the Next.js Studio UI or bash/PowerShell scripts to execute MCP tools directly without an LLM:

```bash
# Example: Scan installed VST3 plugins
.venv\Scripts\python.exe servers/cli_runner.py scan_vst3

# Example: Import DAW MIDI to GP5 and sync map
.venv\Scripts\python.exe servers/cli_runner.py import_daw_midi --params "{\"project_name\":\"MySong\",\"midi_path\":\"workspace/output_tabs/MySong.mid\",\"tuning\":\"Standard E\"}"
```
