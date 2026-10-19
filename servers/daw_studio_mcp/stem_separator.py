"""6-Stem Audio Separation with Anti-Bleed Spectral Gating, Multi-Guitar, Vocal, & Orchestral Decomposition."""

import os
import sys
import gc
import time
from typing import Dict, Any, Optional
import numpy as np
import soundfile as sf
import librosa
import pedalboard as pb
try:
    from .model_registry import get_model_metadata
except ImportError:
    from model_registry import get_model_metadata

try:
    from .guitar_decomposer import decompose_guitar_stem
    from .vocal_decomposer import decompose_vocal_stem
    from .orchestra_decomposer import decompose_orchestral_stem
except ImportError:
    from guitar_decomposer import decompose_guitar_stem
    from vocal_decomposer import decompose_vocal_stem
    from orchestra_decomposer import decompose_orchestral_stem


def apply_anti_bleed_gate(audio_stereo: np.ndarray, sr: int, stem_name: str) -> np.ndarray:
    """Apply an Anti-Bleed Spectral Filter & Noise Gate via Spotify pedalboard to clean crosstalk."""
    board = pb.Pedalboard()
    stem = stem_name.lower()

    if "vocal" in stem:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=85.0))
        board.append(pb.LowpassFilter(cutoff_frequency_hz=14000.0))
        board.append(pb.NoiseGate(threshold_db=-45.0, ratio=4.0, attack_ms=5.0, release_ms=100.0))
    elif "drum" in stem:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=28.0))
        board.append(pb.NoiseGate(threshold_db=-42.0, ratio=3.0, attack_ms=2.0, release_ms=80.0))
    elif "bass" in stem:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=30.0))
        board.append(pb.LowpassFilter(cutoff_frequency_hz=5500.0))
        board.append(pb.NoiseGate(threshold_db=-45.0, ratio=4.0, attack_ms=5.0, release_ms=120.0))
    elif "guitar" in stem:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=75.0))
        board.append(pb.LowpassFilter(cutoff_frequency_hz=10000.0))
        board.append(pb.NoiseGate(threshold_db=-45.0, ratio=4.0, attack_ms=5.0, release_ms=100.0))
    elif "synth" in stem or "piano" in stem:
        board.append(pb.HighpassFilter(cutoff_frequency_hz=60.0))
        board.append(pb.NoiseGate(threshold_db=-48.0, ratio=3.0, attack_ms=5.0, release_ms=150.0))
    else:
        board.append(pb.NoiseGate(threshold_db=-48.0, ratio=2.5, attack_ms=10.0, release_ms=150.0))

    try:
        cleaned = board(audio_stereo, sr)
        return cleaned
    except Exception:
        return audio_stereo


def capture_cuda_telemetry(torch_module: Any, telemetry: Dict[str, Any]) -> Dict[str, Any]:
    """Capture actual peak CUDA allocator counters when CUDA is available."""
    if torch_module.cuda.is_available():
        telemetry["device"] = "cuda"
        telemetry["peak_allocated_mb"] = round(torch_module.cuda.max_memory_allocated() / (1024 ** 2), 2)
        telemetry["peak_reserved_mb"] = round(torch_module.cuda.max_memory_reserved() / (1024 ** 2), 2)
    else:
        telemetry["device"] = "cpu"
        telemetry["peak_allocated_mb"] = None
        telemetry["peak_reserved_mb"] = None
    return telemetry


