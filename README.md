# Universal AI Music & Video Production MCP Suite (`music-video-mcp-suite`)

Suite of 3 Universal Model Context Protocol (MCP) servers built with Python (`FastMCP`) over `stdio` for Claude Code Desktop, Antigravity Desktop, Claude Desktop, and Cursor / OpenAI Codex, accompanied by a **Next.js Web UI Studio Dashboard** with Dual-Dispatcher capabilities.

Currently implemented:
- **Demucs `htdemucs_6s` separation:** vocals, drums, bass, guitar, piano, and other.
- **Experimental sub-stem masks:** guitar, vocal, and orchestra DSP masks; not validated source separation and disabled by default.
- **Phase 11 source isolation:** the song dropdown reads only `workspace/source_songs/`; generated outputs are stored per project under `workspace/input_stems/<project_name>/`.
- **Honest separation metadata and previews:** Demucs output labels, model caveats, measured inference telemetry, structured CUDA OOM errors, and browser playback for generated WAV stems.
- **Pluggable cascade status:** task-specific cascades remain unavailable until verified weights, licenses, and output-label mappings are configured. Existing heuristic decomposers remain preserved and marked experimental.
- **Mixing and REAPER project skeletons:** available VST3 plugin paths may be added; no MIDI replacement notes are fabricated.
- **Automatic tablature and visual sync drafts:** Guitar Pro 5, MusicXML, and timed events, all requiring human review.
- **CapCut draft tooling and Next.js dashboard:** availability depends on valid footage/assets and the target application's installed plugins.

---

## Directory Structure

```text
music-video-mcp-suite/
├── PRD.md
├── start_studio_ui.bat             # 1-Click launcher to open Web UI on http://localhost:3000
├── mcp_config.json                 # Ready-to-use config with Windows absolute paths
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Test runner configuration (with VST3 safe faulthandler)
├── README.md                       # Setup & usage documentation
├── shared_schemas/
│   ├── __init__.py
│   └── sync_map_schema.py          # Flexible Pydantic models for Audio-Tab-Video JSON contract
├── servers/
│   ├── cli_runner.py               # CLI bridge between Web UI and Python MCP backend
│   ├── daw_studio_mcp/             # MODULE 1: Audio Mashup, Warping, Mixing & Mastering
│   │   ├── server.py
│   │   ├── vst3_manager.py         # Category A-D VST3/VSTi scanner, parameter inspector & role chains
│   │   ├── stem_separator.py       # htdemucs_6s source separation; never silently substitutes filterbank DSP
│   │   ├── guitar_decomposer.py    # Hybrid M/S + Salience 3-Way Guitar Decomposition
│   │   ├── vocal_decomposer.py     # 3-Way Vocal Decomposition with Lip-Sync Readiness Gating
│   │   ├── orchestra_decomposer.py # Orchestral acoustic detection & selective stem decomposition
│   │   ├── mashup_engine.py        # BPM Time-Stretch, Key Detection & Pitch-Shift
│   │   ├── mix_master_engine.py    # Stem EQ/Comp/LUFS Balancing, Reference & Flagship VST3 Mastering
│   │   └── daw_bridge.py           # REAPER .rpp generator, Ableton manifest & OSC transport bridge
│   ├── tab_transcriber_mcp/        # MODULE 2: Audio-to-Tab (.gp5) & Visual Coordinate Generator
│   │   ├── server.py
│   │   ├── pitch_tracker.py        # Pitch tracking & frequency-band drum onset detection
│   │   ├── fretboard_solver.py     # Viterbi solver (Guitars, Bass, Violin, Viola, Cello, Vocals)
│   │   ├── gp5_exporter.py         # Multi-Track GP5 & MusicXML generator (Band, Strings, Vocals)
│   │   └── visual_prompt_mapper.py # Nano Banana 2.1 & Veo prompts (Bowing, Singers, Guitars)
│   └── capcut_director_mcp/        # MODULE 3: Automated CapCut Timeline & Beat-Sync Assembler
│       ├── server.py
│       ├── draft_manager.py        # Resolves %LOCALAPPDATA% CapCut draft folders
│       ├── beat_cutter.py          # Micro speed-ramping, transient hard cuts & multi-character shots
│       └── fx_injector.py          # Breakdown zoom / camera shake / white flash keyframes
├── web-ui/                         # Next.js Studio Dashboard (App Router, Tailwind, Lucide)
│   ├── src/
│   │   └── app/
│   │       ├── api/
│   │       │   ├── execute/route.ts   # Dual-Dispatcher (Direct Python MCP / Agent CLI)
│   │       │   └── workspace/route.ts # Real-time file & sync map inspector
│   │       ├── page.tsx               # Studio Dashboard with 4 Tabs & Prompt Playground
│   │       ├── layout.tsx
│   │       └── globals.css
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.mjs
├── vendor/
│   └── pyCapCut/                   # Vendored pyCapCut library
└── workspace/                      # User workspace assets
    ├── input_stems/
    ├── output_audio/
    ├── output_tabs/
    └── veo_footage/
```

