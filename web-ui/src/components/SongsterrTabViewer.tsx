"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  Play,
  Pause,
  Square,
  ZoomIn,
  ZoomOut,
  Volume2,
  VolumeX,
  Music,
  Download,
  RefreshCw,
  Sparkles,
  Layers,
  Radio,
} from "lucide-react";

interface SongsterrTabViewerProps {
  projectName: string;
  gp5FileName?: string;
  musicXmlFileName?: string;
  bpm?: number;
  musicalKey?: string;
  tuning?: string;
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
  bpm = 91,
  musicalKey = "D Major",
  tuning = "Standard E",
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
  const [layoutMode, setLayoutMode] = useState<"horizontal" | "page">("horizontal");
  const [zoom, setZoom] = useState<number>(1.0);
  const [currentTime, setCurrentTime] = useState<string>("0:00");
  const [totalTime, setTotalTime] = useState<string>("0:00");
  const [soloActiveTrack, setSoloActiveTrack] = useState<boolean>(true);

  const tabApiUrl = `/api/tabs/file?file=workspace/output_tabs/${encodeURIComponent(gp5FileName)}`;
  const musicXmlApiUrl = `/api/tabs/file?file=workspace/output_tabs/${encodeURIComponent(musicXmlFileName)}`;

  // Apply track soloing helper
  const applyTrackSoloing = useCallback((targetTrackIndex: number, isSolo: boolean) => {
    if (!apiRef.current || !apiRef.current.score) return;
    try {
      const allTracks = apiRef.current.score.tracks || [];
      if (allTracks.length === 0) return;

      if (isSolo) {
        const target = allTracks.find((t: any) => t.index === targetTrackIndex) || allTracks[0];
        // Un-solo all first, then solo the target
        apiRef.current.changeTrackSolo(allTracks, false);
        apiRef.current.changeTrackSolo([target], true);
      } else {
        // Un-solo all tracks -> full band audio mix
        apiRef.current.changeTrackSolo(allTracks, false);
      }
    } catch (e) {
      console.warn("Could not apply track solo state:", e);
    }
  }, []);

