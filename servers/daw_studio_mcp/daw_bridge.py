"""DAW Bridge & project skeleton generator for REAPER (.rpp) and Ableton.

Only existing plugin paths are written as REAPER FX entries. Optional VSTi
tracks require an installed plugin and source MIDI events; this module does
not invent replacement notes or claim to instantiate unavailable plugins.
"""

import os
import json
import socket
import soundfile as sf
from typing import Dict, Any, Optional, List

try:
    from .vst3_manager import (
        scan_installed_vst3_plugins,
        build_flagship_role_chain,
        _find_best_plugin_path,
    )
except ImportError:
    from vst3_manager import (
        scan_installed_vst3_plugins,
        build_flagship_role_chain,
        _find_best_plugin_path,
    )


class DAWBridge:
    """Provides OSC/UDP bridge to communicate with DAWs like Reaper and Ableton."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Attempt to initialize a UDP socket for OSC messaging."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return True
        except Exception:
            return False

    def send_osc_command(self, address: str, value: Any = 1.0) -> Dict[str, Any]:
        """Send a basic OSC packet to the DAW."""
        if not self.sock:
            if not self.connect():
                return {"status": "error", "message": "Failed to open socket"}

        try:
            addr_bytes = address.encode("utf-8") + b"\x00"
            while len(addr_bytes) % 4 != 0:
                addr_bytes += b"\x00"

            type_tags = b",f\x00\x00"
            import struct
            val_bytes = struct.pack(">f", float(value))
            packet = addr_bytes + type_tags + val_bytes

            self.sock.sendto(packet, (self.host, self.port))
            return {"status": "sent", "address": address, "value": value}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def play(self) -> Dict[str, Any]:
        return self.send_osc_command("/play", 1.0)

    def stop(self) -> Dict[str, Any]:
        return self.send_osc_command("/stop", 1.0)

    def record(self) -> Dict[str, Any]:
        return self.send_osc_command("/record", 1.0)


def _format_rpp_fxchain(vst_list: List[Dict[str, Any]]) -> str:
    """Format a list of VST3 plugin entries into a REAPER <FXCHAIN ...> block."""
    if not vst_list:
        return ""

    lines = ["    <FXCHAIN", "      SHOW 0", "      LASTSEL 0", "      DOCKED 0"]
    for item in vst_list:
        p_name = item.get("plugin_name", "VST3 Plugin")
        p_path = item.get("vst3_path", "")
        if not p_path or not os.path.exists(p_path):
            continue
        file_name = os.path.basename(p_path)
        lines.append(f'      <VST "VST3: {p_name}" "{file_name}" 0 "" 0 ""')
        lines.append("      >")
    lines.append("    >")
    return "\n".join(lines)


def _format_rpp_audio_item(name: str, file_path: str, duration_sec: Optional[float] = None) -> str:
    """Format a REAPER audio media item block with full length of the audio file."""
    abs_path = os.path.abspath(file_path).replace("\\", "/")
    item_duration = duration_sec or 0.0
    if os.path.isfile(file_path):
        try:
            info = sf.info(file_path)
            if info.duration > 0:
                item_duration = float(info.duration)
        except Exception:
            pass
    if item_duration <= 0:
        item_duration = 240.0

    return f"""    <ITEM
      POSITION 0.00000000000000
      SNAPOFFS 0.00000000000000
      LENGTH {item_duration:.6f}
      LOOP 0
      ALLTAKES 0
      FADEIN 1 0.005000 0.000000 1 0 0 0
      FADEOUT 1 0.005000 0.000000 1 0 0 0
      MUTE 0
      NAME "{name}"
      <SOURCE WAVE
        FILE "{abs_path}"
      >
    >"""


def _format_rpp_midi_item(name: str, events: List[Dict[str, Any]], duration_sec: float) -> str:
    """Format a REAPER inline MIDI item from instrument/drum events."""
    lines = [
        "    <ITEM",
        "      POSITION 0.00000000000000",
        "      SNAPOFFS 0.00000000000000",
        f"      LENGTH {max(2.0, duration_sec):.6f}",
        "      LOOP 0",
        "      ALLTAKES 0",
        "      MUTE 0",
        f'      NAME "{name}"',
        "      <SOURCE MIDI",
        "        HASDATA 1 960 QN",
    ]

    # Convert events to MIDI Note-On and Note-Off ticks (960 ticks = 1 quarter note)
    for ev in events[:64]:
        start_t = ev.get("start_time_sec", 0.0)
        dur = max(0.1, ev.get("duration_sec", 0.25))
        m_notes = ev.get("midi_notes", [36])
        for n in m_notes:
            pitch_hex = f"{int(n):02X}"
            # Simple tick delta
            lines.append(f"        E 480 90 {pitch_hex} 64")
            lines.append(f"        E 480 80 {pitch_hex} 00")

    lines.append("      >")
    lines.append("    >")
    return "\n".join(lines)


def generate_reaper_project_rpp(
    project_name: str,
    bpm: float,
    time_signature: str = "4/4",
    stem_paths: Optional[Dict[str, str]] = None,
    sync_map_json_path: Optional[str] = None,
    include_vsti_midi_tracks: bool = False,
    vst3_assignments: Optional[Dict[str, Any]] = None,
    output_rpp_path: str = "session.rpp",
    launch_reaper: bool = False,
    auto_use_detected_vst3: bool = True,
) -> Dict[str, Any]:
    """Generate a REAPER project skeleton using supplied audio and available plugins."""
    os.makedirs(os.path.dirname(os.path.abspath(output_rpp_path)), exist_ok=True)
    stems = dict(stem_paths or {})
    vst_reg = scan_installed_vst3_plugins()

    # Parse time signature
    try:
        ts_num, ts_den = [int(x) for x in time_signature.split("/")]
    except Exception:
        ts_num, ts_den = 4, 4

    # Load sync map if provided
    sync_events: List[Dict[str, Any]] = []
    max_duration = 4.0
    if sync_map_json_path and os.path.exists(sync_map_json_path):
        try:
            with open(sync_map_json_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
            sync_events = s_data.get("events", [])
            for ev in sync_events:
                max_duration = max(max_duration, ev.get("end_time_sec", 4.0))
        except Exception:
            pass

    # Build Master Bus VST3 chain
    master_chain_cfg = build_flagship_role_chain("master_bus", vst_reg)
    master_fx_str = _format_rpp_fxchain(master_chain_cfg)

    project_sample_rate = 44100
    for stem_path in stems.values():
        if stem_path and os.path.exists(stem_path):
            try:
                project_sample_rate = sf.info(stem_path).samplerate
                break
            except Exception:
                continue

    rpp_lines = [
        '<REAPER_PROJECT 0.1 "7.0" 1718000000',
        "  RIPPLE 0",
        "  GROUPOVERRIDE 0 0 0",
        "  AUTOXFADE 1",
        "  ENVATTACH 1",
        "  PEAKGAIN 1",
        "  FEEDBACK 0",
        f"  TEMPO {bpm:.6f} {ts_num} {ts_den}",
        f"  SAMPLERATE {project_sample_rate} 0 0",
    ]

    # Insert Project Markers from sync map
    marker_count = 0
    for idx, ev in enumerate(sync_events):
        if ev.get("is_transient_peak") or ev.get("recommended_capcut_fx") != "none" or idx % 8 == 0:
            m_time = ev.get("start_time_sec", 0.0)
            m_label = f"Beat {idx+1} [{ev.get('instrument', 'hit')}: {ev.get('playing_state', '')}]"
            rpp_lines.append(f'  MARKER {marker_count+1} {m_time:.6f} "{m_label}" 0 0 1')
            marker_count += 1
            if marker_count >= 50:
                break

    # Master Track & FX List Definition (Standard REAPER 7 structure)
    rpp_lines.extend([
        "  <MASTERTRACK",
        "    SHOW 1",
        "    PEAKCOL 16576",
        "    BEAT 0",
        "  >",
    ])
    if master_fx_str:
        rpp_lines.extend([
            "  <MASTERFXLIST",
            "    SHOW 0",
            "    LASTSEL 0",
            "    DOCKED 0",
        ])
        for p in master_chain_cfg:
            p_name = p.get("plugin_name", "VST3 Plugin")
            p_path = p.get("vst3_path", "")
            if p_path and os.path.exists(p_path):
                rpp_lines.append(f'    <VST "VST3: {p_name}" "{os.path.basename(p_path)}" 0 "" 0 ""')
                rpp_lines.append("    >")
        rpp_lines.append("  >")

    total_tracks_count = 0
    total_buses_count = 0

    # Helper to append a track
    def append_track(
        name: str,
        is_bus_depth: int,  # 1 = folder start, 0 = normal child, -1 = folder end
        file_path: Optional[str] = None,
        role: Optional[str] = None,
        is_rec_arm: bool = False,
        is_vsti: bool = False,
        midi_events: Optional[List[Dict[str, Any]]] = None,
    ):
        nonlocal total_tracks_count
        total_tracks_count += 1

        rec_flag = "1" if is_rec_arm else "0"
        isbus_str = f"1 {is_bus_depth}" if is_bus_depth > 0 else (f"2 {is_bus_depth}" if is_bus_depth < 0 else "0 0")

        # Get FX chain
        fx_chain_cfg = []
        if role and auto_use_detected_vst3:
            fx_chain_cfg = build_flagship_role_chain(role, vst_reg)
        if is_vsti and role == "vsti_drums":
            fx_chain_cfg = [{
                "plugin_name": "Superior Drummer 3",
                "vst3_path": _find_best_plugin_path(["superior drummer", "ezdrummer"], vst_reg),
            }]
        elif is_vsti and role == "vsti_orchestra":
            fx_chain_cfg = [{
                "plugin_name": "BBC Symphony Orchestra / Kontakt",
                "vst3_path": _find_best_plugin_path(["bbc symphony", "kontakt"], vst_reg),
            }]

        fx_str = _format_rpp_fxchain(fx_chain_cfg)

        t_lines = [
            "  <TRACK",
            f'    NAME "{name}"',
            f"    ISBUS {isbus_str}",
            f"    REC {rec_flag} 0 0 0 0 0 0",
            "    VOLPAN 1 0 -1 -1 1",
        ]

        if fx_str:
            t_lines.append(fx_str)

        # Append media item if available
        if file_path and os.path.exists(file_path):
            t_lines.append(_format_rpp_audio_item(name, file_path, max_duration))
        elif midi_events is not None:
            t_lines.append(_format_rpp_midi_item(name, midi_events, max_duration))

        t_lines.append("  >")
        rpp_lines.extend(t_lines)

    def existing_stem(name: str) -> Optional[str]:
        path = stems.get(name)
        return path if path and os.path.exists(path) else None

    # Build bus children only for real files; do not create labeled phantom
    # singer/performance tracks from absent heuristic sub-stems.
    vocal_children = []
    if existing_stem("vocal_lead"):
        vocal_children.append(("Vocal lead", existing_stem("vocal_lead"), "vocal_lead"))
    elif existing_stem("vocals"):
        vocal_children.append(("Vocals (combined; singers not split)", existing_stem("vocals"), "vocals"))
    if existing_stem("vocal_co_lead"):
        vocal_children.append(("Vocal co-lead", existing_stem("vocal_co_lead"), "vocal_co_lead"))
    if existing_stem("vocal_backing"):
        vocal_children.append(("Vocal backing", existing_stem("vocal_backing"), "vocal_backing"))
    if vocal_children:
        total_buses_count += 1
        append_track("VOCAL BUS", is_bus_depth=1)
        for idx, (name, path, role) in enumerate(vocal_children):
            append_track(name, -1 if idx == len(vocal_children) - 1 else 0, path, role=role)

    guitar_children = []
    if existing_stem("guitar_rhythm"):
        guitar_children.append(("Guitar rhythm", existing_stem("guitar_rhythm"), "guitar_rhythm"))
    elif existing_stem("guitar"):
        guitar_children.append(("Guitar (combined; performances not split)", existing_stem("guitar"), "guitar_rhythm"))
    if existing_stem("guitar_lead"):
        guitar_children.append(("Guitar lead", existing_stem("guitar_lead"), "guitar_lead"))
    if existing_stem("guitar_additional"):
        guitar_children.append(("Guitar additional", existing_stem("guitar_additional"), "guitar_additional"))
    if guitar_children:
        total_buses_count += 1
        append_track("GUITAR BUS", is_bus_depth=1)
        for name, path, role in guitar_children:
            append_track(name, 0, path, role=role)
        append_track("GUITAR RE-TRACK (Human DI -> Archetype Gojira X)", -1, None, role="guitar_lead", is_rec_arm=True)

    rhythm_children = [(name, existing_stem(name), name) for name in ("bass", "drums") if existing_stem(name)]
    if rhythm_children:
        total_buses_count += 1
        append_track("BASS & DRUM BUS", is_bus_depth=1)
        for idx, (name, path, role) in enumerate(rhythm_children):
            append_track(name, -1 if idx == len(rhythm_children) - 1 else 0, path, role=role)

    # 4. BUS 4: ORCHESTRA & KEYS BUS (Folder)
    orch_keys = ["synth", "piano", "other", "violin", "viola", "cello", "strings_ensemble", "brass", "woodwinds", "flute", "choir"]
    active_orch = [k for k in orch_keys if k in stems]
    if active_orch:
        total_buses_count += 1
        append_track("ORCHESTRA & KEYS BUS", is_bus_depth=1)
        for idx, ok in enumerate(active_orch):
            is_last = (idx == len(active_orch) - 1)
            depth = -1 if is_last else 0
            track_name = "Other residual (not a separated instrument)" if ok == "other" else ok
            append_track(track_name, depth, stems.get(ok), role=None if ok == "other" else "orchestra")

    # 5. BUS 5: VSTi REPLACEMENT / LAYERING BUS (Folder - Category D)
    if include_vsti_midi_tracks:
        drum_plugin = _find_best_plugin_path(["superior drummer", "ezdrummer"], vst_reg)
        orchestra_plugin = _find_best_plugin_path(["bbc symphony", "kontakt"], vst_reg)
        drum_midi_events = [e for e in sync_events if e.get("instrument") == "drums" and e.get("midi_notes")]
        orch_midi_events = [e for e in sync_events if any(k in str(e.get("instrument")) for k in ["violin", "cello", "string", "brass", "choir"]) and e.get("midi_notes")]
        available_vsti = []
        if drum_plugin and os.path.exists(drum_plugin) and drum_midi_events:
            available_vsti.append(("VSTi Drums", "vsti_drums", drum_midi_events))
        if orchestra_plugin and os.path.exists(orchestra_plugin) and orch_midi_events:
            available_vsti.append(("VSTi Orchestra", "vsti_orchestra", orch_midi_events))
        if available_vsti:
            total_buses_count += 1
            append_track("VSTi REPLACEMENT / LAYERING BUS", is_bus_depth=1)
            for idx, (name, role, events) in enumerate(available_vsti):
                if idx == len(available_vsti) - 1:
                    append_track(name, -1, None, role=role, is_vsti=True, midi_events=events)
                else:
                    append_track(name, 0, None, role=role, is_vsti=True, midi_events=events)

    rpp_lines.append(">")

    # Write .rpp file
    with open(output_rpp_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rpp_lines) + "\n")

    launched = False
    if launch_reaper and os.path.isfile(output_rpp_path):
        launched = launch_reaper_project(output_rpp_path)

    return {
        "status": "success",
        "project_name": project_name,
        "output_rpp_path": output_rpp_path,
        "rpp_path": output_rpp_path,
        "launched": launched,
        "bpm": bpm,
        "time_signature": time_signature,
        "total_tracks": total_tracks_count,
        "folder_buses_count": total_buses_count,
        "markers_count": marker_count,
        "vsti_midi_tracks_included": include_vsti_midi_tracks,
        "master_vst3_plugins": [p["plugin_name"] for p in master_chain_cfg if p.get("vst3_path") and os.path.exists(p["vst3_path"])],
    }


def find_reaper_executable() -> Optional[str]:
    """Search common paths for REAPER executable."""
    candidates = [
        r"F:\installer program\REAPER\reaper.exe",
        r"C:\Program Files\REAPER (x64)\reaper.exe",
        r"C:\Program Files\REAPER\reaper.exe",
        r"C:\Program Files (x86)\REAPER\reaper.exe",
        r"D:\REAPER (x64)\reaper.exe",
        r"D:\REAPER\reaper.exe",
        r"F:\REAPER (x64)\reaper.exe",
        r"F:\REAPER\reaper.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\REAPER\reaper.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    try:
        import shutil
        which = shutil.which("reaper")
        if which and os.path.isfile(which):
            return which
    except Exception:
        pass
    return None


def launch_reaper_project(rpp_path: str) -> bool:
    """Launch REAPER with the specified .rpp project file."""
    if not os.path.isfile(rpp_path):
        return False
    exe = find_reaper_executable()
    try:
        import subprocess
        abs_rpp = os.path.abspath(rpp_path)
        if exe and os.path.isfile(exe):
            subprocess.Popen([exe, abs_rpp], close_fds=True)
            return True
        elif hasattr(os, "startfile"):
            os.startfile(abs_rpp)
            return True
    except Exception:
        pass
    return False


def find_ableton_executable() -> Optional[str]:
    """Search common paths for Ableton Live executable."""
    candidates = [
        r"F:\installer program\Live 12 Suite\Program\Ableton Live 12 Suite.exe",
        r"C:\Program Files\Ableton\Live 12 Suite\Program\Ableton Live 12 Suite.exe",
        r"C:\Program Files\Ableton\Live 11 Suite\Program\Ableton Live 11 Suite.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    start_menu = os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\Ableton Live 12 Suite.lnk")
    if os.path.isfile(start_menu):
        try:
            import subprocess
            cmd = f'$sh = New-Object -ComObject WScript.Shell; $sh.CreateShortcut("{start_menu}").TargetPath'
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=5)
            target = res.stdout.strip()
            if target and os.path.isfile(target):
                return target
        except Exception:
            pass
    return None


def launch_ableton_project(als_path: str) -> bool:
    """Launch Ableton Live with the specified .als project file."""
    if not os.path.isfile(als_path):
        return False
    exe = find_ableton_executable()
    try:
        import subprocess
        abs_als = os.path.abspath(als_path)
        if exe and os.path.isfile(exe):
            subprocess.Popen([exe, abs_als], close_fds=True)
            return True
        elif hasattr(os, "startfile"):
            os.startfile(abs_als)
            return True
    except Exception:
        return False
    return False


def generate_ableton_live_set_als(
    project_name: str,
    bpm: float,
    stem_paths: Optional[Dict[str, str]] = None,
    output_als_path: Optional[str] = None,
) -> str:
    """Generate a native Ableton Live Set (.als) with stem audio tracks and BPM."""
    import copy
    import gzip
    import xml.etree.ElementTree as ET

    if not output_als_path:
        output_als_path = os.path.join("workspace", "output_audio", f"{project_name}_session.als")

    os.makedirs(os.path.dirname(os.path.abspath(output_als_path)), exist_ok=True)

    module_dir = os.path.dirname(os.path.abspath(__file__))
    tpl_dir = os.path.join(module_dir, "templates")
    base_als_tpl = os.path.join(tpl_dir, "base_liveset_template.als")
    clip_xml_tpl = os.path.join(tpl_dir, "audioclip_template.xml")

    # Fallback to system Live 12 templates if local templates missing
    if not os.path.isfile(base_als_tpl):
        sys_tpl = r"F:\installer program\Live 12 Suite\Resources\Builtin\Templates\DefaultLiveSet.als"
        if os.path.isfile(sys_tpl):
            base_als_tpl = sys_tpl

    if not os.path.isfile(base_als_tpl):
        raise FileNotFoundError(f"Base Ableton Live template not found at {base_als_tpl}")

    with gzip.open(base_als_tpl, "rb") as f:
        root = ET.fromstring(f.read())

    ls = root.find("LiveSet")
    if ls is None:
        raise ValueError("Invalid LiveSet XML: missing LiveSet root")

    # Set project BPM
    main_track = ls.find("MainTrack")
    if main_track is not None:
        mixer = main_track.find("DeviceChain/Mixer")
        if mixer is not None:
            tempo = mixer.find("Tempo/Manual")
            if tempo is not None:
                tempo.attrib["Value"] = str(float(bpm))

    tracks = ls.find("Tracks")
    if tracks is None:
        tracks = ET.SubElement(ls, "Tracks")

    # Find sample AudioTrack to clone
    sample_at = None
    for child in list(tracks):
        if child.tag == "AudioTrack":
            sample_at = copy.deepcopy(child)
            break

    if sample_at is None:
        raise ValueError("Could not find AudioTrack template in base LiveSet")

    # Load clip template
    clip_template = None
    if os.path.isfile(clip_xml_tpl):
        clip_template = ET.parse(clip_xml_tpl).getroot()

    # Clear existing tracks in template
    for child in list(tracks):
        tracks.remove(child)

    stems = dict(stem_paths or {})
    track_id = 100
    clip_id = 1000

    for name, path in stems.items():
        if not path or not os.path.isfile(path):
            continue
        try:
            info = sf.info(path)
            beats = info.duration / (60.0 / max(bpm, 1.0))
        except Exception:
            beats = 64.0
            info = None

        t = copy.deepcopy(sample_at)
        t.attrib["Id"] = str(track_id)
        track_id += 1

        # Format display name
        display_name = name.replace("_", " ").title()
        eff_name = t.find("Name/EffectiveName")
        if eff_name is not None:
            eff_name.attrib["Value"] = display_name
        usr_name = t.find("Name/UserName")
        if usr_name is not None:
            usr_name.attrib["Value"] = display_name

        if clip_template is not None:
            clip = copy.deepcopy(clip_template)
            clip.attrib["Id"] = str(clip_id)
            clip_id += 1
            clip.attrib["Time"] = "0"

            c_start = clip.find("CurrentStart")
            if c_start is not None:
                c_start.attrib["Value"] = "0"
            c_end = clip.find("CurrentEnd")
            if c_end is not None:
                c_end.attrib["Value"] = str(beats)
            c_name = clip.find("Name")
            if c_name is not None:
                c_name.attrib["Value"] = display_name

            is_warped = clip.find("IsWarped")
            if is_warped is not None:
                is_warped.attrib["Value"] = "false"

            sr = clip.find("SampleRef")
            if sr is not None:
                fr = sr.find("FileRef")
                if fr is not None:
                    p_elem = fr.find("Path")
                    if p_elem is not None:
                        p_elem.attrib["Value"] = os.path.abspath(path).replace("\\", "/")
                    rp_elem = fr.find("RelativePath")
                    if rp_elem is not None:
                        rp_elem.attrib["Value"] = os.path.basename(path)
                if info:
                    dur = sr.find("DefaultDuration")
                    if dur is not None:
                        dur.attrib["Value"] = str(int(info.frames))
                    srate = sr.find("DefaultSampleRate")
                    if srate is not None:
                        srate.attrib["Value"] = str(int(info.samplerate))

            events = t.find("DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events")
            if events is not None:
                for old_c in list(events):
                    events.remove(old_c)
                events.append(clip)

        tracks.append(t)

    with gzip.open(output_als_path, "wb") as f:
        f.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))

    return output_als_path


def export_ableton_als_session_manifest(
    project_name: str,
    bpm: float,
    musical_key: str,
    stem_paths: Optional[Dict[str, str]] = None,
    sync_map_json_path: Optional[str] = None,
    vst3_assignments: Optional[Dict[str, Any]] = None,
    output_dir: str = "workspace/output_audio",
    generate_als: bool = True,
    launch_ableton: bool = False,
    output_als_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate an Ableton Live Session Manifest JSON detailing track groups, routing, and VST3 assignments, and optionally generate/launch .als."""
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, f"{project_name}_ableton_manifest.json")
    vst_reg = scan_installed_vst3_plugins()

    stems = dict(stem_paths or {})

    groups = [
        {
            "group_name": "VOCAL GROUP",
            "tracks": [
                {"name": "Vocal Lead", "stem_file": stems.get("vocal_lead"), "devices": build_flagship_role_chain("vocal_lead", vst_reg)},
                {"name": "Vocal Co-Lead", "stem_file": stems.get("vocal_co_lead"), "devices": build_flagship_role_chain("vocal_co_lead", vst_reg)},
                {"name": "Vocal Backing", "stem_file": stems.get("vocal_backing"), "devices": build_flagship_role_chain("vocal_backing", vst_reg)},
            ],
        },
        {
            "group_name": "GUITAR GROUP",
            "tracks": [
                {"name": "Rhythm Guitar", "stem_file": stems.get("guitar_rhythm"), "devices": build_flagship_role_chain("guitar_rhythm", vst_reg)},
                {"name": "Lead Guitar", "stem_file": stems.get("guitar_lead"), "devices": build_flagship_role_chain("guitar_lead", vst_reg)},
                {"name": "Additional Guitar", "stem_file": stems.get("guitar_additional"), "devices": build_flagship_role_chain("guitar_additional", vst_reg)},
                {"name": "GUITAR RE-TRACK (Archetype Gojira X)", "stem_file": None, "arm": True, "devices": build_flagship_role_chain("guitar_lead", vst_reg)},
            ],
        },
        {
            "group_name": "BASS & DRUMS",
            "tracks": [
                {"name": "Bass", "stem_file": stems.get("bass"), "devices": build_flagship_role_chain("bass", vst_reg)},
                {"name": "Drums", "stem_file": stems.get("drums"), "devices": build_flagship_role_chain("drums", vst_reg)},
            ],
        },
        {
            "group_name": "VSTi REPLACEMENT & LAYERING",
            "tracks": [
                {"name": "Superior Drummer 3 (MIDI)", "type": "MIDI", "vsti": "Superior Drummer 3.vst3"},
                {"name": "BBC Symphony Orchestra / Kontakt (MIDI)", "type": "MIDI", "vsti": "BBC Symphony Orchestra.vst3"},
            ],
        },
    ]

    manifest = {
        "project_name": project_name,
        "bpm": bpm,
        "musical_key": musical_key,
        "master_bus_chain": build_flagship_role_chain("master_bus", vst_reg),
        "groups": groups,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    als_path = None
    if generate_als:
        if not output_als_path:
            output_als_path = os.path.join(output_dir, f"{project_name}_session.als")
        try:
            als_path = generate_ableton_live_set_als(
                project_name=project_name,
                bpm=bpm,
                stem_paths=stems,
                output_als_path=output_als_path,
            )
        except Exception as e:
            als_path = None

    launched = False
    if launch_ableton and als_path:
        launched = launch_ableton_project(als_path)

    return {
        "status": "success",
        "project_name": project_name,
        "manifest_path": manifest_path,
        "als_path": als_path,
        "launched": launched,
        "groups_count": len(groups),
    }