---

## Launching the Web UI Studio Dashboard

Double-click `start_studio_ui.bat` in the project root:
```bat
start_studio_ui.bat
```

Place full-song source files (`.wav`, `.mp3`, or `.flac`) in `workspace/source_songs/`. That directory feeds the source-song dropdown; generated audio, stems, tablature, and video assets stay outside the source catalog.
This automatically starts the Next.js studio server on `http://localhost:3000` and opens your default browser.

Or manually start the development server:
```bash
cd web-ui
npm run dev
```

### Dashboard Features:
1. **Execution Engine Selector:** Switch seamlessly between:
   - `⚡ Direct Python MCP Engine (Instant & Deterministic)`
   - `🤖 Claude Code CLI / Desktop`
   - `🚀 Antigravity Desktop / Gemini CLI`
   - `🧠 OpenAI Codex CLI`
2. **4 Workflow Tabs:**
   - **Tab 1: 🎚️ Stem Separation & Mashup Splicer:** Demucs six-source separation; optional vocal/guitar/orchestra DSP masks are experimental and disabled by default.
   - **Tab 2: 🎛️ VST3 Mix, Master & DAW Project:** Plugin discovery, LUFS controls, and REAPER session skeleton generation from existing audio files and installed plugins.
   - **Tab 3: 🎸 Tablature (.gp5) & Visual Prompt Explorer:** Full-band tab transcription, interactive timeline cards, 1-click copy for Nano Banana 2.1 & Veo prompts, with **Custom Modifiers** support.
   - **Tab 4: 🎬 Veo Footage Manager & CapCut Auto-Director:** Footage inspection, sync map requirement checklist, and automated CapCut Desktop project assembly.
3. **Agent Prompt & Custom Override Workspace (Two-Way Synced Drawer):**
   - Live Studio Terminal log output.
   - Real-time prompt assembly reflecting form changes with full manual override capabilities and one-click dispatch to AI agents.

---

## MCP Configuration (`mcp_config.json`)

Copy the configuration below into your Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`), Antigravity Desktop, or Cursor MCP configuration:

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

---

## Running All Unit Tests

Run the complete test suite across all 10 phases:

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```
*(39 tests covering Phase 1 through Phase 10)*

### Audio separation and output status

`separate_stems` requires the pretrained `htdemucs_6s` model. It stops without writing stems if the model cannot load; the optional DSP filterbank fallback is experimental and must not be treated as isolated instrument sources. The model's six labels are `drums`, `bass`, `other`, `vocals`, `guitar`, and `piano` (`piano` is not relabeled as `synth`).

The current guitar, vocal, and orchestra sub-decomposers use heuristic masks. They are disabled by default, labeled experimental when explicitly enabled, and excluded from the full pipeline's mastering/transcription inputs. They do not meet production source-separation quality. Automatic tablature and sync events are drafts and require human review.
