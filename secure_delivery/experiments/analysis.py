from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def aggregate_batch_results(output_root: str) -> Dict[str, str]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)

    run_dirs = sorted({path.parent for path in root.rglob("runs.csv") if path.parent != root})
    batch_runs: List[Dict[str, object]] = []
    batch_messages: List[Dict[str, object]] = []
    batch_queue: List[Dict[str, object]] = []
    batch_resources: List[Dict[str, object]] = []
    batch_policy_events: List[Dict[str, object]] = []

    for run_dir in run_dirs:
        manifest = _read_manifest(run_dir / "manifest.json")
        runs_rows = _read_csv(run_dir / "runs.csv")
        messages_rows = _read_csv(run_dir / "messages.csv")
        queue_rows = _read_csv(run_dir / "queue_timeseries.csv")
        resource_rows = _read_csv(run_dir / "resource_usage.csv")
        policy_rows = _read_csv(run_dir / "policy_events.csv")

        run_context = {
            "run_id": manifest.get("run_id", run_dir.name),
            "base_run_id": manifest.get("base_run_id", manifest.get("run_id", run_dir.name)),
            "replicate_index": manifest.get("replicate_index", 0),
            "scenario": manifest.get("scenario", ""),
            "scenario_family": manifest.get("scenario_family", manifest.get("scenario", "")),
            "load_profile": manifest.get("load_profile", "custom"),
            "config_name": Path(manifest.get("config_path", run_dir.name)).stem,
        }

        for row in runs_rows:
            batch_runs.append({**run_context, **row})
        for row in messages_rows:
            batch_messages.append({**run_context, **row})
        for row in queue_rows:
            batch_queue.append({**run_context, **row})
        for row in resource_rows:
            batch_resources.append({**run_context, **row})
        for row in policy_rows:
            batch_policy_events.append({**run_context, **row})

    batch_runs_path = root / "batch_runs.csv"
    batch_messages_path = root / "batch_messages.csv"
    batch_queue_path = root / "batch_queue_timeseries.csv"
    batch_resources_path = root / "batch_resource_usage.csv"
    batch_policy_path = root / "batch_policy_events.csv"
    scenario_comparison_path = root / "scenario_comparison.csv"

    _write_csv(batch_runs_path, batch_runs)
    _write_csv(batch_messages_path, batch_messages)
    _write_csv(batch_queue_path, batch_queue)
    _write_csv(batch_resources_path, batch_resources)
    _write_csv(batch_policy_path, batch_policy_events)
    _write_csv(scenario_comparison_path, _group_rows(batch_runs, ("load_profile", "scenario_family")))

    return {
        "batch_runs": str(batch_runs_path),
        "batch_messages": str(batch_messages_path),
        "batch_queue_timeseries": str(batch_queue_path),
        "batch_resource_usage": str(batch_resources_path),
        "batch_policy_events": str(batch_policy_path),
        "scenario_comparison": str(scenario_comparison_path),
    }


def compare_metric(output_root: str, metric: str, output_path: str | None = None) -> List[Dict[str, object]]:
    root = Path(output_root)
    batch_runs_path = root / "batch_runs.csv"
    if not batch_runs_path.exists():
        aggregate_batch_results(output_root)
    rows = _read_csv(batch_runs_path)
    grouped: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for row in rows:
        value = _to_float(row.get(metric))
        if value is None:
            continue
        grouped[(row.get("load_profile", "custom"), row.get("scenario_family", ""))].append(value)

    result_rows: List[Dict[str, object]] = []
    for (load_profile, scenario_family), values in sorted(grouped.items()):
        summary = _summarize_values(values)
        result_rows.append(
            {
                "load_profile": load_profile,
                "scenario_family": scenario_family,
                "metric": metric,
                **summary,
            }
        )

    target_path = Path(output_path) if output_path else root / f"comparison_{metric}.csv"
    _write_csv(target_path, result_rows)
    return result_rows


