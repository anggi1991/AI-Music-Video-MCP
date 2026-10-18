"""CapCut Desktop Draft Path Resolver and Project Draft Manager."""

import os
import sys
import platform
import shutil
from typing import Optional, Dict, Any, Tuple

# Ensure vendor/pyCapCut is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
VENDOR_PYCAPCUT = os.path.join(PROJECT_ROOT, "vendor", "pyCapCut")
if VENDOR_PYCAPCUT not in sys.path:
    sys.path.insert(0, VENDOR_PYCAPCUT)

import pycapcut as cc


def resolve_capcut_draft_root(custom_path: Optional[str] = None) -> str:
    """Resolve the OS-specific CapCut Desktop draft root directory.

    - Windows: %LOCALAPPDATA%\\CapCut\\User Data\\Projects\\com.lveditor.draft\\
    - macOS: ~/Movies/CapCut/User Data/Projects/com.lveditor.draft/
    - Custom override or fallback to workspace/capcut_drafts
    """
    if custom_path and custom_path.strip():
        os.makedirs(custom_path, exist_ok=True)
        return os.path.abspath(custom_path)

    system = platform.system()
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            standard_path = os.path.join(
                local_app_data,
                "CapCut",
                "User Data",
                "Projects",
                "com.lveditor.draft",
            )
            if os.path.exists(standard_path):
                return standard_path
            # Check JianYing (Chinese CapCut variant)
            jy_path = os.path.join(
                local_app_data,
                "JianyingPro",
                "User Data",
                "Projects",
                "com.lveditor.draft",
            )
            if os.path.exists(jy_path):
                return jy_path

    elif system == "Darwin":  # macOS
        standard_path = os.path.expanduser(
            "~/Movies/CapCut/User Data/Projects/com.lveditor.draft/"
        )
        if os.path.exists(standard_path):
            return standard_path

    # Fallback default in project workspace
    fallback_path = os.path.join(PROJECT_ROOT, "workspace", "capcut_drafts")
    os.makedirs(fallback_path, exist_ok=True)
    return os.path.abspath(fallback_path)


def initialize_capcut_draft(
    draft_name: str,
    drafts_root: Optional[str] = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> Tuple[cc.ScriptFile, str]:
    """Create a new CapCut project draft folder and return the ScriptFile instance and draft dir."""
    root_dir = resolve_capcut_draft_root(drafts_root)
    draft_folder = cc.DraftFolder(root_dir)
    script = draft_folder.create_draft(
        draft_name,
        width=width,
        height=height,
        fps=fps,
        maintrack_adsorb=False,
        allow_replace=True,
    )
    draft_dir = os.path.join(root_dir, draft_name)
    return script, draft_dir


def finalize_and_save_draft(script: cc.ScriptFile, draft_dir: str) -> Dict[str, Any]:
    """Save the CapCut draft and ensure both draft_content.json and draft_info.json exist."""
    script.save()

    content_path = os.path.join(draft_dir, "draft_content.json")
    meta_path = os.path.join(draft_dir, "draft_meta_info.json")
    info_path = os.path.join(draft_dir, "draft_info.json")

    # Mirror meta to draft_info.json if only draft_meta_info exists
    if os.path.exists(meta_path) and not os.path.exists(info_path):
        shutil.copy(meta_path, info_path)
    elif os.path.exists(info_path) and not os.path.exists(meta_path):
        shutil.copy(info_path, meta_path)

    return {
        "status": "success",
        "draft_dir": draft_dir,
        "draft_content_json": content_path,
        "draft_info_json": info_path if os.path.exists(info_path) else meta_path,
    }