def dsp_spectral_6stem_separation(
    y_stereo: np.ndarray,
    sr: int,
) -> Dict[str, np.ndarray]:
    """Mathematical DSP 6-stem separation using Mid/Side spatial analysis and HPSS spectral filterbanks."""
    n_channels, n_samples = y_stereo.shape
    n_fft = 2048
    hop_length = 512

    # Mid/Side
    y_mid = 0.5 * (y_stereo[0] + y_stereo[1])
    y_side = 0.5 * (y_stereo[0] - y_stereo[1])

    D_L = librosa.stft(y_stereo[0], n_fft=n_fft, hop_length=hop_length)
    D_R = librosa.stft(y_stereo[1], n_fft=n_fft, hop_length=hop_length)
    D_M = librosa.stft(y_mid, n_fft=n_fft, hop_length=hop_length)
    D_S = librosa.stft(y_side, n_fft=n_fft, hop_length=hop_length)

    mag_M = np.abs(D_M)
    mag_S = np.abs(D_S)
    center_ratio = mag_M / (mag_M + mag_S + 1e-6)
    side_ratio = mag_S / (mag_M + mag_S + 1e-6)

    # HPSS
    H_L, P_L = librosa.decompose.hpss(D_L, margin=(1.2, 1.2))
    H_R, P_R = librosa.decompose.hpss(D_R, margin=(1.2, 1.2))
    H_mag = 0.5 * (np.abs(H_L) + np.abs(H_R))
    P_mag = 0.5 * (np.abs(P_L) + np.abs(P_R))

    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)[:, np.newaxis]

    # Frequency mask profiles
    # 1. Bass: 30Hz - 320Hz, harmonic dominated
    f_bass = np.exp(-0.5 * ((freqs - 120.0) / 80.0) ** 2)
    W_bass = f_bass * (H_mag / (H_mag + P_mag + 1e-6)) * center_ratio * 2.0

    # 2. Drums: Percussive dominated across spectrum (Kick 40-100Hz, Snare 180-350Hz, Cymbals > 4kHz)
    f_kick = np.exp(-0.5 * ((freqs - 65.0) / 35.0) ** 2)
    f_snare = np.exp(-0.5 * ((freqs - 220.0) / 90.0) ** 2)
    f_cymbals = 1.0 / (1.0 + np.exp(-(freqs - 4500.0) / 1000.0))
    W_drums = (P_mag / (H_mag + P_mag + 1e-6)) * (1.2 * f_kick + 1.0 * f_snare + 1.2 * f_cymbals + 0.3)

    # 3. Vocals: Centered mid-range harmonic, 200Hz - 4000Hz formant zone
    f_vocal = np.exp(-0.5 * ((freqs - 1200.0) / 900.0) ** 2)
    W_vocals = f_vocal * (H_mag / (H_mag + P_mag + 1e-6)) * (center_ratio ** 1.8) * 2.0

    # 4. Guitar: 80Hz - 6500Hz, wide stereo presence
    f_guitar = np.exp(-0.5 * ((freqs - 850.0) / 600.0) ** 2) + np.exp(-0.5 * ((freqs - 2500.0) / 1500.0) ** 2)
    W_guitar = f_guitar * (side_ratio * 1.5 + 0.5)

    # 5. Synth: 300Hz - 12000Hz, high harmonicity and ambient spread
    f_synth = np.exp(-0.5 * ((freqs - 1800.0) / 1200.0) ** 2) + 0.5 * (freqs > 3000.0)
    W_synth = f_synth * (H_mag / (H_mag + P_mag + 1e-6)) * 0.8

    # 6. Other: Residual high-frequency air and ambient floor
    W_other = 0.15 * np.ones_like(freqs)

    # Soft mask normalization
    W_sum = W_bass + W_drums + W_vocals + W_guitar + W_synth + W_other + 1e-7
    M_bass = W_bass / W_sum
    M_drums = W_drums / W_sum
    M_vocals = W_vocals / W_sum
    M_guitar = W_guitar / W_sum
    M_synth = W_synth / W_sum
    M_other = W_other / W_sum

    stem_masks = {
        "bass": M_bass,
        "drums": M_drums,
        "vocals": M_vocals,
        "guitar": M_guitar,
        "synth": M_synth,
        "other": M_other,
    }

    separated_stems = {}
    for name, mask in stem_masks.items():
        out_L = librosa.istft(D_L * mask, hop_length=hop_length, length=n_samples)
        out_R = librosa.istft(D_R * mask, hop_length=hop_length, length=n_samples)
        separated_stems[name] = np.stack([out_L, out_R], axis=0)

    return separated_stems