def export_article_tables(output_root: str, output_dir: str) -> Dict[str, str]:
    root = Path(output_root)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    batch_runs_path = root / "batch_runs.csv"
    if not batch_runs_path.exists():
        aggregate_batch_results(output_root)

    rows = _read_csv(batch_runs_path)
    grouped = _group_rows(rows, ("load_profile", "scenario_family"))

    critical_rows: List[Dict[str, object]] = []
    system_rows: List[Dict[str, object]] = []
    components_rows: List[Dict[str, object]] = []
    delta_rows = _build_scenario_delta_rows(grouped)

    for row in grouped:
        critical_rows.append(
            {
                "load_profile": row["load_profile"],
                "scenario_family": row["scenario_family"],
                "critical_deadline_met_ratio": row.get("critical_deadline_met_ratio"),
                "critical_deadline_met_ratio__ci95_low": row.get("critical_deadline_met_ratio__ci95_low"),
                "critical_deadline_met_ratio__ci95_high": row.get("critical_deadline_met_ratio__ci95_high"),
                "critical_latency_mean_s": row.get("critical_latency_mean_s"),
                "critical_latency_mean_s__ci95_low": row.get("critical_latency_mean_s__ci95_low"),
                "critical_latency_mean_s__ci95_high": row.get("critical_latency_mean_s__ci95_high"),
                "critical_latency_p95_s": row.get("critical_latency_p95_s"),
                "critical_jitter_s": row.get("critical_jitter_s"),
                "critical_jitter_s__ci95_low": row.get("critical_jitter_s__ci95_low"),
                "critical_jitter_s__ci95_high": row.get("critical_jitter_s__ci95_high"),
            }
        )
        system_rows.append(
            {
                "load_profile": row["load_profile"],
                "scenario_family": row["scenario_family"],
                "channel_utilization": row.get("channel_utilization"),
                "channel_utilization__ci95_low": row.get("channel_utilization__ci95_low"),
                "channel_utilization__ci95_high": row.get("channel_utilization__ci95_high"),
                "crypto_utilization": row.get("crypto_utilization"),
                "crypto_utilization__ci95_low": row.get("crypto_utilization__ci95_low"),
                "crypto_utilization__ci95_high": row.get("crypto_utilization__ci95_high"),
                "average_queue_length": row.get("average_queue_length"),
                "background_delivered_ratio": row.get("background_delivered_ratio"),
                "background_dropped_ratio": row.get("background_dropped_ratio"),
            }
        )
        components_rows.append(
            {
                "load_profile": row["load_profile"],
                "scenario_family": row["scenario_family"],
                "critical_classification_time_mean_s": row.get("critical_classification_time_mean_s"),
                "critical_crypto_time_mean_s": row.get("critical_crypto_time_mean_s"),
                "critical_queue_time_mean_s": row.get("critical_queue_time_mean_s"),
                "critical_tx_time_mean_s": row.get("critical_tx_time_mean_s"),
                "critical_ack_time_mean_s": row.get("critical_ack_time_mean_s"),
            }
        )

    critical_path = target_dir / "table_critical_performance.csv"
    system_path = target_dir / "table_system_cost.csv"
    components_path = target_dir / "table_critical_components.csv"
    deltas_path = target_dir / "table_scenario_deltas.csv"
    _write_csv(critical_path, critical_rows)
    _write_csv(system_path, system_rows)
    _write_csv(components_path, components_rows)
    _write_csv(deltas_path, delta_rows)

    return {
        "critical_performance": str(critical_path),
        "system_cost": str(system_path),
        "critical_components": str(components_path),
        "scenario_deltas": str(deltas_path),
    }


def _group_rows(rows: List[Dict[str, object]], keys: Tuple[str, ...]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, ...], List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)

    result_rows: List[Dict[str, object]] = []
    for key_values, grouped_rows in sorted(grouped.items()):
        aggregated: Dict[str, object] = {key: value for key, value in zip(keys, key_values)}
        aggregated["runs"] = len(grouped_rows)
        numeric_columns = _numeric_columns(grouped_rows)
        for column in numeric_columns:
            values = [_to_float(row.get(column)) for row in grouped_rows]
            values = [value for value in values if value is not None]
            if values:
                summary = _summarize_values(values)
                aggregated[column] = summary["mean"]
                aggregated[f"{column}__min"] = summary["min"]
                aggregated[f"{column}__max"] = summary["max"]
                aggregated[f"{column}__stddev"] = summary["stddev"]
                aggregated[f"{column}__stderr"] = summary["stderr"]
                aggregated[f"{column}__ci95_low"] = summary["ci95_low"]
                aggregated[f"{column}__ci95_high"] = summary["ci95_high"]
        result_rows.append(aggregated)
    return result_rows


