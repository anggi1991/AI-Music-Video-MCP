"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Play,
  Pause,
  Square,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Volume2,
  Music,
  Download,
  FolderOpen,
  Sliders,
  Maximize2,
  Check,
  RefreshCw,
  Sparkles,
} from "lucide-react";

interface SongsterrTabViewerProps {
  projectName: string;
  gp5FileName?: string;
  musicXmlFileName?: string;
  bpm?: number;
  musicalKey?: string;
}

declare global {
  interface Window {
    alphaTab: any;
  }
}

export default function SongsterrTabViewer({
  projectName,
  gp5FileName = "Fearless_my_tears.gp5",
  musicXmlFileName = "Fearless_my_tears.musicxml",
  bpm = 140,
  musicalKey = "C Minor",
}: SongsterrTabViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<any>(null);

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [tracks, setTracks] = useState<any[]>([]);
  const [selectedTrackIndex, setSelectedTrackIndex] = useState<number>(0);
  const [staveProfile, setStaveProfile] = useState<"default" | "tab" | "score">("default");
  const [layoutMode, setLayoutMode] = useState<"horizontal" | "page">("page");
  const [zoom, setZoom] = useState<number>(1.0);
  const [currentTime, setCurrentTime] = useState<string>("0:00");
  const [totalTime, setTotalTime] = useState<string>("0:00");

  const tabApiUrl = `/api/tabs/file?file=workspace/output_tabs/${encodeURIComponent(gp5FileName)}`;
  const musicXmlApiUrl = `/api/tabs/file?file=workspace/output_tabs/${encodeURIComponent(musicXmlFileName)}`;

  // Load alphaTab script dynamically from reliable CDN
  useEffect(() => {
    let isMounted = true;

    const loadAlphaTab = () => {
      if (window.alphaTab) {
        initAlphaTab();
        return;
      }

      const existingScript = document.getElementById("alphatab-script");
      if (existingScript) {
        existingScript.addEventListener("load", () => {
          if (isMounted) initAlphaTab();
        });
        return;
      }

      const script = document.createElement("script");
      script.id = "alphatab-script";
      script.src = "https://cdn.jsdelivr.net/npm/@coderline/alphatab@1.3.0/dist/alphaTab.js";
      script.async = true;
      script.onload = () => {
        if (isMounted) initAlphaTab();
      };
      script.onerror = () => {
        if (isMounted) {
          setLoading(false);
          setLoadError("Failed to load alphaTab interactive engine. Please check your internet connection.");
        }
      };
      document.body.appendChild(script);
    };

    const initAlphaTab = () => {
      if (!containerRef.current || !window.alphaTab) return;

      try {
        if (apiRef.current) {
          apiRef.current.destroy();
          apiRef.current = null;
        }

        const settings = {
          file: tabApiUrl,
          core: {
            engine: "svg",
            logLevel: "error",
          },
          display: {
            staveProfile: staveProfile,
            layoutMode: layoutMode,
            scale: zoom,
          },
          player: {
            enablePlayer: true,
            soundFont: "https://cdn.jsdelivr.net/npm/@coderline/alphatab@1.3.0/dist/soundfont/sonivox.sf2",
            scrollElement: scrollContainerRef.current,
          },
        };

        const api = new window.alphaTab.AlphaTabApi(containerRef.current, settings);
        apiRef.current = api;

        api.scoreLoaded.on((score: any) => {
          if (!isMounted) return;
          setLoading(false);
          setTracks(score.tracks || []);
          if (score.tracks && score.tracks.length > 0) {
            setSelectedTrackIndex(score.tracks[0].index);
          }
        });

        api.playerStateChanged.on((args: any) => {
          if (!isMounted) return;
          setIsPlaying(args.state === 1);
        });

        api.playerPositionChanged.on((args: any) => {
          if (!isMounted) return;
          const curSec = Math.floor(args.currentTime / 1000);
          const endSec = Math.floor(args.endTime / 1000);
          const fmt = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
          setCurrentTime(fmt(curSec));
          setTotalTime(fmt(endSec));
        });

        api.error.on((err: any) => {
          if (!isMounted) return;
          console.warn("AlphaTab render warning:", err);
        });
      } catch (err: any) {
        if (isMounted) {
          setLoading(false);
          setLoadError(`Interactive Tab Render Error: ${err.message}`);
        }
      }
    };

    loadAlphaTab();

    return () => {
      isMounted = false;
      if (apiRef.current) {
        try {
          apiRef.current.destroy();
        } catch {
          // ignore
        }
        apiRef.current = null;
      }
    };
  }, [tabApiUrl]);

  // Update Track
  const handleSelectTrack = (trackIndex: number) => {
    setSelectedTrackIndex(trackIndex);
    if (apiRef.current && apiRef.current.score) {
      const selected = apiRef.current.score.tracks.find((t: any) => t.index === trackIndex);
      if (selected) {
        apiRef.current.renderTracks([selected]);
      }
    }
  };

  // Update Stave Profile (Not Balok + Fret Angka vs Fret Saja vs Balok Saja)
  const handleChangeStaveProfile = (profile: "default" | "tab" | "score") => {
    setStaveProfile(profile);
    if (apiRef.current) {
      apiRef.current.settings.display.staveProfile = profile;
      apiRef.current.updateSettings();
      apiRef.current.render();
    }
  };

  // Update Layout Mode (Horizontal endless scroll vs Page)
  const handleChangeLayout = (mode: "horizontal" | "page") => {
    setLayoutMode(mode);
    if (apiRef.current) {
      apiRef.current.settings.display.layoutMode = mode;
      apiRef.current.updateSettings();
      apiRef.current.render();
    }
  };

  // Zoom Controls
  const handleZoom = (delta: number) => {
    const newZoom = Math.min(1.8, Math.max(0.6, Number((zoom + delta).toFixed(2))));
    setZoom(newZoom);
    if (apiRef.current) {
      apiRef.current.settings.display.scale = newZoom;
      apiRef.current.updateSettings();
      apiRef.current.render();
    }
  };

  // Play / Pause
  const handlePlayPause = () => {
    if (apiRef.current) {
      apiRef.current.playPause();
    }
  };

  // Stop / Rewind
  const handleStop = () => {
    if (apiRef.current) {
      apiRef.current.stop();
      apiRef.current.tickPosition = 0;
      setIsPlaying(false);
    }
  };

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col mb-6">
      {/* Top Songsterr-Style Header Bar */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-950 to-slate-900 border-b border-slate-800/80 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
            <Music className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white tracking-wide">{projectName}</h3>
              <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full font-mono font-bold">
                Songsterr Interactive Score
              </span>
            </div>
            <p className="text-[11px] text-slate-400 flex items-center gap-2">
              <span>BPM: <strong className="text-cyan-400">{bpm}</strong></span>
              <span>•</span>
              <span>Key: <strong className="text-emerald-400">{musicalKey}</strong></span>
              <span>•</span>
              <span>Tuning: <strong className="text-violet-300">Drop C / Standard</strong></span>
            </p>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2">
          <a
            href={tabApiUrl}
            download={gp5FileName}
            className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
            title="Download Guitar Pro 5 binary file"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span>.GP5 File</span>
          </a>
          <a
            href={musicXmlApiUrl}
            download={musicXmlFileName}
            className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
            title="Download MusicXML score"
          >
            <Download className="w-3.5 h-3.5 text-violet-400" />
            <span>.MusicXML</span>
          </a>
        </div>
      </div>

      {/* Secondary Controls Bar: Tracks, Playback, View Options */}
      <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Track Selector Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-0.5">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider mr-1">Instrument:</span>
          {tracks.length > 0 ? (
            tracks.map((track) => (
              <button
                key={track.index}
                onClick={() => handleSelectTrack(track.index)}
                className={`px-3 py-1 rounded-lg font-semibold text-xs transition cursor-pointer flex items-center gap-1.5 ${
                  selectedTrackIndex === track.index
                    ? "bg-violet-600 text-white shadow-md shadow-violet-600/30"
                    : "bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/60"
                }`}
              >
                <span>{track.name || `Track ${track.index + 1}`}</span>
              </button>
            ))
          ) : (
            <span className="text-slate-500 italic text-[11px]">Loading tracks...</span>
          )}
        </div>

        {/* View Mode Switches (Not Balok + Fret Angka) */}
        <div className="flex items-center gap-3">
          {/* Stave Profile Toggle */}
          <div className="flex items-center bg-slate-950 rounded-lg border border-slate-800 p-0.5">
            <button
              onClick={() => handleChangeStaveProfile("default")}
              className={`px-2 py-1 rounded text-[11px] font-medium transition cursor-pointer ${
                staveProfile === "default" ? "bg-violet-700 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
              title="Standard Notation (Not Balok) + Guitar Tablature (Fret Angka)"
            >
              Balok + Tab
            </button>
            <button
              onClick={() => handleChangeStaveProfile("tab")}
              className={`px-2 py-1 rounded text-[11px] font-medium transition cursor-pointer ${
                staveProfile === "tab" ? "bg-violet-700 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
              title="Guitar Tablature Only (Fret Angka Saja)"
            >
              Tab Saja
            </button>
            <button
              onClick={() => handleChangeStaveProfile("score")}
              className={`px-2 py-1 rounded text-[11px] font-medium transition cursor-pointer ${
                staveProfile === "score" ? "bg-violet-700 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
              title="Standard Musical Staff Only (Not Balok Saja)"
            >
              Balok Saja
            </button>
          </div>

          {/* Layout Mode (Horizontal vs Page) */}
          <div className="flex items-center bg-slate-950 rounded-lg border border-slate-800 p-0.5">
            <button
              onClick={() => handleChangeLayout("page")}
              className={`px-2 py-1 rounded text-[11px] font-medium transition cursor-pointer ${
                layoutMode === "page" ? "bg-emerald-600 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
              title="Page Layout (Halaman Lembar Musik)"
            >
              Page View
            </button>
            <button
              onClick={() => handleChangeLayout("horizontal")}
              className={`px-2 py-1 rounded text-[11px] font-medium transition cursor-pointer ${
                layoutMode === "horizontal" ? "bg-emerald-600 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
              title="Songsterr Horizontal Track Scrolling"
            >
              Songsterr Scroll
            </button>
          </div>

          {/* Zoom Buttons */}
          <div className="flex items-center gap-1 bg-slate-950 rounded-lg border border-slate-800 px-1 py-0.5">
            <button
              onClick={() => handleZoom(-0.15)}
              className="p-1 hover:text-white text-slate-400 cursor-pointer"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[10px] font-mono text-slate-300 px-1">{Math.round(zoom * 100)}%</span>
            <button
              onClick={() => handleZoom(0.15)}
              className="p-1 hover:text-white text-slate-400 cursor-pointer"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Tablature Display Area (Songsterr Canvas) */}
      <div
        ref={scrollContainerRef}
        className="relative bg-[#121316] p-6 min-h-[500px] max-h-[680px] overflow-auto flex justify-center"
      >
        {loading && (
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center gap-3 z-20">
            <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
            <p className="text-sm font-semibold text-slate-200">
              Rendering Songsterr Tablature & Standard Notation...
            </p>
            <p className="text-xs text-slate-400">
              Parsing 6-string fret positions, palm mutes, and measure bars from {gp5FileName}.
            </p>
          </div>
        )}

        {loadError && (
          <div className="absolute inset-0 bg-slate-950 flex flex-col items-center justify-center p-6 text-center z-20">
            <p className="text-red-400 font-semibold mb-2">{loadError}</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs rounded-xl border border-slate-700 cursor-pointer"
            >
              Reload Score
            </button>
          </div>
        )}

        {/* AlphaTab Target Element with Dark Inversion Filter for High-Contrast Studio Look */}
        <div
          ref={containerRef}
          className="w-full max-w-5xl alphatab-container rounded-xl text-slate-100"
          style={{
            // High-contrast dark styling for alphaTab's crisp vector rendering
            filter: "invert(92%) hue-rotate(180deg) brightness(1.05) contrast(1.1)",
          }}
        />
      </div>

      {/* Bottom Transport Bar (Songsterr Audio Synthesizer Controls) */}
      <div className="bg-slate-900 border-t border-slate-800 px-4 py-2.5 flex items-center justify-between text-xs text-slate-300">
        <div className="flex items-center gap-3">
          <button
            onClick={handlePlayPause}
            className="w-9 h-9 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 flex items-center justify-center font-bold shadow-lg shadow-emerald-500/30 transition cursor-pointer"
            title={isPlaying ? "Pause Score Playback" : "Play Score Synthesizer"}
          >
            {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
          </button>
          <button
            onClick={handleStop}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center transition cursor-pointer"
            title="Stop / Rewind to Measure 1"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
          </button>

          <div className="flex items-center gap-1.5 font-mono text-xs bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-emerald-400 font-bold">{currentTime}</span>
            <span className="text-slate-600">/</span>
            <span className="text-slate-400">{totalTime}</span>
          </div>
        </div>

        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5 text-cyan-400 font-medium">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Interactive Real-Time Cursor Tracking</span>
          </span>
          <span>•</span>
          <span>Double-click any measure to jump playback</span>
        </div>
      </div>
    </div>
  );
}
