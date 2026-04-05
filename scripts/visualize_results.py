#!/usr/bin/env python3
"""
Расширенная визуализация результатов batch-экспериментов.

Скрипт читает агрегированные CSV из директории результатов и генерирует:
1) базовые графики через secure_delivery.cli build-plots;
2) расширенный набор сравнительных графиков по QoS/ресурсам/политикам;
3) markdown-отчет с автоматически рассчитанными метриками и выводами.

Требует установки: matplotlib, seaborn, pandas, numpy.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Позволяет запускать скрипт напрямую из scripts/ без установки пакета.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from secure_delivery.plots.builder import build_plots as build_core_plots


SCENARIO_ORDER = ["A", "B", "C"]
LOAD_ORDER = ["normal", "high", "overload", "emergency"]
TRAFFIC_CLASSES = ["critical", "control", "telemetry", "background"]
TRUE_VALUES = {"1", "true", "t", "yes", "y"}

LOAD_LABELS = {
    "normal": "Нормальная",
    "high": "Высокая",
    "overload": "Перегрузка",
    "emergency": "Аварийная",
}

CLASS_LABELS = {
    "critical": "Критический",
    "control": "Управляющий",
    "telemetry": "Телеметрия",
    "background": "Фоновый",
}

COMPONENT_LABELS = {
    "classification": "Классификация",
    "crypto": "Крипто",
    "queue": "Очередь",
    "tx": "Передача",
    "ack": "Подтверждение",
}

OUTCOME_LABELS = {
    "on_time": "В дедлайне",
    "deadline_missed": "Просрочено",
    "dropped": "Сброшено",
}

REASON_LABELS = {
    "initial": "Начальная",
    "scheduled": "Плановая",
    "unspecified": "Не указана",
}

CORE_PLOT_TITLES = {
    "critical_latency_cdf_by_scenario": "CDF задержки критического класса по сценариям",
    "critical_deadline_by_scenario": "Доля критического класса в дедлайне по сценариям",
    "critical_components_by_scenario": "Компоненты задержки критического класса",
    "useful_throughput_by_class_and_scenario": "Полезная пропускная способность по классам",
    "latency_distribution": "Распределение задержки по классам",
    "critical_latency_cdf": "CDF задержки critical",
    "queue_timeseries": "Длина очереди во времени",
    "deadline_met_ratio": "Доля сообщений в дедлайне",
    "latency_components": "Компоненты задержки",
    "throughput_by_class": "Пропускная способность по классам",
    "crypto_share": "Доля криптообработки в задержке",
}


def display_load(value: object) -> str:
    return LOAD_LABELS.get(str(value), str(value))


def display_class(value: object) -> str:
    return CLASS_LABELS.get(str(value), str(value))


def display_component(value: object) -> str:
    return COMPONENT_LABELS.get(str(value), str(value))


def display_outcome(value: object) -> str:
    return OUTCOME_LABELS.get(str(value), str(value))


def display_reason(value: object) -> str:
    return REASON_LABELS.get(str(value), str(value))


def display_scenario_load(value: str) -> str:
    if "|" not in value:
        return value
    scenario, load = value.split("|", 1)
    return f"{scenario}|{display_load(load)}"


def configure_plot_style() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 12,
            "axes.labelsize": 13,
            "axes.titlesize": 14,
            "legend.fontsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "figure.dpi": 250,
            "savefig.bbox": "tight",
        }
    )


def read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def read_optional_manifest(path: Path) -> List[Dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def ensure_context_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    enriched = df.copy()
    if "scenario_family" not in enriched.columns:
        if "scenario" in enriched.columns:
            enriched["scenario_family"] = enriched["scenario"].astype(str)
        else:
            enriched["scenario_family"] = "unknown"
    if "load_profile" not in enriched.columns:
        enriched["load_profile"] = "custom"
    enriched["scenario_family"] = enriched["scenario_family"].astype(str).fillna("unknown")
    enriched["load_profile"] = enriched["load_profile"].astype(str).fillna("custom")
    return enriched


def try_convert_numeric(df: pd.DataFrame, skip_columns: Iterable[str]) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    converted = df.copy()
    skip = set(skip_columns)
    for column in converted.columns:
        if column in skip:
            continue
        numeric = pd.to_numeric(converted[column], errors="coerce")
        if numeric.notna().any():
            converted[column] = numeric
    return converted.copy()


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(TRUE_VALUES)


def ordered_values(values: Iterable[object], preferred: List[str]) -> List[str]:
    value_set = {str(value) for value in values if str(value).strip()}
    prioritized = [value for value in preferred if value in value_set]
    extras = sorted(value_set - set(preferred))
    return prioritized + extras


def save_figure(
    fig,
    out_dir: Path,
    stem: str,
    title: str,
    artifacts: List[Dict[str, str]],
    source: str = "extended",
) -> None:
    png_path = out_dir / f"{stem}.png"
    fig.tight_layout()
    fig.savefig(png_path, dpi=250)
    plt.close(fig)
    artifacts.append(
        {
            "source": source,
            "title": title,
            "png": png_path.name,
        }
    )


def barplot_with_ci(
    *,
    data: pd.DataFrame,
    x: str,
    y: str,
    hue: str,
    order: List[str],
    hue_order: List[str],
    capsize: float,
    linewidth: float,
    ax,
    palette: str | None = None,
) -> None:
    common_kwargs = {
        "data": data,
        "x": x,
        "y": y,
        "hue": hue,
        "order": order,
        "hue_order": hue_order,
        "capsize": capsize,
        "ax": ax,
    }
    if palette:
        common_kwargs["palette"] = palette

    try:
        sns.barplot(
            **common_kwargs,
            errorbar=("ci", 95),
            err_kws={"linewidth": linewidth},
        )
    except TypeError:
        sns.barplot(
            **common_kwargs,
            ci=95,
            errwidth=linewidth,
        )


def aggregate_runs_by_context(runs: pd.DataFrame) -> pd.DataFrame:
    if runs.empty or "scenario_family" not in runs.columns or "load_profile" not in runs.columns:
        return pd.DataFrame()

    numeric_columns = runs.select_dtypes(include="number").columns.tolist()
    if not numeric_columns:
        return pd.DataFrame()

    grouped = (
        runs.groupby(["scenario_family", "load_profile"], as_index=False)[numeric_columns]
        .mean()
        .reset_index(drop=True)
    )

    scenario_order = ordered_values(grouped["scenario_family"], SCENARIO_ORDER)
    load_order = ordered_values(grouped["load_profile"], LOAD_ORDER)
    grouped["scenario_family"] = pd.Categorical(grouped["scenario_family"], categories=scenario_order, ordered=True)
    grouped["load_profile"] = pd.Categorical(grouped["load_profile"], categories=load_order, ordered=True)
    grouped = grouped.sort_values(["load_profile", "scenario_family"]).reset_index(drop=True)
    return grouped


def add_metric_bar_plots(runs: pd.DataFrame, out_dir: Path, artifacts: List[Dict[str, str]]) -> None:
    metric_specs = [
        (
            "critical_latency_mean_s",
            "extended_critical_latency_mean",
            "Средняя задержка критического класса по сценариям и нагрузкам",
            "Задержка, с",
            False,
        ),
        (
            "critical_latency_p95_s",
            "extended_critical_latency_p95",
            "95-й процентиль задержки критического класса",
            "Задержка p95, с",
            False,
        ),
        (
            "critical_deadline_met_ratio",
            "extended_critical_deadline_met_ratio",
            "Доля сообщений критического класса, доставленных до дедлайна",
            "Доля, %",
            True,
        ),
        (
            "critical_jitter_s",
            "extended_critical_jitter",
            "Джиттер критического трафика",
            "Джиттер, с",
            False,
        ),
        (
            "crypto_utilization",
            "extended_crypto_utilization",
            "Утилизация криптомодуля",
            "Загрузка, %",
            True,
        ),
        (
            "channel_utilization",
            "extended_channel_utilization",
            "Утилизация канала",
            "Загрузка, %",
            True,
        ),
        (
            "average_queue_length",
            "extended_average_queue_length",
            "Средняя длина очереди",
            "Сообщений в очереди",
            False,
        ),
        (
            "background_dropped_ratio",
            "extended_background_dropped_ratio",
            "Доля потерь фонового класса",
            "Потери, %",
            True,
        ),
        (
            "retransmission_ratio",
            "extended_retransmission_ratio",
            "Доля ретрансляций",
            "Ретрансляции, %",
            True,
        ),
    ]

    for metric, stem, title, ylabel, as_percent in metric_specs:
        if metric not in runs.columns:
            continue
        plot_metric_bar(runs, metric, stem, title, ylabel, out_dir, artifacts, as_percent=as_percent)


def plot_metric_bar(
    runs: pd.DataFrame,
    value_column: str,
    stem: str,
    title: str,
    ylabel: str,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
    as_percent: bool,
) -> None:
    data = runs[["scenario_family", "load_profile", value_column]].copy()
    data[value_column] = pd.to_numeric(data[value_column], errors="coerce")
    data = data.dropna(subset=[value_column])
    if data.empty:
        return

    data["value"] = data[value_column] * 100.0 if as_percent else data[value_column]
    scenario_order = ordered_values(data["scenario_family"], SCENARIO_ORDER)
    load_order = ordered_values(data["load_profile"], LOAD_ORDER)
    load_order_display = [display_load(item) for item in load_order]
    data["load_profile_label"] = data["load_profile"].map(display_load)

    fig, ax = plt.subplots(figsize=(11, 6))
    barplot_with_ci(
        data=data,
        x="load_profile_label",
        y="value",
        hue="scenario_family",
        order=load_order_display,
        hue_order=scenario_order,
        palette="Set2",
        capsize=0.12,
        linewidth=1.2,
        ax=ax,
    )
    ax.set_title(title)
    ax.set_xlabel("Профиль нагрузки")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.legend(title="Сценарий")
    save_figure(fig, out_dir, stem, title, artifacts)


def add_critical_component_plot(
    grouped: pd.DataFrame,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
) -> None:
    component_specs = [
        ("critical_classification_time_mean_s", "classification"),
        ("critical_crypto_time_mean_s", "crypto"),
        ("critical_queue_time_mean_s", "queue"),
        ("critical_tx_time_mean_s", "tx"),
        ("critical_ack_time_mean_s", "ack"),
    ]
    available = [spec for spec in component_specs if spec[0] in grouped.columns]
    if grouped.empty or not available:
        return

    labels = [f"{display_load(row.load_profile)} | {row.scenario_family}" for row in grouped.itertuples(index=False)]
    bottoms = np.zeros(len(labels))
    fig, ax = plt.subplots(figsize=(13, 6))

    for column, label in available:
        values = pd.to_numeric(grouped[column], errors="coerce").fillna(0.0).to_numpy()
        ax.bar(labels, values, bottom=bottoms, label=display_component(label))
        bottoms = bottoms + values

    title = "Вклад компонентов в задержку критического класса"
    ax.set_title(title)
    ax.set_xlabel("Нагрузка и сценарий")
    ax.set_ylabel("Среднее время, с")
    ax.tick_params(axis="x", rotation=35)
    ax.legend(title="Компонент", loc="upper left", ncol=2)
    save_figure(fig, out_dir, "extended_critical_components_stack", title, artifacts)


def add_class_heatmaps(
    grouped: pd.DataFrame,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
) -> None:
    if grouped.empty:
        return

    heatmap_specs = [
        (
            "delivered_ratio",
            "extended_class_delivery_heatmap",
            "Доля доставки по классам и режимам",
            True,
            ".1f",
            "Доля доставки, %",
        ),
        (
            "useful_throughput_bps",
            "extended_class_useful_throughput_heatmap",
            "Полезная пропускная способность по классам",
            False,
            ".0f",
            "Полезная пропускная способность, бит/с",
        ),
        (
            "latency_mean_s",
            "extended_class_latency_heatmap",
            "Средняя задержка по классам",
            False,
            ".3f",
            "задержка, с",
        ),
    ]

    scenario_order = ordered_values(grouped["scenario_family"], SCENARIO_ORDER)
    load_order = ordered_values(grouped["load_profile"], LOAD_ORDER)

    for suffix, stem, title, as_percent, fmt, colorbar_label in heatmap_specs:
        records = []
        for row in grouped.itertuples(index=False):
            scenario = str(row.scenario_family)
            load = str(row.load_profile)
            for traffic_class in TRAFFIC_CLASSES:
                column = f"{traffic_class}_{suffix}"
                if column not in grouped.columns:
                    continue
                value = pd.to_numeric(pd.Series([getattr(row, column)]), errors="coerce").iloc[0]
                if pd.isna(value):
                    continue
                records.append(
                    {
                        "traffic_class": traffic_class,
                        "scenario_load": f"{scenario}|{load}",
                        "value": value * 100.0 if as_percent else float(value),
                    }
                )

        if not records:
            continue

        matrix = pd.DataFrame(records).pivot(index="traffic_class", columns="scenario_load", values="value")
        ordered_columns = [
            f"{scenario}|{load}"
            for load in load_order
            for scenario in scenario_order
            if f"{scenario}|{load}" in matrix.columns
        ]
        if not ordered_columns:
            continue

        matrix = matrix.reindex(index=[c for c in TRAFFIC_CLASSES if c in matrix.index], columns=ordered_columns)
        matrix.index = [display_class(item) for item in matrix.index]
        matrix.columns = [display_scenario_load(item) for item in matrix.columns]
        fig_width = max(9.0, 1.15 * len(matrix.columns))
        fig, ax = plt.subplots(figsize=(fig_width, 4.8))
        sns.heatmap(
            matrix,
            annot=True,
            fmt=fmt,
            linewidths=0.5,
            cmap="YlGnBu",
            cbar_kws={"label": colorbar_label},
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("Сценарий | Нагрузка")
        ax.set_ylabel("Класс трафика")
        save_figure(fig, out_dir, stem, title, artifacts)


def add_tradeoff_scatter_plots(
    grouped: pd.DataFrame,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
) -> None:
    if grouped.empty:
        return

    critical_required = {
        "critical_deadline_met_ratio",
        "critical_latency_mean_s",
        "crypto_utilization",
    }
    if critical_required.issubset(set(grouped.columns)):
        data = grouped[
            [
                "scenario_family",
                "load_profile",
                "critical_deadline_met_ratio",
                "critical_latency_mean_s",
                "crypto_utilization",
            ]
        ].copy()
        data = data.dropna()
        if not data.empty:
            data["critical_deadline_pct"] = data["critical_deadline_met_ratio"] * 100.0
            data["load_profile_label"] = data["load_profile"].map(display_load)
            data["label"] = data["scenario_family"].astype(str) + "|" + data["load_profile_label"].astype(str)

            fig, ax = plt.subplots(figsize=(10, 6))
            sns.scatterplot(
                data=data,
                x="critical_deadline_pct",
                y="critical_latency_mean_s",
                hue="scenario_family",
                style="load_profile_label",
                size="crypto_utilization",
                sizes=(90, 520),
                alpha=0.9,
                ax=ax,
            )
            for row in data.itertuples(index=False):
                ax.annotate(
                    row.label,
                    (row.critical_deadline_pct, row.critical_latency_mean_s),
                    textcoords="offset points",
                    xytext=(4, 4),
                    fontsize=8,
                )
            title = "Компромисс: дедлайн критического трафика и задержка"
            ax.set_title(title)
            ax.set_xlabel("Доля critical в дедлайне, %")
            ax.set_ylabel("Средняя задержка критического класса, с")
            ax.grid(linestyle="--", alpha=0.4)
            ax.legend(loc="best", fontsize=8)
            save_figure(fig, out_dir, "extended_critical_tradeoff_scatter", title, artifacts)

    background_required = {
        "critical_deadline_met_ratio",
        "background_dropped_ratio",
        "critical_latency_mean_s",
    }
    if background_required.issubset(set(grouped.columns)):
        data = grouped[
            [
                "scenario_family",
                "load_profile",
                "critical_deadline_met_ratio",
                "background_dropped_ratio",
                "critical_latency_mean_s",
            ]
        ].copy()
        data = data.dropna()
        if not data.empty:
            data["critical_deadline_pct"] = data["critical_deadline_met_ratio"] * 100.0
            data["background_drop_pct"] = data["background_dropped_ratio"] * 100.0
            data["load_profile_label"] = data["load_profile"].map(display_load)
            data["label"] = data["scenario_family"].astype(str) + "|" + data["load_profile_label"].astype(str)

            fig, ax = plt.subplots(figsize=(10, 6))
            sns.scatterplot(
                data=data,
                x="background_drop_pct",
                y="critical_deadline_pct",
                hue="scenario_family",
                style="load_profile_label",
                size="critical_latency_mean_s",
                sizes=(90, 520),
                alpha=0.9,
                ax=ax,
            )
            for row in data.itertuples(index=False):
                ax.annotate(
                    row.label,
                    (row.background_drop_pct, row.critical_deadline_pct),
                    textcoords="offset points",
                    xytext=(4, 4),
                    fontsize=8,
                )
            title = "Компромисс: потери фонового трафика и дедлайны критического класса"
            ax.set_title(title)
            ax.set_xlabel("Потери фонового класса, %")
            ax.set_ylabel("Доля критического класса в дедлайне, %")
            ax.grid(linestyle="--", alpha=0.4)
            ax.legend(loc="best", fontsize=8)
            save_figure(fig, out_dir, "extended_background_tradeoff_scatter", title, artifacts)


def add_message_level_plots(
    messages: pd.DataFrame,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
) -> None:
    if messages.empty:
        return

    data = ensure_context_columns(messages)
    data = try_convert_numeric(
        data,
        {
            "run_id",
            "base_run_id",
            "scenario",
            "scenario_family",
            "load_profile",
            "config_name",
            "message_id",
            "src",
            "dst",
            "message_class",
            "policy_version_id",
            "drop_reason",
            "lifecycle_events_json",
            "metadata_json",
            "delivered",
            "dropped",
            "deadline_missed",
        },
    )

    for bool_column in ("delivered", "dropped", "deadline_missed"):
        if bool_column in data.columns:
            data[bool_column] = to_bool(data[bool_column])

    if {"message_class", "total_latency_s"}.issubset(set(data.columns)):
        latency_data = data.copy()
        latency_data["total_latency_s"] = pd.to_numeric(latency_data["total_latency_s"], errors="coerce")
        latency_data = latency_data.dropna(subset=["total_latency_s"])
        if "delivered" in latency_data.columns:
            latency_data = latency_data[latency_data["delivered"]]

        critical = latency_data[latency_data["message_class"] == "critical"]
        if not critical.empty and "scenario_family" in critical.columns:
            scenario_order = ordered_values(critical["scenario_family"], SCENARIO_ORDER)
            fig, ax = plt.subplots(figsize=(10, 6))
            for scenario in scenario_order:
                values = np.sort(critical.loc[critical["scenario_family"] == scenario, "total_latency_s"].to_numpy())
                if values.size == 0:
                    continue
                cdf = np.arange(1, values.size + 1) / float(values.size)
                ax.plot(values, cdf, label=scenario)
            title = "CDF задержки сообщений критического класса"
            ax.set_title(title)
            ax.set_xlabel("Задержка, с")
            ax.set_ylabel("Функция распределения (CDF)")
            ax.grid(linestyle="--", alpha=0.4)
            ax.legend(title="Сценарий")
            save_figure(fig, out_dir, "extended_critical_latency_cdf", title, artifacts)

        class_subset = latency_data[latency_data["message_class"].isin(TRAFFIC_CLASSES)]
        if not class_subset.empty:
            class_subset = class_subset.copy()
            class_subset["message_class_label"] = class_subset["message_class"].map(display_class)
            scenario_order = ordered_values(class_subset["scenario_family"], SCENARIO_ORDER)
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.boxplot(
                data=class_subset,
                x="message_class_label",
                y="total_latency_s",
                hue="scenario_family",
                hue_order=scenario_order,
                showfliers=False,
                ax=ax,
            )
            title = "Распределение задержки по классам (доставленные)"
            ax.set_title(title)
            ax.set_xlabel("Класс")
            ax.set_ylabel("Задержка, с")
            ax.legend(title="Сценарий")
            save_figure(fig, out_dir, "extended_latency_box_by_class", title, artifacts)

    if {"message_class", "payload_bytes", "total_latency_s"}.issubset(set(data.columns)):
        scatter_data = data.copy()
        scatter_data["payload_bytes"] = pd.to_numeric(scatter_data["payload_bytes"], errors="coerce")
        scatter_data["total_latency_s"] = pd.to_numeric(scatter_data["total_latency_s"], errors="coerce")
        scatter_data = scatter_data.dropna(subset=["payload_bytes", "total_latency_s"])
        scatter_data = scatter_data[scatter_data["message_class"].isin(TRAFFIC_CLASSES)]
        if "delivered" in scatter_data.columns:
            scatter_data = scatter_data[scatter_data["delivered"]]
        scatter_data = scatter_data.copy()
        scatter_data["message_class_label"] = scatter_data["message_class"].map(display_class)
        if len(scatter_data) > 6000:
            scatter_data = scatter_data.sample(6000, random_state=42)
        if not scatter_data.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.scatterplot(
                data=scatter_data,
                x="payload_bytes",
                y="total_latency_s",
                hue="message_class_label",
                alpha=0.45,
                s=22,
                ax=ax,
            )
            title = "Связь размера полезной нагрузки и задержки"
            ax.set_title(title)
            ax.set_xlabel("Полезная нагрузка, байт")
            ax.set_ylabel("Задержка, с")
            ax.grid(linestyle="--", alpha=0.35)
            save_figure(fig, out_dir, "extended_payload_vs_latency", title, artifacts)

    if {"message_class", "delivered", "dropped", "deadline_missed"}.issubset(set(data.columns)):
        outcome = data[data["message_class"].isin(TRAFFIC_CLASSES)].copy()
        outcome["outcome"] = "other"
        outcome.loc[outcome["dropped"], "outcome"] = "dropped"
        outcome.loc[(~outcome["dropped"]) & outcome["delivered"] & outcome["deadline_missed"], "outcome"] = "deadline_missed"
        outcome.loc[(~outcome["dropped"]) & outcome["delivered"] & (~outcome["deadline_missed"]), "outcome"] = "on_time"
        outcome = outcome[outcome["outcome"].isin(["on_time", "deadline_missed", "dropped"])]

        if not outcome.empty:
            ratio_table = outcome.groupby(["message_class", "outcome"]).size().unstack(fill_value=0)
            ratio_table = ratio_table.div(ratio_table.sum(axis=1), axis=0).fillna(0.0)
            ratio_table = ratio_table.reindex(index=[c for c in TRAFFIC_CLASSES if c in ratio_table.index], fill_value=0.0)
            ratio_table.index = [display_class(item) for item in ratio_table.index]

            fig, ax = plt.subplots(figsize=(10, 6))
            x = np.arange(len(ratio_table.index))
            bottom = np.zeros(len(ratio_table.index))
            ordered_outcomes = ["on_time", "deadline_missed", "dropped"]
            colors = {
                "on_time": "#2ca02c",
                "deadline_missed": "#ff7f0e",
                "dropped": "#d62728",
            }
            for column in ordered_outcomes:
                if column not in ratio_table.columns:
                    continue
                values = ratio_table[column].to_numpy()
                ax.bar(x, values, bottom=bottom, label=display_outcome(column), color=colors.get(column))
                bottom = bottom + values

            title = "Исходы сообщений по классам"
            ax.set_title(title)
            ax.set_xticks(x)
            ax.set_xticklabels(ratio_table.index)
            ax.set_ylim(0, 1.02)
            ax.set_ylabel("Доля")
            ax.legend(title="Исход")
            save_figure(fig, out_dir, "extended_deadline_outcomes_by_class", title, artifacts)


def add_queue_plots(
    queue: pd.DataFrame,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
) -> None:
    if queue.empty:
        return

    data = ensure_context_columns(queue)
    required = {"run_id", "time_s", "queue_total", "scenario_family", "load_profile"}
    if not required.issubset(set(data.columns)):
        return

    data["time_s"] = pd.to_numeric(data["time_s"], errors="coerce")
    data["queue_total"] = pd.to_numeric(data["queue_total"], errors="coerce")
    data = data.dropna(subset=["time_s", "queue_total"])
    if data.empty:
        return

    max_time = float(data["time_s"].max())
    bucket = max(max_time / 140.0, 0.1)
    bucket = round(bucket, 3)
    data["time_bucket"] = (data["time_s"] / bucket).round() * bucket

    grouped = (
        data.groupby(["load_profile", "scenario_family", "time_bucket"], as_index=False)["queue_total"]
        .mean()
        .sort_values("time_bucket")
    )

    load_order = ordered_values(grouped["load_profile"], LOAD_ORDER)
    scenario_order = ordered_values(grouped["scenario_family"], SCENARIO_ORDER)
    if not load_order or not scenario_order:
        return

    cols = 2
    rows = int(math.ceil(len(load_order) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(14, max(4.5, rows * 3.6)), sharey=True)
    flat_axes = np.array(axes).reshape(-1)

    for index, load in enumerate(load_order):
        ax = flat_axes[index]
        subset = grouped[grouped["load_profile"] == load]
        for scenario in scenario_order:
            line = subset[subset["scenario_family"] == scenario]
            if line.empty:
                continue
            ax.plot(line["time_bucket"], line["queue_total"], label=scenario)
        ax.set_title(f"Нагрузка={display_load(load)}")
        ax.set_xlabel("Время, с")
        ax.set_ylabel("Средняя очередь")
        ax.grid(linestyle="--", alpha=0.4)

    for index in range(len(load_order), len(flat_axes)):
        flat_axes[index].axis("off")

    handles, labels = flat_axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, title="Сценарий", loc="upper right")

    title = "Динамика длины очереди (mean по run и времени)"
    fig.suptitle(title, fontsize=14)
    save_figure(fig, out_dir, "extended_queue_timeseries", title, artifacts)

    per_run_peak = data.groupby(["scenario_family", "load_profile", "run_id"], as_index=False)["queue_total"].max()
    if not per_run_peak.empty:
        peak_mean = (
            per_run_peak.groupby(["scenario_family", "load_profile"], as_index=False)["queue_total"]
            .mean()
            .rename(columns={"queue_total": "mean_peak_queue"})
        )
        matrix = peak_mean.pivot(index="scenario_family", columns="load_profile", values="mean_peak_queue")
        matrix = matrix.reindex(
            index=ordered_values(matrix.index, SCENARIO_ORDER),
            columns=ordered_values(matrix.columns, LOAD_ORDER),
        )
        fig, ax = plt.subplots(figsize=(8.6, 4.8))
        sns.heatmap(
            matrix,
            annot=True,
            fmt=".2f",
            cmap="YlOrRd",
            linewidths=0.5,
                cbar_kws={"label": "Пик очереди"},
            ax=ax,
        )
        title = "Средний пиковый размер очереди"
        ax.set_title(title)
        ax.set_xlabel("Профиль нагрузки")
        ax.set_ylabel("Сценарий")
        save_figure(fig, out_dir, "extended_queue_peak_heatmap", title, artifacts)


def add_resource_plots(
    resources: pd.DataFrame,
    runs: pd.DataFrame,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
) -> None:
    if resources.empty:
        return

    data = ensure_context_columns(resources)
    required = {"run_id", "resource", "duration_s", "scenario_family", "load_profile"}
    if not required.issubset(set(data.columns)):
        return

    data["resource"] = data["resource"].astype(str)
    data["duration_s"] = pd.to_numeric(data["duration_s"], errors="coerce")
    data = data.dropna(subset=["duration_s"])
    crypto = data[data["resource"].str.lower() == "crypto"].copy()
    if crypto.empty:
        return

    scenario_order = ordered_values(crypto["scenario_family"], SCENARIO_ORDER)
    load_order = ordered_values(crypto["load_profile"], LOAD_ORDER)
    load_order_display = [display_load(item) for item in load_order]
    crypto["load_profile_label"] = crypto["load_profile"].map(display_load)

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.boxplot(
        data=crypto,
        x="load_profile_label",
        y="duration_s",
        hue="scenario_family",
        order=load_order_display,
        hue_order=scenario_order,
        showfliers=False,
        ax=ax,
    )
    title = "Распределение длительностей операций криптомодуля"
    ax.set_title(title)
    ax.set_xlabel("Профиль нагрузки")
    ax.set_ylabel("Длительность операции, с")
    ax.legend(title="Сценарий")
    save_figure(fig, out_dir, "extended_crypto_busy_duration_box", title, artifacts)

    if {"run_id", "observation_window_s", "scenario_family", "load_profile"}.issubset(set(runs.columns)):
        window_col = "observation_window_s"
    elif {"run_id", "duration_s", "scenario_family", "load_profile"}.issubset(set(runs.columns)):
        window_col = "duration_s"
    else:
        window_col = ""

    if window_col:
        busy = (
            crypto.groupby(["run_id", "scenario_family", "load_profile"], as_index=False)["duration_s"]
            .sum()
            .rename(columns={"duration_s": "crypto_busy_s"})
        )
        windows = runs[["run_id", "scenario_family", "load_profile", window_col]].copy()
        windows[window_col] = pd.to_numeric(windows[window_col], errors="coerce")
        merged = busy.merge(windows, on=["run_id", "scenario_family", "load_profile"], how="left")
        merged = merged.dropna(subset=[window_col])
        merged = merged[merged[window_col] > 0]
        if not merged.empty:
            merged["busy_share"] = merged["crypto_busy_s"] / merged[window_col]
            summary = (
                merged.groupby(["scenario_family", "load_profile"], as_index=False)["busy_share"]
                .mean()
                .rename(columns={"busy_share": "crypto_busy_share"})
            )
            matrix = summary.pivot(index="scenario_family", columns="load_profile", values="crypto_busy_share")
            matrix = matrix.reindex(
                index=ordered_values(matrix.index, SCENARIO_ORDER),
                columns=ordered_values(matrix.columns, LOAD_ORDER),
            )
            matrix.columns = [display_load(item) for item in matrix.columns]
            fig, ax = plt.subplots(figsize=(8.8, 4.8))
            sns.heatmap(
                matrix * 100.0,
                annot=True,
                fmt=".1f",
                cmap="PuBuGn",
                linewidths=0.5,
                cbar_kws={"label": "Занятость криптомодуля, %"},
                ax=ax,
            )
            title = "Доля занятости криптомодуля по режимам"
            ax.set_title(title)
            ax.set_xlabel("Профиль нагрузки")
            ax.set_ylabel("Сценарий")
            save_figure(fig, out_dir, "extended_crypto_busy_share_heatmap", title, artifacts)


def add_policy_plots(
    policy_events: pd.DataFrame,
    out_dir: Path,
    artifacts: List[Dict[str, str]],
) -> None:
    if policy_events.empty:
        return

    data = ensure_context_columns(policy_events)
    if not {"run_id", "event", "scenario_family", "load_profile"}.issubset(set(data.columns)):
        return

    switches = data[data["event"].astype(str) == "policy_switch"].copy()
    if switches.empty:
        return

    switch_counts = (
        switches.groupby(["run_id", "scenario_family", "load_profile"], as_index=False)
        .size()
        .rename(columns={"size": "switch_count"})
    )
    scenario_order = ordered_values(switch_counts["scenario_family"], SCENARIO_ORDER)
    load_order = ordered_values(switch_counts["load_profile"], LOAD_ORDER)
    load_order_display = [display_load(item) for item in load_order]
    switch_counts["load_profile_label"] = switch_counts["load_profile"].map(display_load)

    fig, ax = plt.subplots(figsize=(11, 6))
    barplot_with_ci(
        data=switch_counts,
        x="load_profile_label",
        y="switch_count",
        hue="scenario_family",
        order=load_order_display,
        hue_order=scenario_order,
        palette="Set2",
        capsize=0.12,
        linewidth=1.1,
        ax=ax,
    )
    title = "Среднее число переключений политики на запуск"
    ax.set_title(title)
    ax.set_xlabel("Профиль нагрузки")
    ax.set_ylabel("Переключений политики / запуск")
    ax.legend(title="Сценарий")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    save_figure(fig, out_dir, "extended_policy_switches", title, artifacts)

    if "reason" in switches.columns:
        switches["reason"] = switches["reason"].astype(str).replace("", "unspecified")
        reason_table = switches.groupby(["scenario_family", "reason"]).size().unstack(fill_value=0)
        if not reason_table.empty:
            top_reasons = reason_table.sum(axis=0).sort_values(ascending=False).head(8).index.tolist()
            reason_table = reason_table[top_reasons]
            ratio = reason_table.div(reason_table.sum(axis=1), axis=0).fillna(0.0)
            ratio = ratio.reindex(index=ordered_values(ratio.index, SCENARIO_ORDER), fill_value=0.0)

            fig, ax = plt.subplots(figsize=(10, 6))
            x = np.arange(len(ratio.index))
            bottom = np.zeros(len(ratio.index))
            colors = plt.cm.tab20(np.linspace(0, 1, max(1, len(ratio.columns))))
            for idx, column in enumerate(ratio.columns):
                values = ratio[column].to_numpy()
                ax.bar(x, values, bottom=bottom, label=display_reason(column), color=colors[idx])
                bottom = bottom + values

            title = "Причины переключения политики по сценариям"
            ax.set_title(title)
            ax.set_xticks(x)
            ax.set_xticklabels(ratio.index)
            ax.set_ylim(0, 1.02)
            ax.set_ylabel("Доля")
            ax.set_xlabel("Сценарий")
            ax.legend(title="Причина", bbox_to_anchor=(1.01, 1.0), loc="upper left")
            save_figure(fig, out_dir, "extended_policy_reason_distribution", title, artifacts)


def format_float(value: object, digits: int = 4) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "n/a"
    return f"{float(numeric):.{digits}f}"


def format_percent(value: object, digits: int = 2) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "n/a"
    return f"{float(numeric) * 100.0:.{digits}f}%"


def markdown_table(headers: List[str], rows: List[List[str]]) -> List[str]:
    if not rows:
        return ["_Нет данных для таблицы._"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def pick_extreme(grouped: pd.DataFrame, column: str, higher_is_better: bool) -> pd.Series | None:
    if grouped.empty or column not in grouped.columns:
        return None
    values = pd.to_numeric(grouped[column], errors="coerce")
    if values.notna().sum() == 0:
        return None
    index = values.idxmax() if higher_is_better else values.idxmin()
    if pd.isna(index):
        return None
    return grouped.loc[index]


def build_scenario_delta_rows(grouped: pd.DataFrame) -> List[List[str]]:
    if grouped.empty:
        return []

    keyed = {
        (str(row.scenario_family), str(row.load_profile)): row
        for row in grouped.itertuples(index=False)
    }
    rows: List[List[str]] = []
    for load in ordered_values(grouped["load_profile"], LOAD_ORDER):
        for lhs, rhs in (("C", "A"), ("C", "B"), ("B", "A")):
            lhs_row = keyed.get((lhs, load))
            rhs_row = keyed.get((rhs, load))
            if lhs_row is None or rhs_row is None:
                continue

            lhs_deadline = float(getattr(lhs_row, "critical_deadline_met_ratio", np.nan))
            rhs_deadline = float(getattr(rhs_row, "critical_deadline_met_ratio", np.nan))
            lhs_latency = float(getattr(lhs_row, "critical_latency_mean_s", np.nan))
            rhs_latency = float(getattr(rhs_row, "critical_latency_mean_s", np.nan))
            lhs_bg_drop = float(getattr(lhs_row, "background_dropped_ratio", np.nan))
            rhs_bg_drop = float(getattr(rhs_row, "background_dropped_ratio", np.nan))

            if any(np.isnan(item) for item in [lhs_deadline, rhs_deadline, lhs_latency, rhs_latency, lhs_bg_drop, rhs_bg_drop]):
                continue

            rows.append(
                [
                    load,
                    f"{lhs}-{rhs}",
                    f"{(lhs_deadline - rhs_deadline) * 100.0:.2f} п.п.",
                    f"{lhs_latency - rhs_latency:.4f}",
                    f"{(rhs_latency - lhs_latency) / rhs_latency * 100.0:.2f}%" if rhs_latency > 0 else "n/a",
                    f"{(lhs_bg_drop - rhs_bg_drop) * 100.0:.2f} п.п.",
                ]
            )
    return rows


def generate_markdown_report(
    report_path: Path,
    title: str,
    input_root: Path,
    out_dir: Path,
    runs: pd.DataFrame,
    grouped: pd.DataFrame,
    messages: pd.DataFrame,
    queue: pd.DataFrame,
    resources: pd.DataFrame,
    policy_events: pd.DataFrame,
    manifest: List[Dict[str, object]],
    artifacts: List[Dict[str, str]],
    core_plot_count: int,
    extended_plot_count: int,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scenarios = ordered_values(runs.get("scenario_family", pd.Series(dtype=object)), SCENARIO_ORDER)
    loads = ordered_values(runs.get("load_profile", pd.Series(dtype=object)), LOAD_ORDER)

    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Сформирован: {now}")
    lines.append(f"Каталог данных: {input_root}")
    lines.append(f"Каталог графиков: {out_dir}")
    lines.append("")

    lines.append("## Охват эксперимента")
    lines.append("")
    lines.append(f"- Запусков (run_id): {runs['run_id'].nunique() if 'run_id' in runs.columns else len(runs)}")
    lines.append(f"- Строк в batch_runs.csv: {len(runs)}")
    lines.append(f"- Строк в batch_messages.csv: {len(messages)}")
    lines.append(f"- Строк в batch_queue_timeseries.csv: {len(queue)}")
    lines.append(f"- Строк в batch_resource_usage.csv: {len(resources)}")
    lines.append(f"- Строк в batch_policy_events.csv: {len(policy_events)}")
    lines.append(f"- Сценарии: {', '.join(scenarios) if scenarios else 'n/a'}")
    lines.append(f"- Профили нагрузки: {', '.join(loads) if loads else 'n/a'}")
    if "seed" in runs.columns:
        lines.append(f"- Количество seed: {runs['seed'].nunique()}")
    if "replicate_index" in runs.columns:
        max_rep = pd.to_numeric(runs["replicate_index"], errors="coerce").max()
        if pd.notna(max_rep):
            lines.append(f"- Реплик на конфигурацию (оценка): {int(max_rep) + 1}")
    if manifest:
        config_names = sorted(
            {
                Path(str(item.get("config", ""))).name
                for item in manifest
                if isinstance(item, dict) and item.get("config")
            }
        )
        if config_names:
            lines.append(f"- Конфигураций из batch_manifest: {len(config_names)}")
    lines.append("")

    lines.append("## Автоматические highlights")
    lines.append("")
    highlights = [
        ("critical_deadline_met_ratio", "Максимальная доля critical в дедлайне", True, True),
        ("critical_latency_mean_s", "Минимальная средняя задержка critical", False, False),
        ("critical_latency_p95_s", "Минимальный p95 задержки critical", False, False),
        ("critical_jitter_s", "Минимальный джиттер critical", False, False),
        ("background_dropped_ratio", "Минимальные потери background", False, True),
        ("crypto_utilization", "Пиковая загрузка криптомодуля", True, True),
    ]
    any_highlight = False
    for column, label, higher_is_better, as_percent in highlights:
        row = pick_extreme(grouped, column, higher_is_better)
        if row is None:
            continue
        scenario = str(row["scenario_family"])
        load = str(row["load_profile"])
        value = format_percent(row[column]) if as_percent else format_float(row[column], digits=4)
        lines.append(f"- {label}: {value} (сценарий={scenario}, нагрузка={load}).")
        any_highlight = True
    if not any_highlight:
        lines.append("- Недостаточно данных для автоматических highlights.")
    lines.append("")

    lines.append("## KPI по профилям нагрузки")
    lines.append("")
    per_load_rows: List[List[str]] = []
    for load in loads:
        subset = grouped[grouped["load_profile"].astype(str) == load]
        if subset.empty:
            continue

        best_deadline = pick_extreme(subset, "critical_deadline_met_ratio", True)
        best_latency = pick_extreme(subset, "critical_latency_mean_s", False)
        best_background = pick_extreme(subset, "background_dropped_ratio", False)

        per_load_rows.append(
            [
                load,
                str(best_deadline["scenario_family"]) if best_deadline is not None else "n/a",
                format_percent(best_deadline["critical_deadline_met_ratio"]) if best_deadline is not None else "n/a",
                str(best_latency["scenario_family"]) if best_latency is not None else "n/a",
                format_float(best_latency["critical_latency_mean_s"]) if best_latency is not None else "n/a",
                str(best_background["scenario_family"]) if best_background is not None else "n/a",
                format_percent(best_background["background_dropped_ratio"]) if best_background is not None else "n/a",
            ]
        )

    lines.extend(
        markdown_table(
            [
                "Нагрузка",
                "Лидер по дедлайну",
                "critical deadline met",
                "Лидер по задержке",
                "critical latency mean, c",
                "Минимум background drop",
                "background dropped",
            ],
            per_load_rows,
        )
    )
    lines.append("")

    lines.append("## Дельты между сценариями")
    lines.append("")
    lines.extend(
        markdown_table(
            [
                "Нагрузка",
                "Пара",
                "Delta deadline",
                "Delta latency mean, c",
                "Улучшение latency",
                "Delta background drop",
            ],
            build_scenario_delta_rows(grouped),
        )
    )
    lines.append("")

    lines.append("## Сводка по классам трафика")
    lines.append("")
    class_rows: List[List[str]] = []
    for traffic_class in TRAFFIC_CLASSES:
        delivered_col = f"{traffic_class}_delivered_ratio"
        deadline_col = f"{traffic_class}_deadline_met_ratio"
        latency_col = f"{traffic_class}_latency_mean_s"
        throughput_col = f"{traffic_class}_useful_throughput_bps"
        if not any(column in grouped.columns for column in [delivered_col, deadline_col, latency_col, throughput_col]):
            continue
        class_rows.append(
            [
                traffic_class,
                format_percent(grouped[delivered_col].mean()) if delivered_col in grouped.columns else "n/a",
                format_percent(grouped[deadline_col].mean()) if deadline_col in grouped.columns else "n/a",
                format_float(grouped[latency_col].mean()) if latency_col in grouped.columns else "n/a",
                format_float(grouped[throughput_col].mean(), digits=1) if throughput_col in grouped.columns else "n/a",
            ]
        )

    lines.extend(
        markdown_table(
            ["Класс", "Delivered", "Deadline met", "Latency mean, c", "Useful throughput, bps"],
            class_rows,
        )
    )
    lines.append("")

    lines.append("## Очереди и ресурсы")
    lines.append("")
    queue_rows: List[List[str]] = []
    if not queue.empty and {"run_id", "scenario_family", "load_profile", "queue_total"}.issubset(set(queue.columns)):
        queue_data = ensure_context_columns(queue)
        queue_data["queue_total"] = pd.to_numeric(queue_data["queue_total"], errors="coerce")
        queue_data = queue_data.dropna(subset=["queue_total"])
        if not queue_data.empty:
            per_run = (
                queue_data.groupby(["run_id", "scenario_family", "load_profile"], as_index=False)["queue_total"]
                .max()
                .rename(columns={"queue_total": "peak_queue"})
            )
            summary = per_run.groupby(["scenario_family", "load_profile"], as_index=False).agg(
                mean_peak_queue=("peak_queue", "mean"),
                max_peak_queue=("peak_queue", "max"),
            )
            for row in summary.itertuples(index=False):
                queue_rows.append(
                    [
                        str(row.scenario_family),
                        str(row.load_profile),
                        format_float(row.mean_peak_queue, digits=2),
                        format_float(row.max_peak_queue, digits=2),
                    ]
                )
    lines.extend(markdown_table(["Сценарий", "Нагрузка", "Mean peak queue", "Max peak queue"], queue_rows))
    lines.append("")

    resource_rows: List[List[str]] = []
    if not resources.empty and {"resource", "scenario_family", "load_profile", "duration_s"}.issubset(set(resources.columns)):
        resource_data = ensure_context_columns(resources)
        resource_data["duration_s"] = pd.to_numeric(resource_data["duration_s"], errors="coerce")
        resource_data = resource_data.dropna(subset=["duration_s"])
        crypto = resource_data[resource_data["resource"].astype(str).str.lower() == "crypto"]
        if not crypto.empty:
            summary = crypto.groupby(["scenario_family", "load_profile"], as_index=False).agg(
                total_busy_s=("duration_s", "sum"),
                mean_interval_s=("duration_s", "mean"),
                intervals=("duration_s", "count"),
            )
            for row in summary.itertuples(index=False):
                resource_rows.append(
                    [
                        str(row.scenario_family),
                        str(row.load_profile),
                        format_float(row.total_busy_s, digits=2),
                        format_float(row.mean_interval_s, digits=4),
                        str(int(row.intervals)),
                    ]
                )
    lines.extend(markdown_table(["Сценарий", "Нагрузка", "Crypto busy sum, c", "Mean op duration, c", "Intervals"], resource_rows))
    lines.append("")

    lines.append("## Политики")
    lines.append("")
    policy_rows: List[List[str]] = []
    reason_rows: List[List[str]] = []
    if not policy_events.empty and {"run_id", "scenario_family", "load_profile", "event"}.issubset(set(policy_events.columns)):
        policy_data = ensure_context_columns(policy_events)
        switches = policy_data[policy_data["event"].astype(str) == "policy_switch"]
        if not switches.empty:
            switch_counts = (
                switches.groupby(["run_id", "scenario_family", "load_profile"], as_index=False)
                .size()
                .rename(columns={"size": "switch_count"})
            )
            switch_summary = switch_counts.groupby(["scenario_family", "load_profile"], as_index=False)["switch_count"].mean()
            for row in switch_summary.itertuples(index=False):
                policy_rows.append(
                    [
                        str(row.scenario_family),
                        str(row.load_profile),
                        format_float(row.switch_count, digits=2),
                    ]
                )

            if "reason" in switches.columns:
                reason_summary = (
                    switches.assign(reason=switches["reason"].astype(str).replace("", "unspecified"))
                    .groupby(["scenario_family", "reason"], as_index=False)
                    .size()
                    .rename(columns={"size": "count"})
                    .sort_values("count", ascending=False)
                )
                for row in reason_summary.head(12).itertuples(index=False):
                    reason_rows.append([str(row.scenario_family), str(row.reason), str(int(row.count))])

    lines.extend(markdown_table(["Сценарий", "Нагрузка", "Policy switch / run"], policy_rows))
    lines.append("")
    lines.extend(markdown_table(["Сценарий", "Причина switch", "Событий"], reason_rows))
    lines.append("")

    lines.append("## Сгенерированные графики")
    lines.append("")
    lines.append(f"- Базовые графики (core build-plots): {core_plot_count}")
    lines.append(f"- Расширенные графики: {extended_plot_count}")
    lines.append(f"- Всего графиков: {len(artifacts)}")
    lines.append("")
    artifact_rows = [
        [artifact.get("source", "n/a"), artifact.get("title", "n/a"), artifact.get("png", "n/a")]
        for artifact in artifacts
    ]
    lines.extend(markdown_table(["Источник", "Описание", "PNG"], artifact_rows))
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Расширенная визуализация результатов secure-delivery batch")
    parser.add_argument("--input", required=True, help="Путь к batch_runs.csv")
    parser.add_argument("--outdir", required=True, help="Директория для сохранения графиков и отчета")
    parser.add_argument(
        "--input-root",
        default="",
        help="Корень batch-результатов (если не указан, берется директория input-файла)",
    )
    parser.add_argument(
        "--report-name",
        default="experiment_report.md",
        help="Имя markdown-отчета внутри outdir",
    )
    parser.add_argument(
        "--title",
        default="Отчет по экспериментам приоритетной защищенной доставки",
        help="Заголовок markdown-отчета",
    )
    parser.add_argument(
        "--skip-core-plots",
        action="store_true",
        help="Не вызывать встроенный secure_delivery build-plots",
    )

    args = parser.parse_args()
    input_file = Path(args.input)
    if not input_file.exists():
        raise SystemExit(f"Ошибка: файл {input_file} не найден")

    input_root = Path(args.input_root) if args.input_root else input_file.parent
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    configure_plot_style()

    runs = ensure_context_columns(read_optional_csv(input_file))
    if runs.empty:
        raise SystemExit(f"Ошибка: {input_file} пустой или не содержит данных")

    runs = try_convert_numeric(
        runs,
        {
            "run_id",
            "base_run_id",
            "scenario",
            "scenario_family",
            "load_profile",
            "config_name",
        },
    )

    messages = ensure_context_columns(read_optional_csv(input_root / "batch_messages.csv"))
    queue = ensure_context_columns(read_optional_csv(input_root / "batch_queue_timeseries.csv"))
    resources = ensure_context_columns(read_optional_csv(input_root / "batch_resource_usage.csv"))
    policy_events = ensure_context_columns(read_optional_csv(input_root / "batch_policy_events.csv"))
    manifest = read_optional_manifest(input_root / "batch_manifest.json")

    artifacts: List[Dict[str, str]] = []
    core_plot_count = 0
    if not args.skip_core_plots:
        try:
            core_plots = build_core_plots(str(input_root), str(out_dir))
            for key, png_path in sorted(core_plots.items()):
                png_name = Path(png_path).name
                artifacts.append(
                    {
                        "source": "core",
                        "title": CORE_PLOT_TITLES.get(key, key.replace("_", " ")),
                        "png": png_name,
                    }
                )
            core_plot_count = len(core_plots)
            print(f"Сгенерированы core-графики: {core_plot_count}")
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Предупреждение: не удалось построить core-графики: {exc}")

    grouped = aggregate_runs_by_context(runs)
    before_extended = len(artifacts)
    add_metric_bar_plots(runs, out_dir, artifacts)
    add_critical_component_plot(grouped, out_dir, artifacts)
    add_class_heatmaps(grouped, out_dir, artifacts)
    add_tradeoff_scatter_plots(grouped, out_dir, artifacts)
    add_message_level_plots(messages, out_dir, artifacts)
    add_queue_plots(queue, out_dir, artifacts)
    add_resource_plots(resources, runs, out_dir, artifacts)
    add_policy_plots(policy_events, out_dir, artifacts)
    extended_plot_count = len(artifacts) - before_extended

    report_path = out_dir / args.report_name
    generate_markdown_report(
        report_path=report_path,
        title=args.title,
        input_root=input_root,
        out_dir=out_dir,
        runs=runs,
        grouped=grouped,
        messages=messages,
        queue=queue,
        resources=resources,
        policy_events=policy_events,
        manifest=manifest,
        artifacts=artifacts,
        core_plot_count=core_plot_count,
        extended_plot_count=extended_plot_count,
    )

    print("Готово.")
    print(f"Всего графиков: {len(artifacts)}")
    print(f"Core-графиков: {core_plot_count}")
    print(f"Расширенных графиков: {extended_plot_count}")
    print(f"Отчет: {report_path}")

if __name__ == "__main__":
    main()