def _build_scenario_delta_rows(grouped_rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    by_key = {
        (str(row.get("load_profile", "custom")), str(row.get("scenario_family", ""))): row for row in grouped_rows
    }
    load_profiles = sorted({str(row.get("load_profile", "custom")) for row in grouped_rows})
    scenario_pairs = (("B", "A"), ("C", "A"), ("C", "B"))
    result_rows: List[Dict[str, object]] = []

    for load_profile in load_profiles:
        for lhs, rhs in scenario_pairs:
            lhs_row = by_key.get((load_profile, lhs))
            rhs_row = by_key.get((load_profile, rhs))
            if not lhs_row or not rhs_row:
                continue
            lhs_latency = _to_float(lhs_row.get("critical_latency_mean_s")) or 0.0
            rhs_latency = _to_float(rhs_row.get("critical_latency_mean_s")) or 0.0
            result_rows.append(
                {
                    "load_profile": load_profile,
                    "lhs_scenario": lhs,
                    "rhs_scenario": rhs,
                    "critical_deadline_met_ratio_delta": (_to_float(lhs_row.get("critical_deadline_met_ratio")) or 0.0)
                    - (_to_float(rhs_row.get("critical_deadline_met_ratio")) or 0.0),
                    "critical_latency_mean_s_delta": lhs_latency - rhs_latency,
                    "critical_latency_improvement_ratio": _safe_divide(rhs_latency - lhs_latency, rhs_latency),
                    "critical_queue_time_mean_s_delta": (_to_float(lhs_row.get("critical_queue_time_mean_s")) or 0.0)
                    - (_to_float(rhs_row.get("critical_queue_time_mean_s")) or 0.0),
                    "critical_crypto_time_mean_s_delta": (_to_float(lhs_row.get("critical_crypto_time_mean_s")) or 0.0)
                    - (_to_float(rhs_row.get("critical_crypto_time_mean_s")) or 0.0),
                    "background_dropped_ratio_delta": (_to_float(lhs_row.get("background_dropped_ratio")) or 0.0)
                    - (_to_float(rhs_row.get("background_dropped_ratio")) or 0.0),
                    "background_delivered_ratio_delta": (_to_float(lhs_row.get("background_delivered_ratio")) or 0.0)
                    - (_to_float(rhs_row.get("background_delivered_ratio")) or 0.0),
                }
            )
    return result_rows


def _numeric_columns(rows: List[Dict[str, object]]) -> List[str]:
    columns: List[str] = []
    seen = set()
    for row in rows:
        for key, value in row.items():
            if key in seen:
                continue
            if _to_float(value) is not None:
                columns.append(key)
                seen.add(key)
    return columns


def _to_float(value: object) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_divide(left: float, right: float) -> float:
    return left / right if right else 0.0


def _summarize_values(values: List[float]) -> Dict[str, float]:
    count = len(values)
    mean = sum(values) / count
    minimum = min(values)
    maximum = max(values)
    if count > 1:
        variance = sum((value - mean) ** 2 for value in values) / (count - 1)
        stddev = math.sqrt(variance)
        stderr = stddev / math.sqrt(count)
    else:
        stddev = 0.0
        stderr = 0.0
    ci_margin = 1.96 * stderr
    return {
        "count": count,
        "mean": mean,
        "min": minimum,
        "max": maximum,
        "stddev": stddev,
        "stderr": stderr,
        "ci95_low": mean - ci_margin,
        "ci95_high": mean + ci_margin,
    }


def _read_manifest(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(path: Path) -> List[Dict[str, object]]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[Dict[str, object]]) -> None:
    rows = list(rows)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
