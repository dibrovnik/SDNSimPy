from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


CLASS_LABELS = {
    "critical": "Критический",
    "control": "Управляющий",
    "telemetry": "Телеметрия",
    "background": "Фоновый",
}

LOAD_LABELS = {
    "normal": "Нормальная",
    "high": "Высокая",
    "overload": "Перегрузка",
    "emergency": "Аварийная",
}

COMPONENT_LABELS = {
    "classification": "Классификация",
    "crypto": "Крипто",
    "queue": "Очередь",
    "tx": "Передача",
    "ack": "Подтверждение",
}


def _display_class(value: str) -> str:
    return CLASS_LABELS.get(value, value)


def _display_load(value: str) -> str:
    return LOAD_LABELS.get(value, value)


def _display_component(value: str) -> str:
    return COMPONENT_LABELS.get(value, value)


def _display_load_scenario_label(value: str) -> str:
    if "-" not in value:
        return value
    load, scenario = value.split("-", 1)
    return f"{_display_load(load)} | {scenario}"


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
    data_dir = target_dir / "plot_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if (source_dir / "batch_runs.csv").exists():
        return _build_batch_plots(source_dir, target_dir, data_dir, plt)
    return _build_single_run_plots(source_dir, target_dir, data_dir, plt)


def _build_single_run_plots(source_dir: Path, target_dir: Path, data_dir: Path, plt) -> Dict[str, str]:
    messages = _read_csv(source_dir / "messages.csv")
    plots: Dict[str, str] = {}

    latency_by_class: Dict[str, List[float]] = defaultdict(list)
    critical_latencies: List[float] = []
    component_rows: List[Dict[str, object]] = []
    throughput_rows: List[Dict[str, object]] = []
    crypto_share_rows: List[Dict[str, object]] = []
    deadline_ratio_rows: List[Dict[str, object]] = []

    for row in messages:
        if row.get("message_class") and row.get("total_latency_s"):
            latency = float(row["total_latency_s"])
            latency_by_class[row["message_class"]].append(latency)
            if row["message_class"] == "critical":
                critical_latencies.append(latency)

    for message_class, values in latency_by_class.items():
        class_rows = [row for row in messages if row.get("message_class") == message_class]
        delivered = sum(1 for row in class_rows if row.get("delivered", "").lower() == "true")
        deadline_met = sum(
            1
            for row in class_rows
            if row.get("delivered", "").lower() == "true" and row.get("deadline_missed", "").lower() != "true"
        )
        wire_bytes = sum(float(row.get("full_size_bytes") or 0) for row in class_rows if row.get("delivered", "").lower() == "true")
        useful_bytes = sum(float(row.get("payload_bytes") or 0) for row in class_rows if row.get("delivered", "").lower() == "true")
        deadline_ratio_rows.append(
            {
                "message_class": message_class,
                "deadline_met_ratio": deadline_met / len(class_rows) if class_rows else 0.0,
            }
        )
        throughput_rows.append(
            {
                "message_class": message_class,
                "wire_bytes": wire_bytes,
                "useful_bytes": useful_bytes,
            }
        )
        component_rows.append(
            {
                "message_class": message_class,
                "classification_time_mean_s": _mean([_to_float(row.get("classification_time_s")) for row in class_rows]),
                "crypto_time_mean_s": _mean([_to_float(row.get("crypto_time_s")) for row in class_rows]),
                "queue_time_mean_s": _mean([_to_float(row.get("queue_time_s")) for row in class_rows]),
                "tx_time_mean_s": _mean([_to_float(row.get("tx_time_s")) for row in class_rows]),
                "ack_time_mean_s": _mean([_to_float(row.get("ack_time_s")) for row in class_rows]),
            }
        )
        crypto_share_rows.append(
            {
                "message_class": message_class,
                "crypto_share_latency_ratio": _mean(
                    [
                        _safe_divide(_to_float(row.get("crypto_time_s")) or 0.0, _to_float(row.get("total_latency_s")) or 0.0)
                        for row in class_rows
                        if _to_float(row.get("total_latency_s")) not in (None, 0.0)
                    ]
                ),
            }
        )

    if latency_by_class:
        class_keys = list(latency_by_class.keys())
        classes = [_display_class(item) for item in class_keys]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.boxplot([latency_by_class[item] for item in class_keys], labels=classes)
        ax.set_title("Распределение задержки по классам")
        ax.set_ylabel("Задержка, с")
        plots["latency_distribution"] = _save_figure(fig, target_dir / "latency_distribution", plt)
        _write_csv(data_dir / "latency_distribution.csv", _flatten_group(latency_by_class, "message_class", "latency_s"))

    if critical_latencies:
        sorted_values = sorted(critical_latencies)
        cdf_y = [(index + 1) / len(sorted_values) for index in range(len(sorted_values))]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(sorted_values, cdf_y)
        ax.set_title("Функция распределения (CDF) задержки критического класса")
        ax.set_xlabel("Задержка, с")
        ax.set_ylabel("Функция распределения (CDF)")
        plots["critical_latency_cdf"] = _save_figure(fig, target_dir / "critical_latency_cdf", plt)
        _write_csv(
            data_dir / "critical_latency_cdf.csv",
            [{"latency_s": latency, "cdf": cdf} for latency, cdf in zip(sorted_values, cdf_y)],
        )

    queue_timeseries = _read_csv(source_dir / "queue_timeseries.csv")
    if queue_timeseries:
        times = [float(row["time_s"]) for row in queue_timeseries]
        totals = [float(row["queue_total"]) for row in queue_timeseries]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(times, totals)
        ax.set_title("Длина очереди во времени")
        ax.set_xlabel("Время, с")
        ax.set_ylabel("Сообщений в очереди")
        plots["queue_timeseries"] = _save_figure(fig, target_dir / "queue_timeseries", plt)
        _write_csv(data_dir / "queue_timeseries.csv", queue_timeseries)

    if deadline_ratio_rows:
        fig, ax = plt.subplots(figsize=(10, 5))
        classes = [_display_class(str(row["message_class"])) for row in deadline_ratio_rows]
        ratios = [float(row["deadline_met_ratio"]) for row in deadline_ratio_rows]
        ax.bar(classes, ratios)
        ax.set_ylim(0, 1.05)
        ax.set_title("Доля сообщений в дедлайне по классам")
        ax.set_ylabel("Доля")
        plots["deadline_met_ratio"] = _save_figure(fig, target_dir / "deadline_met_ratio", plt)
        _write_csv(data_dir / "deadline_met_ratio.csv", deadline_ratio_rows)

    if component_rows:
        classes = [_display_class(str(row["message_class"])) for row in component_rows]
        components = [
            ("classification_time_mean_s", "classification"),
            ("crypto_time_mean_s", "crypto"),
            ("queue_time_mean_s", "queue"),
            ("tx_time_mean_s", "tx"),
            ("ack_time_mean_s", "ack"),
        ]
        fig, ax = plt.subplots(figsize=(10, 6))
        bottoms = [0.0] * len(classes)
        for field, label in components:
            values = [float(row[field]) for row in component_rows]
            ax.bar(classes, values, bottom=bottoms, label=_display_component(label))
            bottoms = [bottom + value for bottom, value in zip(bottoms, values)]
        ax.set_title("Разложение задержки по компонентам")
        ax.set_ylabel("Среднее время компонента, с")
        ax.legend(title="Компонент")
        plots["latency_components"] = _save_figure(fig, target_dir / "latency_components", plt)
        _write_csv(data_dir / "latency_components.csv", component_rows)

    if throughput_rows:
        classes = [_display_class(str(row["message_class"])) for row in throughput_rows]
        useful = [float(row["useful_bytes"]) for row in throughput_rows]
        wire = [float(row["wire_bytes"]) for row in throughput_rows]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(classes, wire, label="Полный трафик, байт")
        ax.bar(classes, useful, label="Полезный трафик, байт")
        ax.set_title("Пропускная способность доставленных сообщений")
        ax.set_ylabel("Байт")
        ax.legend()
        plots["throughput_by_class"] = _save_figure(fig, target_dir / "throughput_by_class", plt)
        _write_csv(data_dir / "throughput_by_class.csv", throughput_rows)

    if crypto_share_rows:
        classes = [_display_class(str(row["message_class"])) for row in crypto_share_rows]
        values = [float(row["crypto_share_latency_ratio"]) for row in crypto_share_rows]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(classes, values)
        ax.set_ylim(0, max(values) * 1.2 if values else 1.0)
        ax.set_title("Доля криптообработки в полной задержке")
        ax.set_ylabel("Доля")
        plots["crypto_share"] = _save_figure(fig, target_dir / "crypto_share", plt)
        _write_csv(data_dir / "crypto_share.csv", crypto_share_rows)

    return plots


