from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def build_plots(input_dir: str, output_dir: str) -> Dict[str, str]:
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required for build-plots. Install dependencies before using this command."
        ) from exc

    source_dir = Path(input_dir)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    messages = _read_csv(source_dir / "messages.csv")
    queue_timeseries = _read_csv(source_dir / "queue_timeseries.csv")

    latency_by_class: Dict[str, List[float]] = defaultdict(list)
    critical_latencies: List[float] = []
    deadline_ratio: Dict[str, float] = {}

    for row in messages:
        if not row.get("total_latency_s"):
            continue
        latency = float(row["total_latency_s"])
        latency_by_class[row["message_class"]].append(latency)
        if row["message_class"] == "critical":
            critical_latencies.append(latency)

    plots: Dict[str, str] = {}

    if latency_by_class:
        fig, ax = plt.subplots(figsize=(9, 5))
        classes = list(latency_by_class.keys())
        ax.boxplot([latency_by_class[item] for item in classes], labels=classes)
        ax.set_title("Latency Distribution by Message Class")
        ax.set_ylabel("Latency (s)")
        output_path = target_dir / "latency_distribution.png"
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        plots["latency_distribution"] = str(output_path)

    if critical_latencies:
        sorted_values = sorted(critical_latencies)
        cdf_y = [(index + 1) / len(sorted_values) for index in range(len(sorted_values))]
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(sorted_values, cdf_y)
        ax.set_title("Critical Latency CDF")
        ax.set_xlabel("Latency (s)")
        ax.set_ylabel("CDF")
        output_path = target_dir / "critical_latency_cdf.png"
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        plots["critical_latency_cdf"] = str(output_path)

    if queue_timeseries:
        times = [float(row["time_s"]) for row in queue_timeseries]
        totals = [float(row["queue_total"]) for row in queue_timeseries]
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(times, totals)
        ax.set_title("Queue Length Over Time")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Queued messages")
        output_path = target_dir / "queue_timeseries.png"
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        plots["queue_timeseries"] = str(output_path)

    return plots


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
