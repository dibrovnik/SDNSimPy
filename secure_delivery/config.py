from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from secure_delivery.models.enums import MessageClass, QueueDiscipline


@dataclass
class ChannelConfig:
    bandwidth_bps: int
    propagation_delay_s: float
    loss_probability: float
    buffer_size: int


@dataclass
class AckConfig:
    delay_s: float = 0.0
    loss_probability: float = 0.0


@dataclass
class AggregationConfig:
    max_messages: int = 1
    max_payload_bytes: int = 0
    hold_time_s: float = 0.0
    member_overhead_bytes: int = 0


@dataclass
class CryptoEngineConfig:
    mode: str = "synthetic"
    lookup_tables: Dict[str, Dict[str, float]] = field(default_factory=dict)
    measured_stub_scale: float = 1.0
    priority_mode: str = "class"


@dataclass
class PolicyBackendConfig:
    backend_type: str
    path: str


@dataclass
class PolicyUpdateConfig:
    at_time_s: float
    version_id: str


@dataclass
class SourceConfig:
    source_id: str
    message_class: MessageClass
    generator: str
    payload_bytes: int
    dst: str
    start_time_s: float = 0.0
    stop_time_s: Optional[float] = None
    deadline_s: Optional[float] = None
    interval_s: Optional[float] = None
    rate_per_sec: Optional[float] = None
    burst_size: Optional[int] = None
    burst_interval_s: Optional[float] = None
    intra_burst_gap_s: float = 0.0

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SourceConfig":
        return cls(
            source_id=str(payload["source_id"]),
            message_class=MessageClass.from_value(str(payload["message_class"])),
            generator=str(payload["generator"]),
            payload_bytes=int(payload["payload_bytes"]),
            dst=str(payload.get("dst", "receiver")),
            start_time_s=float(payload.get("start_time_s", 0.0)),
            stop_time_s=float(payload["stop_time_s"]) if payload.get("stop_time_s") is not None else None,
            deadline_s=float(payload["deadline_s"]) if payload.get("deadline_s") is not None else None,
            interval_s=float(payload["interval_s"]) if payload.get("interval_s") is not None else None,
            rate_per_sec=float(payload["rate_per_sec"]) if payload.get("rate_per_sec") is not None else None,
            burst_size=int(payload["burst_size"]) if payload.get("burst_size") is not None else None,
            burst_interval_s=float(payload["burst_interval_s"]) if payload.get("burst_interval_s") is not None else None,
            intra_burst_gap_s=float(payload.get("intra_burst_gap_s", 0.0)),
        )


@dataclass
class ExperimentConfig:
    run_id: str
    scenario: str
    scenario_family: str
    load_profile: str
    seed: int
    duration_s: float
    queue_discipline: QueueDiscipline
    classification_delay_s: float
    crypto_workers: int
    grace_period_s: float
    channel: ChannelConfig
    ack: AckConfig
    aggregation: AggregationConfig
    crypto_engine: CryptoEngineConfig
    policy_backend: PolicyBackendConfig
    initial_policy_version: str
    policy_updates: List[PolicyUpdateConfig]
    replay_window_size: int
    sources: List[SourceConfig]
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: Dict[str, object], config_path: Optional[Path] = None) -> "ExperimentConfig":
        policy_backend_payload = dict(payload["policy_backend"])
        if config_path is not None:
            policy_path = Path(policy_backend_payload["path"])
            if not policy_path.is_absolute():
                policy_backend_payload["path"] = str((config_path.parent / policy_path).resolve())
        return cls(
            run_id=str(payload["run_id"]),
            scenario=str(payload["scenario"]),
            scenario_family=str(payload.get("scenario_family", payload["scenario"])),
            load_profile=str(payload.get("load_profile", "custom")),
            seed=int(payload.get("seed", 1)),
            duration_s=float(payload["duration_s"]),
            queue_discipline=QueueDiscipline.from_value(str(payload["queue_discipline"])),
            classification_delay_s=float(payload.get("classification_delay_s", 0.0001)),
            crypto_workers=int(payload.get("crypto_workers", 1)),
            grace_period_s=float(payload.get("grace_period_s", 2.0)),
            channel=ChannelConfig(**dict(payload["channel"])),
            ack=AckConfig(**dict(payload.get("ack", {}))),
            aggregation=AggregationConfig(**dict(payload.get("aggregation", {}))),
            crypto_engine=CryptoEngineConfig(**dict(payload.get("crypto_engine", {}))),
            policy_backend=PolicyBackendConfig(**policy_backend_payload),
            initial_policy_version=str(payload["initial_policy_version"]),
            policy_updates=[
                PolicyUpdateConfig(
                    at_time_s=float(item["at_time_s"]),
                    version_id=str(item["version_id"]),
                )
                for item in payload.get("policy_updates", [])
            ],
            replay_window_size=int(payload.get("replay_window_size", 64)),
            sources=[SourceConfig.from_dict(item) for item in payload.get("sources", [])],
            notes=str(payload.get("notes", "")),
        )


def load_experiment_config(path: str) -> ExperimentConfig:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return ExperimentConfig.from_dict(payload, config_path=config_path)
