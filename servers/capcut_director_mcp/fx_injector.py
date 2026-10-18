"""Keyframe visual FX injector for CapCut VideoSegments.

Injects camera scale punch (100% -> 112% -> 100%), screen shake, white flash,
and hard zoom keyframes on breakdown transients.
"""

import sys
import os
from typing import Optional, Literal

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
VENDOR_PYCAPCUT = os.path.join(PROJECT_ROOT, "vendor", "pyCapCut")
if VENDOR_PYCAPCUT not in sys.path:
    sys.path.insert(0, VENDOR_PYCAPCUT)

import pycapcut as cc
from pycapcut import KeyframeProperty


def inject_breakdown_fx(
    segment: cc.VideoSegment,
    fx_type: Optional[str] = "none",
    is_heavy_breakdown: bool = False,
    segment_duration_us: int = 1_000_000,
) -> int:
    """Inject keyframes into a VideoSegment for camera punch, screen shake, white flash, or zoom.

    Returns:
        int: Number of keyframes injected.
    """
    injected_count = 0

    # 1. Base breakdown camera scale punch: 100% -> 112% -> 100% over 150ms
    if is_heavy_breakdown or fx_type in ("screen_shake", "hard_zoom"):
        t_peak = min(50_000, segment_duration_us // 3)
        t_end = min(150_000, segment_duration_us // 2)

        peak_scale = 1.25 if fx_type == "hard_zoom" else 1.12
        segment.add_keyframe(KeyframeProperty.uniform_scale, 0, 1.0)
        segment.add_keyframe(KeyframeProperty.uniform_scale, t_peak, peak_scale)
        segment.add_keyframe(KeyframeProperty.uniform_scale, t_end, 1.0)
        injected_count += 3

    # 2. Screen shake: rapid lateral position jitter
    if fx_type == "screen_shake":
        t1 = min(30_000, segment_duration_us // 5)
        t2 = min(70_000, (segment_duration_us * 2) // 5)
        t3 = min(120_000, (segment_duration_us * 3) // 5)

        segment.add_keyframe(KeyframeProperty.position_x, 0, 0.0)
        segment.add_keyframe(KeyframeProperty.position_x, t1, 0.035)
        segment.add_keyframe(KeyframeProperty.position_x, t2, -0.035)
        segment.add_keyframe(KeyframeProperty.position_x, t3, 0.0)
        injected_count += 4

    # 3. White flash: momentary brightness surge
    if fx_type == "white_flash":
        t_peak = min(35_000, segment_duration_us // 4)
        t_end = min(110_000, segment_duration_us // 2)

        segment.add_keyframe(KeyframeProperty.brightness, 0, 0.0)
        segment.add_keyframe(KeyframeProperty.brightness, t_peak, 0.85)
        segment.add_keyframe(KeyframeProperty.brightness, t_end, 0.0)
        injected_count += 3

    return injected_count
