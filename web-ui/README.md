# AI Music Video Production - Next.js Studio UI

A modern, responsive desktop dashboard built with **Next.js 16 (Turbopack)**, **Tailwind CSS**, and **Lucide Icons** that serves as the visual command center for the Universal AI Music & Video Production MCP Suite.

---

## Features

- **Dual-Mode Dispatcher:** Switch on the fly between **Direct Python MCP Engine** (instant local execution via `cli_runner.py`) and **Agent CLI Dispatcher** (Claude Code, Antigravity, Cursor, OpenAI Codex).
- **Interactive Songsterr Tablature Viewer (`SongsterrTabViewer.tsx`):**
  - Integrated **AlphaTab** engine rendering full-band multi-track tablature and standard notation directly in the browser.
  - Realistic multi-track playback using browser SoundFonts with solo, mute, volume, and tempo scaling controls.
  - Real-time measure and cursor tracking.
- **Hybrid DAW MIDI Importer:** 1-click import for `.mid` files from Superior Drummer 3 Tracker, REAPER, Ableton, or RipX.
- **4 Specialized Workflow Tabs:**
  1. **Stem Separation & Mashup Splicer:** Demucs 6-stem controls, anti-bleed gates, and segment crossfade splicing.
  2. **VST3 Mix & DAW Project:** Category A-D VST3 inspector, LUFS target sliders, Matchering reference selector, and 1-click launchers for REAPER (.rpp) and Ableton Live (.als).
  3. **Tablature (.gp5) & Visual Prompts:** AlphaTab visual score, tuning/key selector, and keyframe prompt explorer.
  4. **Veo Footage & CapCut Director:** Footage validator and automated CapCut Desktop timeline builder.
- **Two-Way Synced Prompt Drawer:** Live terminal logs, auto-generated system prompts, and custom prompt override playground.

---

## Getting Started

### Prerequisites
- Node.js 18+ or 20+
- Installed project Python virtual environment (`.venv`)

### Launching the Web UI

#### Option 1: 1-Click Batch Launcher (Recommended)
From the repository root, double-click:
```bat
start_studio_ui.bat
```

#### Option 2: Manual Development Mode
```bash
cd web-ui
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

#### Option 3: Production Build
```bash
npm run build
npm run start
```

---

## API Routes Overview

- **`POST /api/execute`:**
  Dual-mode execution handler. When `mode === "direct_mcp"`, spawns `servers/cli_runner.py` with sanitized parameters. When `mode === "agent_cli"`, passes the structured prompt to your selected AI coding agent.
- **`GET /api/workspace`:**
  Real-time inspection of the workspace directory. Scans `workspace/source_songs/`, `workspace/input_stems/`, `workspace/output_tabs/`, and parses `visual_sync_map.json` for live dashboard metrics.
- **`GET /api/audio?path=...`:**
  Range-request audio streaming endpoint for browser playback of source songs and separated stems.
- **`GET /api/tabs/file?path=...`:**
  Binary streaming endpoint serving `.gp5` tablature files to the AlphaTab viewer.
