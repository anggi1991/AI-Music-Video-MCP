import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");
const PYTHON_EXE = path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe");
const CLI_RUNNER = path.join(PROJECT_ROOT, "servers", "cli_runner.py");


function resolveAntigravityDispatch(prompt: string): { cliCmd: string; cliArgs: string[]; targetLabel: string } {
  // Option 1: Standalone Antigravity CLI ('agy') if in PATH
  try {
    const { execSync } = require("child_process");
    execSync("where.exe agy", { stdio: "ignore" });
    return {
      cliCmd: "agy",
      cliArgs: [prompt],
      targetLabel: "Antigravity CLI (agy)",
    };
  } catch {}

  // Option 2 (Fallback): Antigravity IDE CLI
  return {
    cliCmd: "antigravity-ide.cmd",
    cliArgs: ["chat", "-r", prompt],
    targetLabel: "Antigravity IDE (Chat Session)",
  };
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      mode = "direct_mcp", // "direct_mcp" | "agent_cli"
      engine = "direct", // "direct" | "claude" | "antigravity" | "codex"
      action,
      params = {},
      customPromptOverride,
    } = body;

    // -------------------------------------------------------------
    // Mode B: AI Agent CLI Dispatcher
    // -------------------------------------------------------------
    if (mode === "agent_cli" || engine !== "direct") {
      const promptToUse =
        customPromptOverride && customPromptOverride.trim()
          ? customPromptOverride.trim()
          : generateMasterPrompt(action, params);

      // Determine CLI executable command based on selected engine
      let cliCmd = "claude";
      let cliArgs = ["-p", promptToUse, "--mcp-config", path.join(PROJECT_ROOT, "mcp_config.json")];
      let agentTarget = engine;

      if (engine === "codex") {
        cliCmd = "codex";
        cliArgs = [promptToUse];
      } else if (engine === "antigravity") {
        const resolved = resolveAntigravityDispatch(promptToUse);
        cliCmd = resolved.cliCmd;
        cliArgs = resolved.cliArgs;
        agentTarget = resolved.targetLabel;
      }

      // If user requested dry-run or copy-only
      if (params.dry_run) {
        return NextResponse.json({
          status: "success",
          mode: "agent_cli",
          engine,
          cli_command: `${cliCmd} ${cliArgs.join(" ")}`,
          prompt: promptToUse,
          message: "Prompt compiled successfully for Agent CLI dispatch.",
        });
      }

      // Execute Agent CLI in background
      return new Promise<NextResponse>((resolve) => {
        try {
          const proc = spawn(cliCmd, cliArgs, {
            cwd: PROJECT_ROOT,
            shell: true,
          });

          let stdout = "";
          let stderr = "";

          proc.stdout.on("data", (d) => {
            stdout += d.toString();
          });
          proc.stderr.on("data", (d) => {
            stderr += d.toString();
          });

          proc.on("close", (code) => {
            const isSuccess = code === 0 && !stderr.includes("not recognized") && !stderr.includes("not found");
            resolve(
              NextResponse.json({
                status: isSuccess ? "success" : "error",
                mode: "agent_cli",
                engine,
                target: agentTarget,
                exit_code: code,
                cli_command: `${cliCmd} ${cliArgs.join(" ")}`,
                prompt: promptToUse,
                stdout: stdout || (isSuccess ? `Prompt dispatched to ${agentTarget} successfully.` : ""),
                stderr: stderr,
                message: isSuccess
                  ? `Prompt successfully sent to ${agentTarget}.`
                  : `Failed to dispatch prompt to ${agentTarget}: ${stderr || "exited with code " + code}`,
              })
            );
          });

          proc.on("error", (err) => {
            resolve(
                NextResponse.json({
                  status: "error",
                mode: "agent_cli",
                engine,
                cli_command: `${cliCmd} ${cliArgs.join(" ")}`,
                prompt: promptToUse,
                stdout: "",
                message: `Agent CLI could not be started: ${err.message}`,
                note: "The prompt was not executed.",
              })
            );
          });
        } catch (err: any) {
          resolve(
            NextResponse.json({
              status: "error",
              mode: "agent_cli",
              engine,
              prompt: promptToUse,
              message: `Agent CLI could not be started: ${err.message}`,
            })
          );
        }
      });
    }

    // -------------------------------------------------------------
    // Mode A: Direct Python MCP Engine Execution
    // -------------------------------------------------------------
    if (!action) {
      return NextResponse.json(
        { status: "error", message: "Action is required for direct_mcp mode." },
        { status: 400 }
      );
    }

    if (action === "reveal_in_explorer") {
      const rawTarget = params.file_path || "workspace/output_audio";
      let fullTarget = path.isAbsolute(rawTarget) ? rawTarget : path.resolve(PROJECT_ROOT, rawTarget);
      try {
        if (fs.existsSync(fullTarget)) {
          spawn("explorer.exe", [`/select,${fullTarget}`], { detached: true });
        } else {
          spawn("explorer.exe", [path.dirname(fullTarget)], { detached: true });
        }
        return NextResponse.json({ status: "success", message: "Explorer launched" });
      } catch (err: any) {
        return NextResponse.json({ status: "error", message: err.message }, { status: 500 });
      }
    }

    const cleanParams: Record<string, any> = {};
    for (const [k, v] of Object.entries(params)) {
      if (typeof v === "string") {
        cleanParams[k] = v.replace(/^["']|["']$/g, "").trim();
      } else {
        cleanParams[k] = v;
      }
    }

    return new Promise<NextResponse>((resolve) => {
      const pythonProcess = spawn(
        PYTHON_EXE,
        [CLI_RUNNER, action, "--params", JSON.stringify(cleanParams)],
        { cwd: PROJECT_ROOT }
      );

      let stdout = "";
      let stderr = "";

      pythonProcess.stdout.on("data", (data) => {
        stdout += data.toString();
      });

      pythonProcess.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      pythonProcess.on("close", (code) => {
        if (code !== 0) {
          try {
            const errJson = JSON.parse(stdout);
            resolve(NextResponse.json(errJson, { status: 500 }));
          } catch {
            resolve(
              NextResponse.json(
                {
                  status: "error",
                  code,
                  stderr: stderr || stdout,
                  message: `Process exited with code ${code}`,
                },
                { status: 500 }
              )
            );
          }
          return;
        }

        try {
          const parsed = JSON.parse(stdout);
          resolve(
            NextResponse.json({
              status: parsed.status || "success",
              mode: "direct_mcp",
              action,
              result: parsed,
            })
          );
        } catch {
          resolve(
            NextResponse.json({
              status: "success",
              mode: "direct_mcp",
              action,
              raw_output: stdout,
            })
          );
        }
      });

      pythonProcess.on("error", (err) => {
        resolve(
          NextResponse.json(
            {
              status: "error",
              message: `Failed to spawn Python process: ${err.message}`,
            },
            { status: 500 }
          )
        );
      });
    });
  } catch (err: any) {
    return NextResponse.json(
      { status: "error", message: err.message },
      { status: 500 }
    );
  }
}