def separate_audio_6stems(
    audio_path: str,
    output_dir: str,
    model_name: str = "htdemucs_6s",
    apply_bleed_gate: bool = False,
    split_guitar_substems: bool = False,
    split_vocal_substems: bool = False,
    split_orchestral_substems: bool = False,
    allow_dsp_fallback: bool = False,
    segment_sec: Optional[float] = None,
    auto_polish_stems: bool = False,
    enable_vst3: bool = True,
) -> Dict[str, Any]:
    """Separate full mix audio into 6 stems (vocals, drums, bass, guitar, synth, other)

    with anti-bleed gating, and optional multi-guitar, vocal 3-way, and orchestral sub-stem decompositions.
    """
    if isinstance(audio_path, str):
        audio_path = audio_path.strip().strip('"').strip("'")
    if isinstance(output_dir, str):
        output_dir = output_dir.strip().strip('"').strip("'")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    os.makedirs(output_dir, exist_ok=True)

    y, sr = librosa.load(audio_path, sr=None, mono=False)
    if y.ndim == 1:
        y_stereo = np.stack([y, y], axis=0)
    else:
        y_stereo = y

    duration_sec = float(y_stereo.shape[-1] / sr)
    stem_files = {}
    separation_engine = "dsp_spectral_fallback"
    telemetry: Dict[str, Any] = {"device": "cpu", "duration_sec": None, "peak_allocated_mb": None, "peak_reserved_mb": None}

    # A frequency/spatial filterbank cannot identify instruments in a mixed
    # master. Keep it available only as an explicitly requested preview mode;
    # never silently present it as source separation.
    demucs_success = False
    demucs_error: Optional[str] = None
    if model_name == "experimental_dsp_masks":
        allow_dsp_fallback = True
    try:
        import demucs.pretrained
        import torch
        started_at = time.perf_counter()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        telemetry["device"] = device
        if model_name == "experimental_dsp_masks":
            model = None
            demucs_error = "Direct fast DSP mask requested."
        else:
            model = demucs.pretrained.get_model(model_name)
        if model is not None:
            from demucs.apply import apply_model
            model_sr = int(model.samplerate)
            model_input = y_stereo
            if sr != model_sr:
                model_input = librosa.resample(
                    model_input, orig_sr=sr, target_sr=model_sr, axis=-1
                )
            wav_tensor = torch.tensor(model_input, dtype=torch.float32).unsqueeze(0)
            if device == "cuda":
                model.to(device)
                torch.cuda.reset_peak_memory_stats()
            with torch.inference_mode():
                apply_kwargs = {"device": device}
                if segment_sec is not None:
                    apply_kwargs.update({"split": True, "segment": float(segment_sec)})
                sources = apply_model(model, wav_tensor, **apply_kwargs)[0]

            source_names = model.sources
            if len(source_names) != int(sources.shape[0]):
                raise RuntimeError(
                    f"Demucs returned {sources.shape[0]} sources but model declares {len(source_names)} labels."
                )
            required_sources = {"drums", "bass", "other", "vocals", "guitar", "piano"}
            if set(source_names) != required_sources:
                raise RuntimeError(
                    f"Model {model_name!r} returned {source_names!r}; expected the six htdemucs_6s classes."
                )
            for idx, name in enumerate(source_names):
                stem_audio = sources[idx].detach().to("cpu").numpy()
                if sr != model_sr:
                    stem_audio = librosa.resample(
                        stem_audio, orig_sr=model_sr, target_sr=sr, axis=-1
                    )
                    stem_audio = librosa.util.fix_length(stem_audio, size=y_stereo.shape[-1], axis=-1)
                # htdemucs_6s calls its fifth source "piano". Preserve the
                # model's actual class instead of relabeling it as synth.
                stem_files[name] = stem_audio
            demucs_success = True
            separation_engine = f"demucs_{model_name}"
            telemetry["duration_sec"] = round(time.perf_counter() - started_at, 3)
            if device == "cuda":
                capture_cuda_telemetry(torch, telemetry)
        else:
            demucs_error = f"Demucs model {model_name!r} was not found."
    except Exception as exc:
        try:
            import torch
            is_oom = isinstance(exc, torch.cuda.OutOfMemoryError)
        except (ImportError, AttributeError):
            is_oom = False
        if is_oom:
            if "started_at" in locals():
                telemetry["duration_sec"] = round(time.perf_counter() - started_at, 3)
            try:
                capture_cuda_telemetry(torch, telemetry)
            except Exception:
                pass
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            gc.collect()
            return {
                "status": "error",
                "error": {
                    "code": "CUDA_OUT_OF_MEMORY",
                    "message": "GPU memory was exhausted during separation.",
                    "suggestion": "Retry with a smaller segment/chunk size or select CPU processing.",
                    "model_id": model_name,
                    "telemetry": telemetry,
                },
                "model_metadata": get_model_metadata(model_name),
            }
        demucs_error = f"{type(exc).__name__}: {exc}"
        demucs_success = False
    finally:
        try:
            if "model" in locals() and model is not None:
                model.to("cpu")
                del model
        except Exception:
            pass
        try:
            del wav_tensor
            del sources
        except UnboundLocalError:
            pass
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    if not demucs_success:
        if not allow_dsp_fallback:
            raise RuntimeError(
                "Reliable stem separation did not run, so no output stems were written. "
                f"Demucs error: {demucs_error or 'unknown error'}. Install the project dependencies "
                "and let Demucs download the htdemucs_6s model, or explicitly enable the "
                "experimental DSP fallback (frequency/spatial filtering; instrument bleed is expected)."
            )
        stem_arrays = dsp_spectral_6stem_separation(y_stereo, sr)
        separation_engine = "experimental_dsp_spectral_filterbank"
    else:
        stem_arrays = stem_files

    # Demucs htdemucs_6s produces piano, not synth. Do not create a fake synth
    # file by copying/renaming a different class.

    # Apply Anti-Bleed Gate and write files to disk
    output_paths = {}
    for stem_name, stem_audio in stem_arrays.items():
        if apply_bleed_gate:
            cleaned_audio = apply_anti_bleed_gate(stem_audio, sr, stem_name)
        else:
            cleaned_audio = stem_audio

        out_path = os.path.join(output_dir, f"{stem_name}.wav")
        sf.write(out_path, cleaned_audio.T, sr, subtype="PCM_16")
        output_paths[stem_name] = out_path

    result: Dict[str, Any] = {
        "status": "success" if demucs_success else "partial",
        "audio_path": audio_path,
        "output_dir": output_dir,
        "separation_engine": separation_engine,
        "duration_sec": round(duration_sec, 3),
        "sample_rate": sr,
        "stems": output_paths,
        "model_metadata": get_model_metadata(model_name) if demucs_success else get_model_metadata("experimental_dsp_masks"),
        "telemetry": telemetry,
        "warnings": ([] if demucs_success else [
            "Experimental frequency/spatial filtering was used. These files are not reliable isolated instrument stems."
        ]),
    }

    # 1. Decompose guitar.wav into 3 sub-stems if requested
    if split_guitar_substems and "guitar" in output_paths:
        guitar_file = output_paths["guitar"]
        guitar_decomp = decompose_guitar_stem(guitar_file, output_dir)
        result["guitar_substems"] = {
            "quality": "heuristic_experimental",
            "label": "Experimental Heuristic DSP Mask (Not Source Separation)",
            "verification_status": "experimental_heuristic",
            "warning": "Frequency, transient, pitch-salience and stereo-width masks cannot reliably separate overlapping guitar performances.",
            "guitar_rhythm": guitar_decomp["guitar_rhythm_path"],
            "guitar_lead": guitar_decomp["guitar_lead_path"],
            "guitar_additional": guitar_decomp["guitar_additional_path"],
            "energy_distribution": guitar_decomp["energy_distribution"],
        }

    # 2. Decompose vocals.wav into 3 sub-stems if requested
    if split_vocal_substems and "vocals" in output_paths:
        vocal_file = output_paths["vocals"]
        vocal_decomp = decompose_vocal_stem(vocal_file, output_dir)
        result["vocal_substems"] = {
            "quality": "heuristic_experimental",
            "label": "Experimental Heuristic DSP Mask (Not Source Separation)",
            "verification_status": "experimental_heuristic",
            "warning": "Center/side, spectral-flatness and pitch-salience masks cannot identify lead, co-lead and backing singers.",
            "vocal_lead": vocal_decomp["vocal_lead_path"],
            "vocal_co_lead": vocal_decomp["vocal_co_lead_path"],
            "vocal_backing": vocal_decomp["vocal_backing_path"],
            "energy_distribution": vocal_decomp["energy_distribution"],
        }

    # 3. Decompose other.wav into active orchestral sub-stems if requested
    if split_orchestral_substems and "other" in output_paths:
        other_file = output_paths["other"]
        orch_decomp = decompose_orchestral_stem(other_file, output_dir, auto_detect_only=True)
        result["orchestral_substems"] = {
            "quality": "heuristic_experimental",
            "label": "Experimental Heuristic DSP Mask (Not Source Separation)",
            "verification_status": "experimental_heuristic",
            "warning": "Instrument labels are estimates from broad spectral profiles; exported files are filtered mixtures, not isolated orchestral sources.",
            "detected_instruments": orch_decomp["detected_active_instruments"],
            "exported_stems": orch_decomp["exported_stems"],
        }

    if any((split_guitar_substems, split_vocal_substems, split_orchestral_substems)):
        result["status"] = "partial"
        result["warnings"].append(
            "One or more experimental heuristic sub-stems were written. They are not source-isolated and must not be used as production stems."
        )

    # 4. Optional Auto-Polish Stems (Phase 14: Dynamic VST3 / Native DSP Fallback)
    if auto_polish_stems:
        try:
            from servers.daw_studio_mcp.stem_polisher import polish_stems_batch
        except ImportError:
            try:
                from stem_polisher import polish_stems_batch
            except Exception:
                polish_stems_batch = None

        if polish_stems_batch:
            polish_res = polish_stems_batch(output_paths, output_dir=output_dir, enable_vst3=enable_vst3)
            result["polish_mode"] = polish_res.get("polish_mode", "native_dsp_fallback")
            result["applied_chains"] = polish_res.get("applied_chains", {})
            result["stems"] = polish_res.get("polished_stems", output_paths)

            manifest_path = os.path.join(output_dir, "stem_polish_manifest.json")
            try:
                import json
                with open(manifest_path, "w", encoding="utf-8") as mf:
                    json.dump({
                        "polish_mode": result["polish_mode"],
                        "applied_chains": result["applied_chains"],
                    }, mf, indent=2)
            except Exception:
                pass

    return result