def _build_batch_plots(source_dir: Path, target_dir: Path, data_dir: Path, plt) -> Dict[str, str]:
    runs = _read_csv(source_dir / "batch_runs.csv")
    messages = _read_csv(source_dir / "batch_messages.csv")
    plots: Dict[str, str] = {}

    critical_cdf_rows: List[Dict[str, object]] = []
    critical_by_scenario: Dict[str, List[float]] = defaultdict(list)
    for row in messages:
        if row.get("message_class") == "critical" and row.get("total_latency_s"):
            critical_by_scenario[str(row.get("scenario_family", ""))].append(float(row["total_latency_s"]))

    if critical_by_scenario:
        fig, ax = plt.subplots(figsize=(10, 5))
        for scenario_family, values in sorted(critical_by_scenario.items()):
            sorted_values = sorted(values)
            cdf_y = [(index + 1) / len(sorted_values) for index in range(len(sorted_values))]
            ax.plot(sorted_values, cdf_y, label=scenario_family)
            for latency, cdf in zip(sorted_values, cdf_y):
                critical_cdf_rows.append(
                    {
                        "scenario_family": scenario_family,
                        "latency_s": latency,
                        "cdf": cdf,
                    }
                )
        ax.set_title("CDF задержки критического класса по сценариям")
        ax.set_xlabel("Задержка, с")
        ax.set_ylabel("Функция распределения (CDF)")
        ax.legend(title="Сценарий")
        plots["critical_latency_cdf_by_scenario"] = _save_figure(fig, target_dir / "critical_latency_cdf_by_scenario", plt)
        _write_csv(data_dir / "critical_latency_cdf_by_scenario.csv", critical_cdf_rows)

    grouped = _group_runs(runs)
    if grouped:
        deadline_rows = []
        component_rows = []
        throughput_rows = []

        for row in grouped:
            deadline_rows.append(
                {
                    "load_profile": row["load_profile"],
                    "scenario_family": row["scenario_family"],
                    "critical_deadline_met_ratio": row.get("critical_deadline_met_ratio", 0.0),
                }
            )
            component_rows.append(
                {
                    "label": f'{row["load_profile"]}-{row["scenario_family"]}',
                    "classification": row.get("critical_classification_time_mean_s", 0.0),
                    "crypto": row.get("critical_crypto_time_mean_s", 0.0),
                    "queue": row.get("critical_queue_time_mean_s", 0.0),
                    "tx": row.get("critical_tx_time_mean_s", 0.0),
                    "ack": row.get("critical_ack_time_mean_s", 0.0),
                }
            )
            for message_class in ("critical", "control", "telemetry", "background"):
                throughput_rows.append(
                    {
                        "label": f'{row["load_profile"]}-{row["scenario_family"]}',
                        "message_class": message_class,
                        "useful_throughput_bps": row.get(f"{message_class}_useful_throughput_bps", 0.0),
                    }
                )

        plots["critical_deadline_by_scenario"] = _plot_grouped_deadline(deadline_rows, target_dir / "critical_deadline_by_scenario", plt)
        _write_csv(data_dir / "critical_deadline_by_scenario.csv", deadline_rows)

        plots["critical_components_by_scenario"] = _plot_component_breakdown(component_rows, target_dir / "critical_components_by_scenario", plt)
        _write_csv(data_dir / "critical_components_by_scenario.csv", component_rows)

        plots["useful_throughput_by_class_and_scenario"] = _plot_class_throughput(
            throughput_rows,
            target_dir / "useful_throughput_by_class_and_scenario",
            plt,
        )
        _write_csv(data_dir / "useful_throughput_by_class_and_scenario.csv", throughput_rows)

    return plots


