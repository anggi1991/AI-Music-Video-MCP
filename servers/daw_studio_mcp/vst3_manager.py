"""Flagship VST3 & VSTi Arsenal Manager and Parameter Inspector.

Scans, categorizes, inspects, and applies Categories A–D VST3/VSTi plugins:
- Category A: Mastering & Surgical (soothe2, Ozone 11/12, FabFilter Pro-Q, Pro-L 2, Pro-MB, Saturn 2)
- Category B: 3-Way Vocals & Reverb (Nectar 4, FabFilter Pro-C, Pro-DS, Valhalla Reverb, ValhallaDelay)
- Category C: Guitar & Bass (Archetype Gojira X, Archetype Nolly X, Parallax X)
- Category D: Virtual Instruments (Superior Drummer 3, EZdrummer, BBC Symphony Orchestra, Kontakt)
"""

import os
import sys
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pedalboard as pb

# Default system VST3 search paths for Windows and common platforms
DEFAULT_VST3_PATHS = [
    r"C:\Program Files\Common Files\VST3",
    r"C:\Program Files (x86)\Common Files\VST3",
    os.path.expanduser(r"~\AppData\Local\Programs\Common\VST3"),
]


def scan_installed_vst3_plugins(custom_search_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """Scan local storage for installed VST3 plugins and categorize into Categories A-D.

    Returns:
        dict: Registry of discovered plugins categorized by production role.
    """
    search_dirs = list(custom_search_paths or []) + DEFAULT_VST3_PATHS
    found_plugins: Dict[str, str] = {}
    scanned_existing_dirs = []

    for d in search_dirs:
        if not os.path.exists(d):
            continue
        scanned_existing_dirs.append(d)
        for root, dirs, files in os.walk(d):
            # Check file vst3
            for f in files:
                if f.lower().endswith(".vst3"):
                    full_p = os.path.abspath(os.path.join(root, f))
                    name = os.path.splitext(f)[0]
                    found_plugins[name] = full_p

            # Check directory bundle vst3
            for sub_d in dirs:
                if sub_d.lower().endswith(".vst3"):
                    full_p = os.path.abspath(os.path.join(root, sub_d))
                    name = os.path.splitext(sub_d)[0]
                    found_plugins[name] = full_p

    # Categorize into Categories A, B, C, D
    cat_a: Dict[str, str] = {}
    cat_b: Dict[str, str] = {}
    cat_c: Dict[str, str] = {}
    cat_d: Dict[str, str] = {}

    for name, path in found_plugins.items():
        n_low = name.lower()

        # Category A: Mastering & Surgical De-Harshing
        if any(k in n_low for k in ["soothe", "ozone", "pro-q", "pro-l", "pro-mb", "saturn"]):
            cat_a[name] = path

        # Category B: Vocals & Reverb / Spatial
        if any(k in n_low for k in ["nectar", "pro-c", "pro-ds", "valhalla"]):
            cat_b[name] = path

        # Category C: Guitar & Bass Metalcore
        if any(k in n_low for k in ["gojira", "nolly", "parallax", "archetype"]):
            cat_c[name] = path

        # Category D: Virtual Instruments (VSTi)
        if any(k in n_low for k in ["superior drummer", "ezdrummer", "bbc symphony", "kontakt", "spitfire"]):
            cat_d[name] = path

    return {
        "status": "success",
        "total_plugins_found": len(found_plugins),
        "scanned_paths": scanned_existing_dirs,
        "category_a_mastering_and_surgical": cat_a,
        "category_b_vocals_and_reverb": cat_b,
        "category_c_guitar_and_bass": cat_c,
        "category_d_virtual_instruments": cat_d,
        "all_plugins": found_plugins,
    }


def inspect_vst3_parameters(vst3_path: str) -> Dict[str, Any]:
    """Inspect parameter names, ranges, and instrument status of a VST3 plugin using pedalboard."""
    if not os.path.exists(vst3_path):
        return {
            "status": "error",
            "vst3_path": vst3_path,
            "message": "File not found",
            "parameters": {},
            "is_instrument": False,
        }

    try:
        plugin = pb.load_plugin(vst3_path)
        is_inst = bool(getattr(plugin, "is_instrument", False))
        param_dict = {}

        for p_name, p_obj in getattr(plugin, "parameters", {}).items():
            param_dict[str(p_name)] = {
                "name": str(p_name),
                "type": type(p_obj).__name__,
                "raw_value": getattr(p_obj, "raw_value", None),
                "string_value": str(p_obj),
            }

        return {
            "status": "success",
            "vst3_path": vst3_path,
            "plugin_name": type(plugin).__name__,
            "is_instrument": is_inst,
            "parameter_count": len(param_dict),
            "parameters": param_dict,
        }
    except Exception as e:
        return {
            "status": "partial",
            "vst3_path": vst3_path,
            "is_instrument": False,
            "load_error": str(e),
            "parameters": {},
        }


def _find_best_plugin_path(
    keywords: List[str],
    registry: Dict[str, Any],
) -> Optional[str]:
    """Find the best matching installed VST3 path for a list of keyword hints."""
    all_p = registry.get("all_plugins", {})
    # Check exact keyword matches
    for kw in keywords:
        kw_low = kw.lower()
        for name, path in all_p.items():
            if kw_low in name.lower():
                return path
    return None


def build_flagship_role_chain(
    role: str,
    installed_registry: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build the ideal Flagship VST3 signal chain for a given production role.

    If a plugin is installed, its actual filepath is attached; otherwise, ideal fallback metadata is provided.
    """
    reg = installed_registry or scan_installed_vst3_plugins()
    role_clean = role.lower().strip()

    def make_entry(ideal_name: str, search_keys: List[str], category: str, default_params: Optional[Dict[str, Any]] = None):
        found_path = _find_best_plugin_path(search_keys, reg)
        return {
            "plugin_name": ideal_name,
            "search_keywords": search_keys,
            "vst3_path": found_path,
            "is_installed": found_path is not None,
            "category": category,
            "params": default_params or {},
            "active": True,
        }

    chain: List[Dict[str, Any]] = []

    if role_clean in ("vocal_lead", "lead_vocal", "vocals"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 90.0, "air_boost_10k": 2.0}),
            make_entry("FabFilter Pro-DS", ["pro-ds"], "category_b_vocals_and_reverb", {"threshold_db": -24.0}),
            make_entry("FabFilter Pro-C", ["pro-c 3", "pro-c 2", "pro-c", "nectar"], "category_b_vocals_and_reverb", {"ratio": 3.5, "threshold_db": -18.0}),
            make_entry("soothe2", ["soothe2", "soothe"], "category_a_mastering_and_surgical", {"depth": 3.0, "sharpness": 5.0}),
        ]

    elif role_clean in ("vocal_co_lead", "co_lead"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 100.0}),
            make_entry("FabFilter Saturn 2", ["saturn 2", "saturn"], "category_a_mastering_and_surgical", {"drive": 2.5, "style": "Warm Tube"}),
            make_entry("FabFilter Pro-C", ["pro-c 3", "pro-c 2", "pro-c"], "category_b_vocals_and_reverb", {"ratio": 4.0, "threshold_db": -20.0}),
            make_entry("ValhallaDelay", ["valhalladelay", "valhalla"], "category_b_vocals_and_reverb", {"mix": 0.20, "feedback": 0.35}),
        ]

    elif role_clean in ("vocal_backing", "backing"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 120.0}),
            make_entry("soothe2", ["soothe2", "soothe"], "category_a_mastering_and_surgical", {"depth": 3.5}),
            make_entry("Valhalla Reverb", ["valhallafutureverb", "valhallavintageverb", "valhalla", "pro-r"], "category_b_vocals_and_reverb", {"mix": 0.35, "decay": 2.5}),
        ]

    elif role_clean in ("guitar_rhythm", "rhythm_guitar"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 80.0, "low_mid_dip_350": -1.5}),
            make_entry("FabFilter Pro-MB", ["pro-mb"], "category_a_mastering_and_surgical", {"band_low_chug": "120Hz"}),
            make_entry("soothe2", ["soothe2", "soothe"], "category_a_mastering_and_surgical", {"depth": 2.8, "mode": "hard"}),
        ]

    elif role_clean in ("guitar_lead", "lead_guitar"):
        chain = [
            make_entry("Archetype Gojira X / Saturn", ["gojira", "saturn 2", "saturn"], "category_c_guitar_and_bass", {"drive": 3.0}),
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"presence_3k": 2.0}),
            make_entry("ValhallaDelay", ["valhalladelay", "timeless", "valhalla"], "category_b_vocals_and_reverb", {"mix": 0.22}),
            make_entry("Valhalla Reverb", ["valhallafutureverb", "valhallavintageverb", "valhalla", "pro-r"], "category_b_vocals_and_reverb", {"mix": 0.25}),
        ]

    elif role_clean in ("guitar_additional", "additional_guitar"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 150.0}),
            make_entry("ValhallaDelay", ["valhalladelay", "timeless", "valhalla"], "category_b_vocals_and_reverb", {"mix": 0.30}),
            make_entry("Valhalla Reverb", ["valhallafutureverb", "valhallavintageverb", "valhalla", "pro-r"], "category_b_vocals_and_reverb", {"mix": 0.40}),
        ]

    elif role_clean in ("bass", "electric_bass"):
        chain = [
            make_entry("Parallax X", ["parallax x", "parallax"], "category_c_guitar_and_bass", {"low_compression": "heavy", "drive": "medium"}),
            make_entry("FabFilter Pro-L 2", ["pro-l 2", "pro-l", "pro-c 3", "pro-c 2", "pro-c"], "category_a_mastering_and_surgical", {"ceiling": -0.5}),
        ]

    elif role_clean in ("drums", "drum"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 30.0, "sub_punch_60": 2.0}),
            make_entry("FabFilter Saturn 2", ["saturn 2", "saturn"], "category_a_mastering_and_surgical", {"drive": 1.5}),
            make_entry("soothe2", ["soothe2", "soothe"], "category_a_mastering_and_surgical", {"depth": 3.5, "hi_shelf_target": "5kHz"}),
        ]

    elif role_clean in ("orchestra", "violin", "cello", "strings", "brass", "choir"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 60.0}),
            make_entry("soothe2", ["soothe2", "soothe"], "category_a_mastering_and_surgical", {"depth": 2.5}),
            make_entry("Valhalla Reverb", ["valhallafutureverb", "valhallavintageverb", "valhalla", "pro-r"], "category_b_vocals_and_reverb", {"mix": 0.35, "space": "Concert Hall"}),
        ]

    elif role_clean in ("master_bus", "master", "mix_bus"):
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical", {"hp_freq": 25.0}),
            make_entry("Ozone Stabilizer", ["ozone 12 stabilizer", "ozone 11 stabilizer", "stabilizer"], "category_a_mastering_and_surgical", {"depth": 40.0}),
            make_entry("Ozone Imager", ["ozone 12 imager", "ozone 11 imager", "imager"], "category_a_mastering_and_surgical", {"width_stereo": 1.15}),
            make_entry("Ozone Maximizer", ["ozone 12 maximizer", "ozone 11 maximizer", "ozone 12", "ozone 11", "maximizer"], "category_a_mastering_and_surgical", {"target_lufs": -9.0}),
            make_entry("FabFilter Pro-L 2", ["pro-l 2", "pro-l"], "category_a_mastering_and_surgical", {"true_peak": -0.5}),
        ]

    else:
        chain = [
            make_entry("FabFilter Pro-Q", ["pro-q 4", "pro-q 3", "pro-q"], "category_a_mastering_and_surgical"),
            make_entry("soothe2", ["soothe2", "soothe"], "category_a_mastering_and_surgical"),
        ]

    return chain


def apply_vst3_chain_to_audio(
    audio_data: np.ndarray,
    sample_rate: int,
    vst3_chain_config: List[Dict[str, Any]],
) -> Tuple[np.ndarray, List[str]]:
    """Process audio data through an ordered list of VST3 plugins using pedalboard.

    Skips virtual instruments (VSTi) and plugins that fail headless initialization with graceful fallback.
    """
    processed = np.array(audio_data, copy=True)
    applied_plugins: List[str] = []

    for item in vst3_chain_config:
        if not item.get("active", True):
            continue

        vst_path = item.get("vst3_path")
        if not vst_path or not os.path.exists(vst_path):
            continue

        try:
            plugin = pb.load_plugin(vst_path)
            # Skip VSTi instruments (they generate audio, not process effects)
            if getattr(plugin, "is_instrument", False):
                continue

            # Process audio
            out = plugin(processed, sample_rate)
            if out is not None and not np.isnan(out).any():
                processed = out
                applied_plugins.append(item.get("plugin_name", os.path.basename(vst_path)))
        except Exception:
            # Graceful headless fallback
            continue

    return processed, applied_plugins
