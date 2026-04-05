from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from secure_delivery.models.enums import MESSAGE_CLASS_ORDER
from secure_delivery.models.message import SecureMessage


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    index = (len(values_sorted) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values_sorted[lower]
    fraction = index - lower
    return values_sorted[lower] + fraction * (values_sorted[upper] - values_sorted[lower])


def _jitter(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return 0.0 if values else None
    diffs = [abs(values[index] - values[index - 1]) for index in range(1, len(values))]
    return statistics.mean(diffs)


class MetricsCollector:
    def __init__(
        self,
        run_id: str,
        scenario: str,
        scenario_family: str,
        load_profile: str,
        seed: int,
        duration_s: float,
        config_name: str = "",
    ) -> None:
        self.run_id = run_id
        self.scenario = scenario
        self.scenario_family = scenario_family
        self.load_profile = load_profile
        self.seed = seed
        self.duration_s = duration_s
        self.config_name = config_name
        self.messages: List[SecureMessage] = []
        self.queue_timeseries: List[Dict[str, object]] = []
        self.resource_usage: List[Dict[str, object]] = []
        self.policy_events: List[Dict[str, object]] = []
        self.replay_events: List[Dict[str, object]] = []
        self.counters: Dict[str, float] = {
            "channel_busy_time_s": 0.0,
            "crypto_busy_time_s": 0.0,
        }

    def register_message(self, message: SecureMessage) -> None:
        self.messages.append(message)

    def record_queue_lengths(self, at_time: float, queue_lengths: Dict[str, int]) -> None:
        total = sum(queue_lengths.values())
        self.queue_timeseries.append(
            {
                "time_s": at_time,
                "queue_total": total,
                **queue_lengths,
            }
        )

    def record_resource_interval(
        self,
        resource_name: str,
        start_time: float,
        end_time: float,
        busy_units: int = 1,
    ) -> None:
        duration = max(0.0, end_time - start_time)
        self.resource_usage.append(
            {
                "resource": resource_name,
                "start_time_s": start_time,
                "end_time_s": end_time,
                "busy_units": busy_units,
                "duration_s": duration,
            }
        )
        counter_key = f"{resource_name}_busy_time_s"
        if counter_key in self.counters:
            self.counters[counter_key] += duration

    def extend_policy_events(self, events: Iterable[Dict[str, object]]) -> None:
        self.policy_events.extend(events)

    def extend_replay_events(self, events: Iterable[Dict[str, object]]) -> None:
        self.replay_events.extend(events)

    def build_run_summary(self) -> Dict[str, object]:
        delivered = [message for message in self.messages if message.delivered]
        message_records = [message.to_record() for message in self.messages]
        latency_by_class: Dict[str, List[float]] = {item.value: [] for item in MESSAGE_CLASS_ORDER}
        for record in message_records:
            latency = record["total_latency_s"]
            if latency is not None:
                latency_by_class[record["message_class"]].append(float(latency))

        queue_total_values = [row["queue_total"] for row in self.queue_timeseries]
        queue_average = statistics.mean(queue_total_values) if queue_total_values else 0.0
        queue_max = max(queue_total_values) if queue_total_values else 0
        observation_window_s = max(
            [self.duration_s] + [float(item["end_time_s"]) for item in self.resource_usage]
        ) if self.resource_usage else self.duration_s
        delivered_ratio = len(delivered) / len(self.messages) if self.messages else 0.0
        dropped_ratio = sum(1 for message in self.messages if message.dropped) / len(self.messages) if self.messages else 0.0
        total_retransmissions = sum(message.retransmission_count for message in self.messages)
        total_latency_values = [float(record["total_latency_s"]) for record in message_records if record["total_latency_s"] is not None]
        total_crypto_times = [message.component_times["crypto_time_s"] for message in self.messages]
        average_crypto_share = statistics.mean(
            [
                message.component_times["crypto_time_s"] / message.total_latency_s
                for message in self.messages
                if message.total_latency_s not in (None, 0.0)
            ]
        ) if any(message.total_latency_s not in (None, 0.0) for message in self.messages) else 0.0
        security_overhead_ratios = [
            (message.full_size_bytes - message.payload_bytes) / float(message.full_size_bytes)
            for message in self.messages
            if message.full_size_bytes
        ]

        summary: Dict[str, object] = {
            "run_id": self.run_id,
            "scenario": self.scenario,
            "scenario_family": self.scenario_family,
            "load_profile": self.load_profile,
            "config_name": self.config_name,
            "seed": self.seed,
            "duration_s": self.duration_s,
            "observation_window_s": observation_window_s,
            "messages_total": len(self.messages),
            "messages_delivered": sum(1 for message in self.messages if message.delivered),
            "messages_dropped": sum(1 for message in self.messages if message.dropped),
            "deadline_missed": sum(1 for message in self.messages if message.deadline_missed),
            "delivered_ratio": delivered_ratio,
            "dropped_ratio": dropped_ratio,
            "deadline_missed_ratio": (
                sum(1 for message in self.messages if message.deadline_missed) / len(self.messages)
                if self.messages else 0.0
            ),
            "retransmissions_total": total_retransmissions,
            "retransmission_ratio": total_retransmissions / len(self.messages) if self.messages else 0.0,
            "average_queue_length": queue_average,
            "max_queue_length": queue_max,
            "channel_utilization": (
                self.counters["channel_busy_time_s"] / observation_window_s if observation_window_s else 0.0
            ),
            "crypto_utilization": (
                self.counters["crypto_busy_time_s"] / observation_window_s if observation_window_s else 0.0
            ),
        }

        delivered_bytes = sum(float(message.metadata.get("effective_tx_bytes", message.full_size_bytes)) for message in delivered)
        summary["throughput_bps"] = (delivered_bytes * 8.0) / self.duration_s if self.duration_s else 0.0
        summary["latency_mean_s"] = statistics.mean(total_latency_values) if total_latency_values else None
        summary["latency_median_s"] = statistics.median(total_latency_values) if total_latency_values else None
        summary["latency_p95_s"] = _percentile(total_latency_values, 0.95)
        summary["latency_p99_s"] = _percentile(total_latency_values, 0.99)
        summary["jitter_s"] = _jitter(total_latency_values)
        summary["crypto_time_mean_s"] = statistics.mean(total_crypto_times) if total_crypto_times else 0.0
        summary["crypto_time_total_s"] = sum(total_crypto_times)
        summary["crypto_share_latency_ratio"] = average_crypto_share
        summary["security_overhead_ratio"] = (
            statistics.mean(security_overhead_ratios) if security_overhead_ratios else 0.0
        )

        for message_class in MESSAGE_CLASS_ORDER:
            class_name = message_class.value
            class_messages = [message for message in self.messages if message.message_class == message_class]
            class_delivered = [message for message in class_messages if message.delivered]
            class_latencies = latency_by_class[class_name]
            deadline_met = sum(1 for message in class_messages if message.delivered and not message.deadline_missed)
            class_deadline_missed = sum(1 for message in class_messages if message.deadline_missed)
            class_dropped = sum(1 for message in class_messages if message.dropped)
            class_retransmissions = sum(message.retransmission_count for message in class_messages)
            delivered_wire_bytes = sum(
                float(message.metadata.get("effective_tx_bytes", message.full_size_bytes))
                for message in class_delivered
            )
            delivered_payload_bytes = sum(message.payload_bytes for message in class_delivered)
            class_crypto_times = [message.component_times["crypto_time_s"] for message in class_messages]
            class_classification_times = [message.component_times["classification_time_s"] for message in class_messages]
            class_queue_times = [message.component_times["queue_time_s"] for message in class_messages]
            class_tx_times = [message.component_times["tx_time_s"] for message in class_messages]
            class_ack_times = [message.component_times["ack_time_s"] for message in class_messages]
            class_crypto_share_values = [
                message.component_times["crypto_time_s"] / message.total_latency_s
                for message in class_messages
                if message.total_latency_s not in (None, 0.0)
            ]
            class_security_overhead_values = [
                (message.full_size_bytes - message.payload_bytes) / float(message.full_size_bytes)
                for message in class_messages
                if message.full_size_bytes
            ]
            summary[f"{class_name}_count"] = len(class_messages)
            summary[f"{class_name}_delivered_ratio"] = (
                len(class_delivered) / len(class_messages) if class_messages else 0.0
            )
            summary[f"{class_name}_deadline_met_ratio"] = (
                deadline_met / len(class_messages) if class_messages else 0.0
            )
            summary[f"{class_name}_deadline_missed_ratio"] = (
                class_deadline_missed / len(class_messages) if class_messages else 0.0
            )
            summary[f"{class_name}_dropped_ratio"] = (
                class_dropped / len(class_messages) if class_messages else 0.0
            )
            summary[f"{class_name}_loss_ratio"] = (
                1.0 - len(class_delivered) / len(class_messages) if class_messages else 0.0
            )
            summary[f"{class_name}_retransmissions_total"] = class_retransmissions
            summary[f"{class_name}_retransmission_ratio"] = (
                class_retransmissions / len(class_messages) if class_messages else 0.0
            )
            summary[f"{class_name}_throughput_bps"] = (
                (delivered_wire_bytes * 8.0) / self.duration_s if self.duration_s else 0.0
            )
            summary[f"{class_name}_useful_throughput_bps"] = (
                (delivered_payload_bytes * 8.0) / self.duration_s if self.duration_s else 0.0
            )
            summary[f"{class_name}_latency_mean_s"] = (
                statistics.mean(class_latencies) if class_latencies else None
            )
            summary[f"{class_name}_latency_median_s"] = (
                statistics.median(class_latencies) if class_latencies else None
            )
            summary[f"{class_name}_latency_p95_s"] = _percentile(class_latencies, 0.95)
            summary[f"{class_name}_latency_p99_s"] = _percentile(class_latencies, 0.99)
            summary[f"{class_name}_jitter_s"] = _jitter(class_latencies)
            summary[f"{class_name}_classification_time_mean_s"] = (
                statistics.mean(class_classification_times) if class_classification_times else 0.0
            )
            summary[f"{class_name}_crypto_time_mean_s"] = (
                statistics.mean(class_crypto_times) if class_crypto_times else 0.0
            )
            summary[f"{class_name}_queue_time_mean_s"] = (
                statistics.mean(class_queue_times) if class_queue_times else 0.0
            )
            summary[f"{class_name}_tx_time_mean_s"] = (
                statistics.mean(class_tx_times) if class_tx_times else 0.0
            )
            summary[f"{class_name}_ack_time_mean_s"] = (
                statistics.mean(class_ack_times) if class_ack_times else 0.0
            )
            summary[f"{class_name}_crypto_share_latency_ratio"] = (
                statistics.mean(class_crypto_share_values) if class_crypto_share_values else 0.0
            )
            summary[f"{class_name}_security_overhead_ratio"] = (
                statistics.mean(class_security_overhead_values) if class_security_overhead_values else 0.0
            )

        return summary

    def export_csv(self, output_dir: str, manifest: Dict[str, object]) -> Dict[str, str]:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        messages_path = target_dir / "messages.csv"
        queue_path = target_dir / "queue_timeseries.csv"
        resource_path = target_dir / "resource_usage.csv"
        policy_path = target_dir / "policy_events.csv"
        runs_path = target_dir / "runs.csv"
        manifest_path = target_dir / "manifest.json"

        self._write_csv(messages_path, [message.to_record() for message in self.messages])
        self._write_csv(queue_path, self.queue_timeseries)
        self._write_csv(resource_path, self.resource_usage)
        self._write_csv(policy_path, self.policy_events + self.replay_events)
        self._write_csv(runs_path, [self.build_run_summary()])

        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)

        return {
            "messages": str(messages_path),
            "queue_timeseries": str(queue_path),
            "resource_usage": str(resource_path),
            "policy_events": str(policy_path),
            "runs": str(runs_path),
            "manifest": str(manifest_path),
        }

    def _write_csv(self, path: Path, rows: List[Dict[str, object]]) -> None:
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