def _plot_grouped_deadline(rows: List[Dict[str, object]], output_path: Path, plt) -> str:
    load_profiles = sorted({str(row["load_profile"]) for row in rows})
    scenario_families = sorted({str(row["scenario_family"]) for row in rows})
    width = 0.22
    x_positions = list(range(len(load_profiles)))
    fig, ax = plt.subplots(figsize=(10, 5))
    for index, scenario_family in enumerate(scenario_families):
        values = []
        for load_profile in load_profiles:
            matched = next(
                (row for row in rows if row["load_profile"] == load_profile and row["scenario_family"] == scenario_family),
                None,
            )
            values.append(float(matched["critical_deadline_met_ratio"]) if matched else 0.0)
        offset_positions = [x + (index - (len(scenario_families) - 1) / 2) * width for x in x_positions]
        ax.bar(offset_positions, values, width=width, label=scenario_family)
    ax.set_xticks(x_positions)
    ax.set_xticklabels([_display_load(item) for item in load_profiles])
    ax.set_ylim(0, 1.05)
    ax.set_title("Доля критического класса в дедлайне по сценариям и нагрузкам")
    ax.set_ylabel("Доля")
    ax.legend(title="Сценарий")
    return _save_figure(fig, output_path, plt)


def _plot_component_breakdown(rows: List[Dict[str, object]], output_path: Path, plt) -> str:
    labels = [_display_load_scenario_label(str(row["label"])) for row in rows]
    components = ["classification", "crypto", "queue", "tx", "ack"]
    fig, ax = plt.subplots(figsize=(12, 6))
    bottoms = [0.0] * len(labels)
    for component in components:
        values = [float(row[component]) for row in rows]
        ax.bar(labels, values, bottom=bottoms, label=_display_component(component))
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]
    ax.set_title("Разложение задержки критического класса по компонентам")
    ax.set_ylabel("Среднее время компонента, с")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(title="Компонент")
    return _save_figure(fig, output_path, plt)


