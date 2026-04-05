from __future__ import annotations

import itertools
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from secure_delivery.experiments.runner import run_batch


def run_parameter_sweep(
    base_config_dir: str,
    matrix_path: str,
    output_root: str,
    replicates: int = 1,
    seed_step: int = 1,
) -> Dict[str, object]:
    root = Path(output_root)
    generated_dir = root / "generated_configs"
    results_dir = root / "results"
    generated = generate_sweep_configs(base_config_dir, matrix_path, str(generated_dir))
    batch_result = run_batch(str(generated_dir), str(results_dir), replicates=replicates, seed_step=seed_step)
    return {
        "generated_config_dir": str(generated_dir),
        "generated_config_count": len(generated),
        "generated_configs": generated,
        "results_root": str(results_dir),
        "batch": batch_result,
    }


def generate_sweep_configs(base_config_dir: str, matrix_path: str, generated_dir: str) -> List[str]:
    matrix_payload = _load_json(Path(matrix_path))
    dimensions = dict(matrix_payload.get("dimensions", {}))
    filters = dict(matrix_payload.get("filters", {}))
    if not dimensions:
        raise ValueError("Sweep matrix must define at least one dimension")

    target_dir = Path(generated_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    generated_files: List[str] = []
    for config_path in sorted(Path(base_config_dir).rglob("*.json")):
        payload = _load_json(config_path)
        if not _matches_filters(payload, filters):
            continue

        for override_values in _iter_dimension_values(dimensions):
            variant_payload = _apply_dimension_overrides(payload, override_values, config_path)
            suffix = _format_suffix(override_values)
            output_path = target_dir / f"{config_path.stem}_{suffix}.json"
            output_path.write_text(json.dumps(variant_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            generated_files.append(str(output_path))

    return generated_files


def _apply_dimension_overrides(
    payload: Dict[str, object],
    override_values: Dict[str, object],
    config_path: Path,
) -> Dict[str, object]:
    variant_payload = deepcopy(payload)
    run_id = str(variant_payload["run_id"])
    suffix = _format_suffix(override_values)
    variant_payload["run_id"] = f"{run_id}_{suffix}"
    variant_payload["notes"] = _extend_notes(str(variant_payload.get("notes", "")), override_values)

    channel = dict(variant_payload.get("channel", {}))
    if "bandwidth_bps" in override_values:
        channel["bandwidth_bps"] = int(override_values["bandwidth_bps"])
    if "buffer_size" in override_values:
        channel["buffer_size"] = int(override_values["buffer_size"])
    if "loss_probability" in override_values:
        channel["loss_probability"] = float(override_values["loss_probability"])
    variant_payload["channel"] = channel

    policy_backend = dict(variant_payload.get("policy_backend", {}))
    policy_path = Path(str(policy_backend["path"]))
    if not policy_path.is_absolute():
        policy_backend["path"] = str((config_path.parent / policy_path).resolve())
    variant_payload["policy_backend"] = policy_backend
    variant_payload["sweep_parameters"] = override_values
    return variant_payload


def _matches_filters(payload: Dict[str, object], filters: Dict[str, object]) -> bool:
    scenario_families = filters.get("scenario_families")
    if scenario_families and str(payload.get("scenario_family", payload.get("scenario", ""))) not in scenario_families:
        return False
    load_profiles = filters.get("load_profiles")
    if load_profiles and str(payload.get("load_profile", "")) not in load_profiles:
        return False
    run_ids = filters.get("run_ids")
    if run_ids and str(payload.get("run_id", "")) not in run_ids:
        return False
    return True


def _iter_dimension_values(dimensions: Dict[str, Iterable[object]]) -> Iterable[Dict[str, object]]:
    ordered_keys = list(dimensions.keys())
    ordered_values = [list(dimensions[key]) for key in ordered_keys]
    for values in itertools.product(*ordered_values):
        yield {key: value for key, value in zip(ordered_keys, values)}


def _format_suffix(override_values: Dict[str, object]) -> str:
    parts: List[str] = []
    if "bandwidth_bps" in override_values:
        bandwidth_bps = int(override_values["bandwidth_bps"])
        parts.append(f"bw{bandwidth_bps // 1000}k")
    if "buffer_size" in override_values:
        parts.append(f"buf{int(override_values['buffer_size'])}")
    if "loss_probability" in override_values:
        loss_probability = float(override_values["loss_probability"])
        parts.append(f"loss{int(round(loss_probability * 100))}pct")
    return "_".join(parts) if parts else "variant"


def _extend_notes(notes: str, override_values: Dict[str, object]) -> str:
    parts = [notes] if notes else []
    parts.append(
        "Sweep overrides: "
        + ", ".join(f"{key}={value}" for key, value in override_values.items())
    )
    return " ".join(parts)


def _load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