  // Load alphaTab script dynamically
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
          setLoadError("Failed to load alphaTab interactive engine. Please check your network connection.");
        }
      };
      document.body.appendChild(script);
    };

    const initAlphaTab = () => {
      if (!containerRef.current || !window.alphaTab) return;

      try {
        if (apiRef.current) {
          try {
            apiRef.current.destroy();
          } catch {
            // ignore
          }
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
            resources: {
              mainGlyphColor: "#f8fafc", // White/silver for notes and fret numbers
              secondaryGlyphColor: "#94a3b8", // Slate for stave lines
              scoreInfoColor: "#38bdf8", // Sky blue for header text
            },
          },
          player: {
            enablePlayer: true,
            // Use locally hosted Sonivox SoundFont with zero latency
            soundFont: "/soundfont/sonivox.sf2",
            scrollElement: scrollContainerRef.current,
            scrollMode: 1, // Continuous scrolling tracking active beat
            scrollOffsetX: 160,
            enableCursor: true,
            enableElementHighlighting: true,
          },
        };

        const api = new window.alphaTab.AlphaTabApi(containerRef.current, settings);
        apiRef.current = api;

        api.scoreLoaded.on((score: any) => {
          if (!isMounted) return;
          setLoading(false);
          const scoreTracks = score.tracks || [];
          setTracks(scoreTracks);
          if (scoreTracks.length > 0) {
            setSelectedTrackIndex(scoreTracks[0].index);
            // Default: solo the primary track so instrument timbre is clear
            if (soloActiveTrack) {
              api.changeTrackSolo([scoreTracks[0]], true);
            }
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

          // Auto-scroll fallback for Songsterr Horizontal View
          if (scrollContainerRef.current && layoutMode === "horizontal") {
            const container = scrollContainerRef.current;
            const cursorBeat = container.querySelector(".at-cursor-beat") as HTMLElement;
            if (cursorBeat) {
              const targetLeft = cursorBeat.offsetLeft - container.clientWidth / 3;
              if (Math.abs(container.scrollLeft - targetLeft) > 20) {
                container.scrollTo({
                  left: Math.max(0, targetLeft),
                  behavior: "smooth",
                });
              }
            }
          }
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
  }, [tabApiUrl, layoutMode]);

  // Update Track (View + Solo Synthesizer)
  const handleSelectTrack = (trackIndex: number) => {
    setSelectedTrackIndex(trackIndex);
    if (apiRef.current && apiRef.current.score) {
      const selected = apiRef.current.score.tracks.find((t: any) => t.index === trackIndex);
      if (selected) {
        apiRef.current.renderTracks([selected]);
        applyTrackSoloing(trackIndex, soloActiveTrack);
      }
    }
  };

  // Toggle Solo Instrument vs Full Band Mix
  const handleToggleSolo = () => {
    const nextSolo = !soloActiveTrack;
    setSoloActiveTrack(nextSolo);
    applyTrackSoloing(selectedTrackIndex, nextSolo);
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

  // Update Layout Mode (Songsterr Scroll vs Page View)
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
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({ left: 0, top: 0, behavior: "smooth" });
      }
    }
  };

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col mb-6">
      {/* AlphaTab Cursor & Highlight Styling (Songsterr Modern Aesthetic) */}
      <style jsx global>{`
        /* Active measure bar block highlight (green glow) */
        .at-cursor-bar {
          background: rgba(16, 185, 129, 0.22) !important;
          border-radius: 6px !important;
          box-shadow: inset 0 0 0 1.5px rgba(16, 185, 129, 0.55) !important;
          z-index: 1 !important;
        }

        /* Active playhead beat cursor line (cyan laser) */
        .at-cursor-beat {
          background: #38bdf8 !important;
          width: 3.5px !important;
          box-shadow: 0 0 14px rgba(56, 189, 248, 0.95), 0 0 3px #ffffff !important;
          border-radius: 2px !important;
          z-index: 25 !important;
        }

        /* Note symbol active playback glow */
        .at-highlight * {
          fill: #38bdf8 !important;
          stroke: #38bdf8 !important;
        }

        /* Beat selection highlight */
        .at-selection div {
          background: rgba(56, 189, 248, 0.18) !important;
          border-radius: 4px !important;
        }

        /* Hide default background canvas artifacts */
        .alphatab-container svg {
          background: transparent !important;
        }
      `}</style>

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
              <span>Tuning: <strong className="text-violet-300">{tuning || "Standard E"}</strong></span>
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

      {/* Control Bar: Instrument Tracks, Stave Layout, Solo Switch */}
      <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Track Selector Pills */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-slate-400 font-semibold text-[11px] uppercase tracking-wider mr-1">Instrument:</span>
          {tracks.length > 0 ? (
            tracks.map((track) => (
              <button
                key={track.index}
                onClick={() => handleSelectTrack(track.index)}
                className={`px-3 py-1.5 rounded-lg font-semibold text-xs transition cursor-pointer flex items-center gap-1.5 ${
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

          {/* Solo / Full Band Audio Switch */}
          <button
            onClick={handleToggleSolo}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-pointer ml-2 border ${
              soloActiveTrack
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-500/20"
                : "bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200"
            }`}
            title="When active, the synthesizer solos ONLY the selected instrument so you hear its true timbre clearly without clash"
          >
            <Radio className="w-3.5 h-3.5" />
            <span>{soloActiveTrack ? "Solo Active Track" : "Full Band Mix"}</span>
          </button>
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

          {/* Layout Mode (Horizontal endless scroll vs Page) */}
          <div className="flex items-center bg-slate-950 rounded-lg border border-slate-800 p-0.5">
            <button
              onClick={() => handleChangeLayout("horizontal")}
              className={`px-2.5 py-1 rounded text-[11px] font-medium transition cursor-pointer ${
                layoutMode === "horizontal" ? "bg-emerald-600 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
              title="Songsterr Continuous Horizontal Track Scrolling (View follows playhead cursor automatically)"
            >
              Songsterr Scroll
            </button>
            <button
              onClick={() => handleChangeLayout("page")}
              className={`px-2.5 py-1 rounded text-[11px] font-medium transition cursor-pointer ${
                layoutMode === "page" ? "bg-emerald-600 text-white font-bold" : "text-slate-400 hover:text-white"
              }`}
              title="Page Layout (Halaman Lembar Musik Tradisional)"
            >
              Page View
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
        className={`relative bg-[#121316] p-6 min-h-[500px] max-h-[680px] ${
          layoutMode === "horizontal"
            ? "block overflow-x-auto overflow-y-hidden"
            : "flex justify-center overflow-y-auto overflow-x-hidden"
        }`}
      >
        {loading && (
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center gap-3 z-30">
            <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
            <p className="text-sm font-semibold text-slate-200">
              Rendering Songsterr Tablature & Standard Notation...
            </p>
            <p className="text-xs text-slate-400">
              Loading 6-string fret positions, drum kits, and measure bars from {gp5FileName}.
            </p>
          </div>
        )}

        {loadError && (
          <div className="absolute inset-0 bg-slate-950 flex flex-col items-center justify-center p-6 text-center z-30">
            <p className="text-red-400 font-semibold mb-2">{loadError}</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs rounded-xl border border-slate-700 cursor-pointer"
            >
              Reload Score
            </button>
          </div>
        )}

        {/* AlphaTab Target Element with Native Dark Theme Styling */}
        <div
          ref={containerRef}
          className={`alphatab-container rounded-xl text-slate-100 ${
            layoutMode === "horizontal" ? "w-max min-w-full" : "w-full max-w-5xl"
          }`}
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
            <span>Real-Time Playhead Tracking (Active Bar Highlight & Auto-Follow)</span>
          </span>
          <span>•</span>
          <span>Double-click any measure to jump playback</span>
        </div>
      </div>
    </div>
  );
}