def _plot_class_throughput(rows: List[Dict[str, object]], output_path: Path, plt) -> str:
    labels = sorted({str(row["label"]) for row in rows})
    classes = ["critical", "control", "telemetry", "background"]
    width = 0.18
    x_positions = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(12, 6))
    for index, message_class in enumerate(classes):
        values = []
        for label in labels:
            matched = next(
                (row for row in rows if row["label"] == label and row["message_class"] == message_class),
                None,
            )
            values.append(float(matched["useful_throughput_bps"]) if matched else 0.0)
        offset_positions = [x + (index - (len(classes) - 1) / 2) * width for x in x_positions]
        ax.bar(offset_positions, values, width=width, label=_display_class(message_class))
    ax.set_xticks(x_positions)
    ax.set_xticklabels([_display_load_scenario_label(item) for item in labels], rotation=30)
    ax.set_title("Полезная пропускная способность по классам и сценариям")
    ax.set_ylabel("бит/с")
    ax.legend(title="Класс")
    return _save_figure(fig, output_path, plt)


def _save_figure(fig, base_path: Path, plt) -> str:
    png_path = base_path.with_suffix(".png")
    fig.tight_layout()
    fig.savefig(png_path, dpi=160)
    plt.close(fig)
    return str(png_path)


def _group_runs(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[tuple[str, str], List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("load_profile", "custom")), str(row.get("scenario_family", "")))].append(row)

    result_rows: List[Dict[str, object]] = []
    for (load_profile, scenario_family), items in sorted(grouped.items()):
        aggregated: Dict[str, object] = {
            "load_profile": load_profile,
            "scenario_family": scenario_family,
        }
        numeric_columns = sorted(
            {
                key
                for item in items
                for key, value in item.items()
                if _to_float(value) is not None
            }
        )
        for column in numeric_columns:
            values = [_to_float(item.get(column)) for item in items]
            values = [value for value in values if value is not None]
            if values:
                aggregated[column] = sum(values) / len(values)
        result_rows.append(aggregated)
    return result_rows


def _flatten_group(grouped: Dict[str, Sequence[float]], group_key: str, value_key: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for group_name, values in grouped.items():
        for value in values:
            rows.append({group_key: group_name, value_key: value})
    return rows


def _mean(values: Iterable[float | None]) -> float:
    cleaned = [value for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else 0.0


def _safe_divide(left: float, right: float) -> float:
    return left / right if right else 0.0


def _to_float(value: object) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> List[Dict[str, str]]:
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
