"""Task-oriented separation model metadata. Labels describe model outputs, not purity."""

from copy import deepcopy
from typing import Any


MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "htdemucs_6s": {
        "model_id": "htdemucs_6s",
        "task_type": "six_source_music_separation",
        "expected_output_labels": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "license_info": "Demucs source code: MIT. Checkpoint terms/provenance should be confirmed from its upstream distribution before redistribution.",
        "verification_status": "verified_pretrained",
        "caveats": [
            "Outputs are estimates from a stereo mix, not bleed-free multitracks.",
            "The piano estimate is limited according to the upstream Demucs documentation.",
            "This model does not split guitar roles or lead and backing vocals.",
        ],
    },
    "cascaded_separation": {
        "model_id": "cascaded_separation",
        "task_type": "sequential_configured_model_pipeline",
        "expected_output_labels": [],
        "license_info": "Per-stage code and checkpoint licenses must be recorded before a stage is enabled.",
        "verification_status": "experimental_heuristic",
        "caveats": [
            "No cascade stage is enabled until a compatible verified model and output mapping are configured.",
            "A cascade can compound separation artifacts and does not guarantee source isolation.",
        ],
    },
    "experimental_dsp_masks": {
        "model_id": "experimental_dsp_masks",
        "task_type": "experimental_heuristic_dsp_mask",
        "expected_output_labels": [],
        "license_info": "Project code; no pretrained model weights.",
        "verification_status": "experimental_heuristic",
        "caveats": ["Experimental DSP masks are not source separation and may contain instrument bleed."],
    },
}


def get_model_metadata(model_id: str) -> dict[str, Any] | None:
    """Return a copy so callers cannot mutate the global registry."""
    item = MODEL_REGISTRY.get(model_id)
    return deepcopy(item) if item is not None else None
