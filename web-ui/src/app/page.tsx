"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Play,
  Square,
  Sliders,
  Music,
  Scissors,
  Video,
  FileCode,
  Terminal,
  Cpu,
  Layers,
  Sparkles,
  Copy,
  Check,
  RefreshCw,
  FolderOpen,
  Volume2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Settings,
  Send,
  Wand2,
} from "lucide-react";

type EngineMode = "direct" | "claude" | "antigravity" | "codex";
type TabType = "separation" | "mixing" | "tabs" | "video";

export default function StudioDashboard() {
  // Global State
  const [engine, setEngine] = useState<EngineMode>("direct");
  const [activeTab, setActiveTab] = useState<TabType>("separation");
  const [audioPath, setAudioPath] = useState("");
  const [projectName, setProjectName] = useState("");
  const [genreProfile, setGenreProfile] = useState("metalcore");
  const [targetLufs, setTargetLufs] = useState(-9.0);
  const [autoVst3, setAutoVst3] = useState(true);
  const [autoLaunchDaw, setAutoLaunchDaw] = useState(true);

  // Separation Toggles
  const [splitVocals, setSplitVocals] = useState(false);
  const [splitGuitars, setSplitGuitars] = useState(false);
  const [splitOrchestra, setSplitOrchestra] = useState(false);
  const [antiBleedGate, setAntiBleedGate] = useState(false);
  const [separationModel, setSeparationModel] = useState("htdemucs_6s");
  const [segmentSec, setSegmentSec] = useState("");

  // Mashup Form
  const [baseStem, setBaseStem] = useState("");
  const [donorStem, setDonorStem] = useState("");
  const [baseStart, setBaseStart] = useState(0.0);
  const [baseEnd, setBaseEnd] = useState(2.0);
  const [donorStart, setDonorStart] = useState(0.0);
  const [donorEnd, setDonorEnd] = useState(2.0);

  // VST3 Registry
  const [vst3Data, setVst3Data] = useState<any>(null);
  const [loadingVst, setLoadingVst] = useState(false);

  // Workspace Files & Sync Map
  const [workspace, setWorkspace] = useState<any>(null);
  const [stemPreviews, setStemPreviews] = useState<any[]>([]);
  const [syncMapFilter, setSyncMapFilter] = useState("All");
  const [customModifiers, setCustomModifiers] = useState<Record<number, string>>({});

  // CapCut Form
  const [capcutDraftName, setCapcutDraftName] = useState("New_Project_MV");

  // Console & Logs
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [executing, setExecuting] = useState(false);
  const [activeOperation, setActiveOperation] = useState("");

  // Prompt Drawer & Override
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [manualPromptOverride, setManualPromptOverride] = useState("");
  const [isManualOverride, setIsManualOverride] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);

  // Fetch workspace on load
  const refreshWorkspace = async () => {
    try {
      const res = await fetch("/api/workspace");
      const data = await res.json();
      if (data.status === "success") {
        setWorkspace(data.workspace);
        if (data.workspace.audio_candidates && data.workspace.audio_candidates.length > 0 && !audioPath) {
          const first = data.workspace.audio_candidates[0];
          setAudioPath(first.path);
          const name = first.name.replace(/\.[^.]+$/, "").replace(/[^\p{L}\p{N}]+/gu, "_").replace(/^_+|_+$/g, "");
          setProjectName(name);
          setCapcutDraftName(`${name}_MV`);
        } else if (!data.workspace.audio_candidates?.length) {
          setAudioPath("");
          setProjectName("");
        }
        const safeProject = projectName.trim().replace(/[^\p{L}\p{N}_-]+/gu, "_").replace(/^_+|_+$/g, "").toLowerCase();
        const experimentalNames = new Set(["guitar_rhythm.wav", "guitar_lead.wav", "guitar_additional.wav", "vocal_lead.wav", "vocal_co_lead.wav", "vocal_backing.wav", "strings_ensemble.wav", "violin.wav", "cello.wav", "brass.wav", "choir.wav"]);
        setStemPreviews((data.workspace.input_stems || []).filter((f: any) =>
          f.relativePath.toLowerCase().startsWith(`input_stems/${safeProject}/`) && f.relativePath.toLowerCase().endsWith(".wav")
        ).map((f: any) => ({ ...f, sourceType: experimentalNames.has(f.name.toLowerCase()) ? "Experimental DSP Mask" : "Pretrained Model Estimate" })));
      }
    } catch (e) {
      addLog("Failed to fetch workspace files.");
    }
  };

  useEffect(() => {
    refreshWorkspace();
  }, []);

  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setConsoleLogs((prev) => [`[${timestamp}] ${msg}`, ...prev.slice(0, 80)]);
  };

  // Real-time Master Prompt Assembler (Two-Way Binding)
  const assembledPrompt = useMemo(() => {
    let p = `Project: ${projectName}\n`;
    p += `Master Audio: ${audioPath}\n`;
    p += `Engine Selected: ${engine.toUpperCase()}\n`;
    p += `--------------------------------------------------\n`;
    if (activeTab === "separation") {
      p += `Task: Separate stems & Sub-stem decomposition\n`;
      p += `- Separation backend: ${separationModel}\n`;
      p += `- Model segment override: ${segmentSec || "model default"} seconds\n`;
      p += `- Experimental heuristic vocal/guitar/orchestra sub-stems (not reliable source separation): ${splitVocals || splitGuitars || splitOrchestra ? "REQUESTED" : "OFF"}\n`;
      p += `- Anti-Bleed Noise Gate: ${antiBleedGate ? "ACTIVE" : "OFF"}\n`;
    } else if (activeTab === "mixing") {
      p += `Task: Flagship VST3 Mix & Master + DAW Session Generation\n`;
      p += `- Genre Profile: ${genreProfile}\n`;
      p += `- Target Loudness: ${targetLufs} LUFS\n`;
      p += `- Flagship VST3 Arsenal: ${autoVst3 ? "Category A (Ozone/Soothe/FabFilter) & Category C (Parallax/Gojira)" : "Internal DSP"}\n`;
      p += `- Generate REAPER .rpp with 5 folder buses, GUITAR RE-TRACK Human DI, & VSTi MIDI items.\n`;
    } else if (activeTab === "tabs") {
      p += `Task: Audio-to-Tablature (.gp5 / .musicxml) & Visual Coordinate Generation\n`;
      p += `- Viterbi 4-fret Hand Box solver with Drop-tuning detection.\n`;
      p += `- Bowed strings tuning (Violin G-D-A-E, Cello C-G-D-A) & Vocal melody notation.\n`;
      p += `- Build visual_sync_map.json with Nano Banana 2.1 & Veo motion prompts.\n`;
    } else if (activeTab === "video") {
      p += `Task: Automated Beat-Synced CapCut Desktop Assembler\n`;
      p += `- Draft Name: ${capcutDraftName}\n`;
      p += `- Align Veo footage clips to BPM with micro speed-ramping.\n`;
      p += `- Inject camera scale punch (112%), white flash & screen shake keyframes.\n`;
    }
    return p;
  }, [
    projectName,
    audioPath,
    engine,
    activeTab,
    splitVocals,
    splitGuitars,
    splitOrchestra,
    antiBleedGate,
    separationModel,
    segmentSec,
    genreProfile,
    targetLufs,
    autoVst3,
    capcutDraftName,
  ]);

  // Keep manual prompt in sync when not overridden
  useEffect(() => {
    if (!isManualOverride) {
      setManualPromptOverride(assembledPrompt);
    }
  }, [assembledPrompt, isManualOverride]);

  // Execute Action via Dual-Dispatcher
  const handleExecute = async (action: string, customParams: any = {}) => {
    setExecuting(true);
    setActiveOperation(action);
    addLog(`Initiating action: ${action} [Mode: ${engine === "direct" ? "Direct MCP Python" : `Agent CLI (${engine})`}]`);

    try {
      const payload: any = {
        mode: engine === "direct" ? "direct_mcp" : "agent_cli",
        engine,
        action,
        params: {
          project_name: projectName,
          audio_path: audioPath.replace(/^["']|["']$/g, "").trim(),
          model_name: separationModel,
          segment_sec: segmentSec ? Number(segmentSec) : undefined,
          output_dir: `workspace/input_stems/${projectName.trim().replace(/[^\p{L}\p{N}_-]+/gu, "_").replace(/^_+|_+$/g, "")}`,
          genre_profile: genreProfile,
          target_lufs: targetLufs,
          auto_use_detected_vst3: autoVst3,
          apply_bleed_gate: antiBleedGate,
          split_guitar_substems: splitGuitars,
          split_vocal_substems: splitVocals,
          split_orchestral_substems: splitOrchestra,
          draft_name: capcutDraftName,
          generate_als: true,
          launch_ableton: autoLaunchDaw,
          launch_reaper: autoLaunchDaw,
          ...customParams,
        },
      };

      if (isManualOverride && manualPromptOverride.trim()) {
        payload.customPromptOverride = manualPromptOverride.trim();
      }

      const res = await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (data.status === "success" || data.status === "partial") {
        addLog(`${data.status.toUpperCase()}: ${action} completed with status ${data.result?.status || data.status}.`);
        if (data.result) {
          addLog(`Result: ${JSON.stringify(data.result, null, 2)}`);
          if (action === "separate_stems" && data.result.telemetry) {
            const t = data.result.telemetry;
            addLog(`VRAM telemetry: ${t.device}; ${t.duration_sec ?? "n/a"}s; allocated ${t.peak_allocated_mb ?? "n/a"} MB; reserved ${t.peak_reserved_mb ?? "n/a"} MB.`);
          }
        }
        if (data.message) {
          addLog(`${data.message}`);
        }
        if (data.stdout) {
          addLog(`Agent Output: ${data.stdout}`);
        }
        await refreshWorkspace();
      } else {
        addLog(`ERROR in ${action}: ${data.message || JSON.stringify(data)}`);
      }
    } catch (err: any) {
      addLog(`Execution failed: ${err.message}`);
    } finally {
      setExecuting(false);
      setActiveOperation("");
    }
  };

  // VST3 Scan
  const handleScanVst = async () => {
    setLoadingVst(true);
    addLog("Scanning C:\\Program Files\\Common Files\\VST3 for Categories A-D plugins...");
    try {
      const res = await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "direct_mcp", action: "scan_vst3" }),
      });
      const data = await res.json();
      if (data.status === "success" && data.result) {
        setVst3Data(data.result);
        addLog(`Discovered ${data.result.total_plugins_found} VST3 plugins across Categories A-D.`);
      }
    } catch (e: any) {
      addLog(`VST3 scan failed: ${e.message}`);
    } finally {
      setLoadingVst(false);
    }
  };

  // Copy prompt helper
  const handleCopyPrompt = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(id);
    setTimeout(() => setCopiedIndex(null), 2000);
    addLog(`Copied prompt to clipboard: "${text.slice(0, 50)}..."`);
  };

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-violet-600 selection:text-white">
      {/* ============================================================== */}
      {/* TOP NAVIGATION & GLOBAL CONTROL BAR                            */}
      {/* ============================================================== */}
      <header className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-violet-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-300 via-cyan-200 to-emerald-300">
              AI Music & Video MCP Studio
            </h1>
            <p className="text-xs text-slate-400">
              DAW Engineering • Multi-Guitar & Bowed Strings • CapCut Director
            </p>
          </div>
        </div>

        {/* Center: Engine Selector & Master Audio */}
        <div className="flex items-center gap-3 bg-slate-950/80 p-1.5 rounded-xl border border-slate-800">
          <div className="flex items-center space-x-1.5 px-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-medium text-slate-300">Engine:</span>
          </div>
          <select
            value={engine}
            onChange={(e) => setEngine(e.target.value as EngineMode)}
            className="bg-slate-900 text-xs font-semibold text-slate-200 border border-slate-700 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500 cursor-pointer"
          >
            <option value="direct">⚡ Direct Python MCP Engine (Instant)</option>
            <option value="claude">🤖 Claude Code CLI / Desktop</option>
            <option value="antigravity">🚀 Antigravity Desktop / Gemini CLI</option>
            <option value="codex">🧠 OpenAI Codex CLI</option>
          </select>

          {workspace?.audio_candidates?.length > 0 ? (
            <select
              value={audioPath}
              onChange={(e) => {
                const selectedPath = e.target.value;
                const selected = workspace.audio_candidates.find((c: any) => c.path === selectedPath);
                setAudioPath(selectedPath.replace(/^["']|["']$/g, "").trim());
                if (selected) {
                  const name = selected.name.replace(/\.[^.]+$/, "").replace(/[^\p{L}\p{N}]+/gu, "_").replace(/^_+|_+$/g, "");
                  setProjectName(name);
                  setCapcutDraftName(`${name}_MV`);
                }
              }}
              className="bg-slate-900 text-xs font-semibold text-cyan-300 border border-cyan-500/40 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-400 max-w-[200px] truncate cursor-pointer"
              title="Select a source song from workspace/source_songs"
            >
              {workspace.audio_candidates.map((c: any) => (
                <option key={c.path} value={c.path}>
                  🎵 {c.relativePath}
                </option>
              ))}
            </select>
          ) : <span className="text-xs text-amber-300">Belum ada file sumber di workspace/source_songs/</span>}
        </div>

        {/* Right: 1-Click Run Pipeline */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExecute("run_full_pipeline")}
            disabled={executing || !audioPath}
            className="flex items-center space-x-2 bg-gradient-to-r from-violet-600 via-indigo-600 to-emerald-600 hover:from-violet-500 hover:to-emerald-500 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-lg shadow-violet-600/30 transition-all duration-150 disabled:opacity-50 cursor-pointer"
          >
            {executing && activeOperation === "run_full_pipeline" ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4 fill-current" />
            )}
            <span>RUN FULL PIPELINE (1-CLICK)</span>
          </button>
        </div>
      </header>

      {/* ============================================================== */}
      {/* 4 WORKFLOW TABS                                               */}
      {/* ============================================================== */}
      <nav className="bg-slate-900 border-b border-slate-800 px-6 py-2 flex items-center space-x-2">
        <button
          onClick={() => setActiveTab("separation")}
          className={`flex items-center space-x-2 text-xs font-semibold px-4 py-2 rounded-lg transition-colors cursor-pointer ${
            activeTab === "separation"
              ? "bg-violet-600/20 text-violet-300 border border-violet-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          }`}
        >
          <Scissors className="w-4 h-4 text-violet-400" />
          <span>1. Stem Separation & Mashup</span>
        </button>

        <button
          onClick={() => setActiveTab("mixing")}
          className={`flex items-center space-x-2 text-xs font-semibold px-4 py-2 rounded-lg transition-colors cursor-pointer ${
            activeTab === "mixing"
              ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          }`}
        >
          <Sliders className="w-4 h-4 text-cyan-400" />
          <span>2. VST3 Mix & DAW Project</span>
        </button>

        <button
          onClick={() => setActiveTab("tabs")}
          className={`flex items-center space-x-2 text-xs font-semibold px-4 py-2 rounded-lg transition-colors cursor-pointer ${
            activeTab === "tabs"
              ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          }`}
        >
          <Music className="w-4 h-4 text-emerald-400" />
          <span>3. Tablature (.GP5) & Visual Prompts</span>
        </button>

        <button
          onClick={() => setActiveTab("video")}
          className={`flex items-center space-x-2 text-xs font-semibold px-4 py-2 rounded-lg transition-colors cursor-pointer ${
            activeTab === "video"
              ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          }`}
        >
          <Video className="w-4 h-4 text-indigo-400" />
          <span>4. Veo Footage & CapCut Director</span>
        </button>
      </nav>

      {/* ============================================================== */}
      {/* MAIN WORKFLOW AREA                                             */}
      {/* ============================================================== */}
      <main className="flex-1 p-6 pb-48 max-w-7xl mx-auto w-full">
        {/* TAB 1: STEM SEPARATION & MASHUP SPLICER */}
        {activeTab === "separation" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2 mb-4">
                <Scissors className="w-5 h-5 text-violet-400" />
                <span>6-Stem Separation & Multi-Stem Sub-Decomposition</span>
              </h2>

              <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-slate-950 rounded-xl border border-violet-500/30 mb-5">
                <div className="flex items-center space-x-2.5 truncate max-w-2xl">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-violet-400 bg-violet-950/80 px-2.5 py-1 rounded-md border border-violet-800/40">
                    Target Song
                  </span>
                  <span className="text-xs text-cyan-300 font-mono font-semibold truncate">
                    {audioPath || "Belum ada file sumber di workspace/source_songs/"}
                  </span>
                </div>
                {workspace?.audio_candidates && workspace.audio_candidates.length > 0 && (
                  <select
                    value={audioPath}
                    onChange={(e) => {
                      const selectedPath = e.target.value;
                      const selected = workspace.audio_candidates.find((c: any) => c.path === selectedPath);
                      setAudioPath(selectedPath);
                      if (selected) {
                        const name = selected.name.replace(/\.[^.]+$/, "").replace(/[^\p{L}\p{N}]+/gu, "_").replace(/^_+|_+$/g, "");
                        setProjectName(name);
                        setCapcutDraftName(`${name}_MV`);
                      }
                    }}
                    className="bg-slate-900 text-xs font-semibold text-slate-200 border border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none focus:border-cyan-500 cursor-pointer"
                  >
                    {workspace.audio_candidates.map((c: any) => (
                      <option key={c.path} value={c.path}>
                        🎵 {c.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <label className="block mb-5">
                <span className="text-xs text-slate-400 block mb-1">Project name</span>
                <input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="Nama proyek dari file sumber" className="w-full max-w-lg bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200" />
              </label>

              <label className="block mb-5 max-w-lg">
                <span className="text-xs text-slate-400 block mb-1">Separation backend</span>
                <select value={separationModel} onChange={(e) => setSeparationModel(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200">
                  <option value="htdemucs_6s">Demucs HT 6-source estimate (default)</option>
                  <option value="cascaded_separation">Cascaded models (unavailable: no verified stages configured)</option>
                </select>
                <span className="text-[11px] text-slate-500 block mt-1">Cascade remains unavailable until verified task-specific weights and output mappings are configured.</span>
              </label>

              <label className="block mb-5 max-w-lg">
                <span className="text-xs text-slate-400 block mb-1">Model segment override (seconds, optional)</span>
                <input type="number" min="1" step="0.5" value={segmentSec} onChange={(e) => setSegmentSec(e.target.value)} placeholder="Use model default" className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200" />
                <span className="text-[11px] text-slate-500 block mt-1">If CUDA runs out of memory, retry with a shorter segment. Leave blank to use the model's default split.</span>
              </label>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <label className="flex items-center justify-between p-3.5 bg-slate-950 rounded-xl border border-slate-800 hover:border-slate-700 cursor-pointer">
                  <div>
                    <div className="text-xs font-bold text-slate-200">
                      Experimental Heuristic DSP Mask (Not Source Separation) — vocals
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Center/side and pitch filters can retain instrument bleed
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={splitVocals}
                    onChange={(e) => setSplitVocals(e.target.checked)}
                    className="w-4 h-4 accent-violet-600 cursor-pointer"
                  />
                </label>

                <label className="flex items-center justify-between p-3.5 bg-slate-950 rounded-xl border border-slate-800 hover:border-slate-700 cursor-pointer">
                  <div>
                    <div className="text-xs font-bold text-slate-200">
                      Experimental Heuristic DSP Mask (Not Source Separation) — guitar
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Frequency, transient and stereo masks can retain other instruments
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={splitGuitars}
                    onChange={(e) => setSplitGuitars(e.target.checked)}
                    className="w-4 h-4 accent-violet-600 cursor-pointer"
                  />
                </label>

                <label className="flex items-center justify-between p-3.5 bg-slate-950 rounded-xl border border-slate-800 hover:border-slate-700 cursor-pointer">
                  <div>
                    <div className="text-xs font-bold text-slate-200">
                      Experimental Heuristic DSP Mask (Not Source Separation) — orchestra
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Broad spectral filters; labels and stems are not source-isolated
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={splitOrchestra}
                    onChange={(e) => setSplitOrchestra(e.target.checked)}
                    className="w-4 h-4 accent-violet-600 cursor-pointer"
                  />
                </label>

                <label className="flex items-center justify-between p-3.5 bg-slate-950 rounded-xl border border-slate-800 hover:border-slate-700 cursor-pointer">
                  <div>
                    <div className="text-xs font-bold text-slate-200">
                      Post-separation filters and gate
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Can suppress quiet notes and tails; does not separate instruments
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={antiBleedGate}
                    onChange={(e) => setAntiBleedGate(e.target.checked)}
                    className="w-4 h-4 accent-violet-600 cursor-pointer"
                  />
                </label>
              </div>

              <button
                onClick={() => handleExecute("separate_stems")}
                disabled={executing || !audioPath || !projectName.trim()}
                className="bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-violet-600/20 transition-all cursor-pointer"
              >
                Run Stem Decomposition
              </button>
              {stemPreviews.length > 0 && (
                <section className="mt-6 border-t border-slate-800 pt-5">
                  <h3 className="text-sm font-bold mb-3">Generated stem previews</h3>
                  <div className="grid gap-3 md:grid-cols-2">
                    {stemPreviews.map((stem: any) => (
                      <div key={stem.relativePath} className="rounded-xl border border-slate-800 bg-slate-950 p-3">
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span className="text-xs font-semibold text-slate-200">{stem.name}</span>
                          <span className={`text-[10px] rounded-full px-2 py-1 ${stem.sourceType === "Experimental DSP Mask" ? "bg-amber-950 text-amber-200" : "bg-cyan-950 text-cyan-200"}`}>
                            {stem.sourceType}
                          </span>
                        </div>
                        <audio controls preload="none" className="w-full" src={`/api/audio?file=${encodeURIComponent(stem.relativePath)}`} />
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>

            {/* Cross-Song Mashup Splicer Panel */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2 mb-4">
                <Layers className="w-5 h-5 text-indigo-400" />
                <span>Frankenstein Mashup Splicer (Auto-BPM & Shortest Key Pitch Shift)</span>
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Base Stem (Song A):</label>
                  <input
                    type="text"
                    value={baseStem}
                    onChange={(e) => setBaseStem(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                  />
                  <div className="flex gap-2 mt-2">
                    <input
                      type="number"
                      step="0.1"
                      value={baseStart}
                      onChange={(e) => setBaseStart(parseFloat(e.target.value))}
                      className="w-1/2 bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-xs text-slate-200"
                      placeholder="Start (sec)"
                    />
                    <input
                      type="number"
                      step="0.1"
                      value={baseEnd}
                      onChange={(e) => setBaseEnd(parseFloat(e.target.value))}
                      className="w-1/2 bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-xs text-slate-200"
                      placeholder="End (sec)"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1">Donor Stem (Song B):</label>
                  <input
                    type="text"
                    value={donorStem}
                    onChange={(e) => setDonorStem(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                  />
                  <div className="flex gap-2 mt-2">
                    <input
                      type="number"
                      step="0.1"
                      value={donorStart}
                      onChange={(e) => setDonorStart(parseFloat(e.target.value))}
                      className="w-1/2 bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-xs text-slate-200"
                      placeholder="Extract Start (sec)"
                    />
                    <input
                      type="number"
                      step="0.1"
                      value={donorEnd}
                      onChange={(e) => setDonorEnd(parseFloat(e.target.value))}
                      className="w-1/2 bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-xs text-slate-200"
                      placeholder="Extract End (sec)"
                    />
                  </div>
                </div>
              </div>

              <button
                onClick={() =>
                  handleExecute("mashup", {
                    base_stem_path: baseStem,
                    donor_stem_path: donorStem,
                    base_replace_start: baseStart,
                    base_replace_end: baseEnd,
                    donor_extract_start: donorStart,
                    donor_extract_end: donorEnd,
                  })
                }
                disabled={executing}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-600/20 cursor-pointer"
              >
                Execute Auto-BPM/Key Mashup (15ms Cosine Crossfade)
              </button>
            </div>
          </div>
        )}

        {/* TAB 2: FLAGSHIP VST3 MIX, MASTER & DAW PROJECT */}
        {activeTab === "mixing" && (
          <div className="space-y-6">
            {/* VST3 Scanner Grid */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2">
                    <Sliders className="w-5 h-5 text-cyan-400" />
                    <span>Flagship VST3 & VSTi Arsenal (Categories A–D)</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Ozone 11/12, FabFilter, soothe2, Nectar 4, Valhalla, Neural DSP Parallax/Gojira, Superior Drummer 3
                  </p>
                </div>
                <button
                  onClick={handleScanVst}
                  disabled={loadingVst}
                  className="bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 text-xs font-bold px-3 py-1.5 rounded-lg flex items-center space-x-1.5 cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingVst ? "animate-spin" : ""}`} />
                  <span>Scan Installed VST3</span>
                </button>
              </div>

              {vst3Data ? (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                    <span className="text-[10px] font-bold tracking-wider uppercase text-cyan-400 block mb-2">
                      Category A: Mastering & De-Harshing
                    </span>
                    <ul className="space-y-1 text-slate-300">
                      {Object.keys(vst3Data.category_a_mastering_and_surgical || {}).slice(0, 6).map((k) => (
                        <li key={k} className="truncate">• {k}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                    <span className="text-[10px] font-bold tracking-wider uppercase text-violet-400 block mb-2">
                      Category B: Vocals & Reverb
                    </span>
                    <ul className="space-y-1 text-slate-300">
                      {Object.keys(vst3Data.category_b_vocals_and_reverb || {}).slice(0, 6).map((k) => (
                        <li key={k} className="truncate">• {k}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                    <span className="text-[10px] font-bold tracking-wider uppercase text-emerald-400 block mb-2">
                      Category C: Guitar & Bass
                    </span>
                    <ul className="space-y-1 text-slate-300">
                      {Object.keys(vst3Data.category_c_guitar_and_bass || {}).slice(0, 6).map((k) => (
                        <li key={k} className="truncate">• {k}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                    <span className="text-[10px] font-bold tracking-wider uppercase text-indigo-400 block mb-2">
                      Category D: Virtual Instruments
                    </span>
                    <ul className="space-y-1 text-slate-300">
                      {Object.keys(vst3Data.category_d_virtual_instruments || {}).slice(0, 6).map((k) => (
                        <li key={k} className="truncate">• {k}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6 text-slate-500 text-xs">
                  Click "Scan Installed VST3" to load your 57+ detected system plugins.
                </div>
              )}
            </div>

            {/* Mix & Master Controls */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2 mb-4">
                <Volume2 className="w-5 h-5 text-emerald-400" />
                <span>Stem Mixing, Reference Mastering & DAW Project</span>
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Genre Profile:</label>
                  <select
                    value={genreProfile}
                    onChange={(e) => setGenreProfile(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                  >
                    <option value="metalcore">Metalcore / Modern Heavy Rock</option>
                    <option value="rock">Classic / Alternative Rock</option>
                    <option value="orchestral">Cinematic Orchestral / Soundtracks</option>
                    <option value="pop">Pop / Commercial Radio</option>
                    <option value="electronic">EDM / Cyberpunk Synthwave</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1">
                    Target Integrated Loudness: <span className="text-cyan-400 font-bold">{targetLufs} LUFS</span>
                  </label>
                  <input
                    type="range"
                    min="-14.0"
                    max="-7.0"
                    step="0.5"
                    value={targetLufs}
                    onChange={(e) => setTargetLufs(parseFloat(e.target.value))}
                    className="w-full mt-2 accent-cyan-500 cursor-pointer"
                  />
                </div>

                <div className="flex flex-col space-y-2 justify-center">
                  <label className="flex items-center space-x-2 text-xs font-semibold text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoVst3}
                      onChange={(e) => setAutoVst3(e.target.checked)}
                      className="w-4 h-4 accent-cyan-500 cursor-pointer"
                    />
                    <span>Auto-Apply Flagship VST3 Chains (Ozone / FabFilter)</span>
                  </label>

                  <label className="flex items-center space-x-2 text-xs font-semibold text-indigo-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoLaunchDaw}
                      onChange={(e) => setAutoLaunchDaw(e.target.checked)}
                      className="w-4 h-4 accent-indigo-500 cursor-pointer"
                    />
                    <span>Auto-Launch DAW (Ableton / REAPER) on Generation</span>
                  </label>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => handleExecute("mix_master")}
                  disabled={executing}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-lg shadow-emerald-600/20 cursor-pointer"
                >
                  Render Master Audio (.wav)
                </button>

                <button
                  onClick={() => handleExecute("create_reaper_rpp")}
                  disabled={executing}
                  className="bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-lg shadow-cyan-600/20 cursor-pointer"
                >
                  Generate REAPER Project (.rpp) with 5 Buses & VSTi
                </button>

                <button
                  onClick={() => handleExecute("create_ableton")}
                  disabled={executing}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-lg shadow-indigo-600/20 cursor-pointer"
                >
                  Generate & Open in Ableton Live (.als)
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: TABLATURE & VISUAL PROMPT EXPLORER */}
        {activeTab === "tabs" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2">
                    <Music className="w-5 h-5 text-emerald-400" />
                    <span>Full-Band Tablature (.GP5 / .MusicXML) & Visual Sync Map</span>
                  </h2>
                  <p className="text-xs text-slate-400">
                    Anatomically accurate tabs (Guitars, Bass, Drums, Violin, Cello, Vocals) with prompt coordinates
                  </p>
                </div>
                <button
                  onClick={() => handleExecute("transcribe_tabs")}
                  disabled={executing}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-4 py-2 rounded-xl shadow-lg shadow-emerald-600/20 cursor-pointer"
                >
                  Transcribe Stems to .GP5 & Sync Map
                </button>
              </div>

              {/* Interactive Sync Map Viewer */}
              {workspace?.sync_map ? (
                <div>
                  <div className="flex items-center justify-between p-4 bg-slate-950 rounded-xl border border-slate-800 mb-4">
                    <div className="flex gap-6 text-xs">
                      <div>
                        <span className="text-slate-400">BPM:</span>{" "}
                        <span className="font-bold text-cyan-400">{workspace.sync_map.bpm}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Key:</span>{" "}
                        <span className="font-bold text-emerald-400">{workspace.sync_map.musical_key}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Events Total:</span>{" "}
                        <span className="font-bold text-violet-400">{workspace.sync_map.events?.length || 0}</span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 text-xs">
                      <span className="text-slate-400">Filter Instrument:</span>
                      <select
                        value={syncMapFilter}
                        onChange={(e) => setSyncMapFilter(e.target.value)}
                        className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200"
                      >
                        <option value="All">All Instruments</option>
                        <option value="vocal_lead">vocal_lead</option>
                        <option value="vocal_co_lead">vocal_co_lead</option>
                        <option value="guitar_rhythm">guitar_rhythm</option>
                        <option value="guitar_lead">guitar_lead</option>
                        <option value="drums">drums</option>
                        <option value="violin">violin</option>
                        <option value="cello">cello</option>
                      </select>
                    </div>
                  </div>

                  {/* Timeline Cards */}
                  <div className="space-y-3 max-h-[480px] overflow-y-auto pr-2">
                    {workspace.sync_map.events
                      ?.filter((ev: any) => syncMapFilter === "All" || ev.instrument === syncMapFilter)
                      .slice(0, 50)
                      .map((ev: any, idx: number) => {
                        const modifier = customModifiers[idx] || "";
                        const finalNbPrompt = modifier
                          ? `${ev.nano_banana_keyframe_prompt}, ${modifier}`
                          : ev.nano_banana_keyframe_prompt;
                        const finalVeoPrompt = modifier
                          ? `${ev.veo_motion_prompt}, ${modifier}`
                          : ev.veo_motion_prompt;

                        return (
                          <div
                            key={idx}
                            className="bg-slate-950 p-4 rounded-xl border border-slate-800 hover:border-slate-700 transition-all text-xs"
                          >
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center space-x-2">
                                <span className="bg-slate-800 text-slate-300 font-mono text-[10px] px-2 py-0.5 rounded">
                                  {ev.start_time_sec}s - {ev.end_time_sec}s
                                </span>
                                <span className="font-bold text-violet-300 uppercase tracking-wide">
                                  {ev.instrument}
                                </span>
                                <span className="bg-violet-950/60 text-violet-300 text-[10px] px-2 py-0.5 rounded-full border border-violet-800/40">
                                  {ev.playing_state}
                                </span>
                              </div>

                              <div className="flex items-center space-x-2">
                                <input
                                  type="text"
                                  value={modifier}
                                  onChange={(e) =>
                                    setCustomModifiers((prev) => ({ ...prev, [idx]: e.target.value }))
                                  }
                                  placeholder="Custom Modifier (e.g. glowing neon eyes)..."
                                  className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 w-56 focus:outline-none focus:border-violet-500"
                                />

                                <button
                                  onClick={() => handleCopyPrompt(finalNbPrompt, `nb-${idx}`)}
                                  className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded flex items-center space-x-1 cursor-pointer"
                                >
                                  {copiedIndex === `nb-${idx}` ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3 text-cyan-400" />
                                  )}
                                  <span className="text-[10px]">Copy Nano Banana</span>
                                </button>

                                <button
                                  onClick={() => handleCopyPrompt(finalVeoPrompt, `veo-${idx}`)}
                                  className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded flex items-center space-x-1 cursor-pointer"
                                >
                                  {copiedIndex === `veo-${idx}` ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3 text-emerald-400" />
                                  )}
                                  <span className="text-[10px]">Copy Veo</span>
                                </button>
                              </div>
                            </div>

                            <p className="text-slate-400 text-[11px] italic">
                              "{finalNbPrompt.slice(0, 140)}..."
                            </p>
                          </div>
                        );
                      })}
                  </div>
                </div>
              ) : (
                <div className="text-center py-10 text-slate-500 text-xs">
                  No visual_sync_map.json found in workspace/output_tabs. Run transcription to populate this table.
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: VEO FOOTAGE & CAPCUT AUTO-DIRECTOR */}
        {activeTab === "video" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2 mb-4">
                <Video className="w-5 h-5 text-indigo-400" />
                <span>Veo Footage Manager & CapCut Timeline Assembler</span>
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">CapCut Project Draft Name:</label>
                  <input
                    type="text"
                    value={capcutDraftName}
                    onChange={(e) => setCapcutDraftName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                  />
                </div>

                <div className="flex items-end">
                  <button
                    onClick={() => handleExecute("assemble_capcut", { draft_name: capcutDraftName })}
                    disabled={executing}
                    className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-bold text-xs py-2.5 rounded-xl shadow-lg shadow-indigo-600/20 cursor-pointer"
                  >
                    🎬 Assemble Beat-Synced CapCut Project
                  </button>
                </div>
              </div>

              {/* Footage Checklist */}
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wide mb-3">
                  Footage Clips in workspace/veo_footage/
                </h3>
                {workspace?.veo_footage && workspace.veo_footage.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    {workspace.veo_footage.map((file: any) => (
                      <div
                        key={file.name}
                        className="bg-slate-900 px-3 py-2 rounded-lg border border-slate-800 flex items-center justify-between text-xs"
                      >
                        <span className="truncate text-slate-300">{file.name}</span>
                        <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 text-slate-500 text-xs">
                    No .mp4 footage found in workspace/veo_footage/.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ============================================================== */}
      {/* DRAWER: AGENT PROMPT & CUSTOM OVERRIDE WORKSPACE                */}
      {/* ============================================================== */}
      <footer className="fixed bottom-0 left-0 right-0 z-40 bg-slate-900 border-t border-slate-800 shadow-2xl transition-all">
        <div className="flex items-center justify-between px-6 py-2.5 bg-slate-950 border-b border-slate-800 cursor-pointer" onClick={() => setDrawerOpen(!drawerOpen)}>
          <div className="flex items-center space-x-2">
            <Terminal className="w-4 h-4 text-violet-400" />
            <span className="text-xs font-bold text-slate-200">
              Agent Prompt & Custom Override Workspace (Two-Way Synced)
            </span>
            {isManualOverride && (
              <span className="bg-amber-500/20 text-amber-300 text-[10px] font-semibold px-2 py-0.5 rounded border border-amber-500/30">
                Manual Override Active
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <span className="text-[11px] text-slate-400">
              {drawerOpen ? "Collapse Drawer" : "Expand Drawer"}
            </span>
            {drawerOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </div>
        </div>

        {drawerOpen && (
          <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4 max-h-72">
            {/* Live Console Output */}
            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 flex flex-col font-mono text-[11px]">
              <span className="text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-1">
                Live Studio Log
              </span>
              <div className="flex-1 overflow-y-auto space-y-1 text-slate-300 max-h-48 pr-1">
                {consoleLogs.map((log, i) => (
                  <div key={i} className="truncate">{log}</div>
                ))}
              </div>
            </div>

            {/* Large Two-Way Agent Prompt Textarea */}
            <div className="md:col-span-2 flex flex-col space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400 text-[11px]">
                  Type custom instructions freely or let UI presets build it:
                </span>
                {isManualOverride && (
                  <button
                    onClick={() => {
                      setIsManualOverride(false);
                      setManualPromptOverride(assembledPrompt);
                    }}
                    className="text-cyan-400 hover:underline text-[11px] cursor-pointer"
                  >
                    Reset to UI Presets
                  </button>
                )}
              </div>

              <textarea
                value={manualPromptOverride}
                onChange={(e) => {
                  setManualPromptOverride(e.target.value);
                  setIsManualOverride(true);
                }}
                rows={5}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-violet-500 resize-none"
              />

              <div className="flex justify-end gap-2">
                <button
                  onClick={() => handleCopyPrompt(manualPromptOverride, "manual-drawer")}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1 cursor-pointer"
                >
                  {copiedIndex === "manual-drawer" ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                  <span>Copy Prompt</span>
                </button>

                <button
                  onClick={() => handleExecute(activeTab === "separation" ? "separate_stems" : (activeTab === "mixing" ? "mix_master" : (activeTab === "tabs" ? "transcribe_tabs" : "assemble_capcut")))}
                  disabled={executing}
                  className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold text-xs px-4 py-1.5 rounded-lg shadow flex items-center space-x-1.5 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Dispatch Custom Prompt to Agent ({engine.toUpperCase()})</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </footer>
    </div>
  );
}
