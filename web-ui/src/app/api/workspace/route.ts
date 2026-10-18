import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const PROJECT_ROOT = path.resolve(process.cwd(), "..");

export async function GET() {
  try {
    const workspaceDir = path.join(PROJECT_ROOT, "workspace");
    const sourceSongsDir = path.join(workspaceDir, "source_songs");
    const inputStemsDir = path.join(workspaceDir, "input_stems");
    const outputAudioDir = path.join(workspaceDir, "output_audio");
    const outputTabsDir = path.join(workspaceDir, "output_tabs");
    const veoFootageDir = path.join(workspaceDir, "veo_footage");

    const getFiles = (dir: string, recursive = false) => {
      if (!fs.existsSync(dir)) return [];
      const files: { name: string; path: string; relativePath: string; size: number }[] = [];
      const walk = (current: string) => {
        for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
          const fullPath = path.join(current, entry.name);
          if (entry.isDirectory() && recursive) walk(fullPath);
          else if (entry.isFile()) files.push({
            name: entry.name,
            path: fullPath,
            relativePath: path.relative(workspaceDir, fullPath).replace(/\\/g, "/"),
            size: fs.statSync(fullPath).size,
          });
        }
      };
      walk(dir);
      return files;
    };

    let hardware = { cuda_available: false, device_name: "CPU" };
    const hardwarePath = path.join(workspaceDir, ".system_hardware.json");
    if (fs.existsSync(hardwarePath)) {
      try {
        hardware = JSON.parse(fs.readFileSync(hardwarePath, "utf-8"));
      } catch {
        // ignore
      }
    }

    let syncMap = null;
    const syncMapPath = path.join(outputTabsDir, "visual_sync_map.json");
    if (fs.existsSync(syncMapPath)) {
      try {
        syncMap = JSON.parse(fs.readFileSync(syncMapPath, "utf-8"));
      } catch {
        // ignore
      }
    }

    const audioCandidates: { name: string; path: string; relativePath: string }[] = [];
    const audioExtensions = new Set([".wav", ".mp3", ".flac"]);
    const walkAudioFiles = (dir: string) => {
      if (!fs.existsSync(dir)) return;
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) walkAudioFiles(fullPath);
        else if (entry.isFile() && audioExtensions.has(path.extname(entry.name).toLowerCase())) {
          audioCandidates.push({
            name: entry.name,
            path: fullPath,
            relativePath: path.relative(workspaceDir, fullPath).replace(/\\/g, "/"),
          });
        }
      }
    };
    fs.mkdirSync(sourceSongsDir, { recursive: true });
    walkAudioFiles(sourceSongsDir);
    audioCandidates.sort((a, b) => a.relativePath.localeCompare(b.relativePath));

    return NextResponse.json({
      status: "success",
      hardware,
      workspace: {
        hardware,
        audio_candidates: audioCandidates,
        source_status: audioCandidates.length ? "ready" : "empty",
        input_stems: getFiles(inputStemsDir, true),
        output_audio: getFiles(outputAudioDir),
        output_tabs: getFiles(outputTabsDir),
        veo_footage: getFiles(veoFootageDir),
        sync_map: syncMap,
      },
    });
  } catch (error: any) {
    return NextResponse.json(
      { status: "error", message: error.message },
      { status: 500 }
    );
  }
}