function generateMasterPrompt(action: string, params: any): string {
  if (action === "run_full_pipeline") {
    return (
      `Run full AI music and video production pipeline for project "${params.project_name || "(derive from selected source file)"}".\n` +
      `- Audio File: "${params.audio_path || "(select from workspace/source_songs/)"}"\n` +
      `- Separate only with real pretrained source-separation models. Never use frequency bands, Mid/Side, HPSS, or gates as instrument isolation.\n` +
      `- Do not claim 3-way singer/guitar/orchestra separation unless a source-separation model for those classes actually ran and its outputs were audited. Report these as unavailable otherwise.\n` +
      `- Mixing & Mastering: Genre profile ${params.genre_profile || "metalcore"} at ${params.target_lufs || -9.0} LUFS using flagship VST3 chains (Ozone, FabFilter, soothe2).\n` +
      `- Generate a REAPER session skeleton from real output files. Insert only plugins that are actually installed and create MIDI only from transcribed events; never add sample/fallback notes.\n` +
      `- Label tablature and sync data as automatic drafts; report unsupported performance-level isolation or transcription honestly.\n` +
      `- Transcribe tablature (.gp5) & generate visual_sync_map.json.\n` +
      `- Assemble beat-synced CapCut Desktop music video timeline.`
    );
  } else if (action === "separate_stems") {
    return (
      `Separate audio file "${params.audio_path}" using the real pretrained htdemucs_6s model. Report the exact model, source labels, sample rate and output paths.\n` +
      `Do not substitute frequency-band, Mid/Side or HPSS filtering and do not report a fallback as successful isolation. Stop with an explicit error if the model is unavailable.\n` +
      `The current DSP vocal/guitar/orchestra routines are experimental masks only. Do not describe their outputs as isolated performers or instruments.` +
      (params.auto_polish_stems
        ? `\n- Auto-Polish Stems: ENABLED. Apply dynamic VST3 / Native DSP de-bleeding chain sequentially to all isolated stems and record applied chains in manifest.`
        : "")
    );
  } else if (action === "mix_master") {
    return (
      `Mix and master audio stems for genre "${params.genre_profile || "metalcore"}" targeting ${params.target_lufs || -9.0} LUFS.\n` +
      `Apply detected flagship VST3 chains (Ozone 11/12, FabFilter Pro-Q, soothe2, Parallax X) and export master.wav.`
    );
  } else if (action === "transcribe_tabs") {
    return (
      `Transcribe separated stems into human-playable multi-track Guitar Pro 5 (.gp5) and .musicxml.\n` +
      `Detect drop tuning, apply 4-fret hand-box Viterbi solver, map violin/cello bowed strings, and generate visual_sync_map.json.`
    );
  } else if (action === "assemble_capcut") {
    return (
      `Assemble beat-synchronized CapCut Desktop project "${params.draft_name}".\n` +
      `Read visual_sync_map.json, map Veo footage clips, apply micro speed-ramping to match song BPM, and inject breakdown camera shake/punch keyframes.`
    );
  } else if (action === "create_ableton") {
    return (
      `Generate native Ableton Live Set (.als) and session manifest for project "${params.project_name}".\n` +
      `- Map all separated audio stems (vocals, guitars, bass, drums, orchestra, piano) to individual audio tracks.\n` +
      `- Set arrangement timeline clips and project tempo to ${params.bpm || 140.0} BPM.\n` +
      `- Auto-launch Ableton Live 12 to open the generated project session.`
    );
  } else if (action === "import_daw_midi") {
    return (
      `Import verified DAW MIDI file "${params.midi_path || "workspace/output_tabs/song.mid"}" (from SD3 Tracker / REAPER / Ableton / RipX) into project "${params.project_name}".\n` +
      `- Solve anatomical 4-fret hand-box guitar positions using Viterbi algorithm with tuning "${params.tuning || "Standard E"}".\n` +
      `- Update .gp5 tablature, .musicxml, and visual_sync_map.json with 100% DAW MIDI accuracy.`
    );
  } else if (action === "create_reaper_rpp") {
    return (
      `Generate REAPER project (.rpp) with 5 folder buses, flagship VST3 chains, and VSTi tracks for project "${params.project_name}".\n` +
      `- Map all separated audio stems to their respective bus folders at ${params.bpm || 140.0} BPM.\n` +
      `- Set markers from visual_sync_map.json and include Archetype Gojira and Superior Drummer 3 tracks.`
    );
  }
  return `Execute MCP task "${action}" with parameters: ${JSON.stringify(params, null, 2)}`;
}
