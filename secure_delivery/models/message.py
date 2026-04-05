from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from secure_delivery.models.enums import MessageClass


@dataclass
class SecureMessage:
    message_id: str
    src: str
    dst: str
    message_class: MessageClass
    payload_bytes: int
    generated_at: float
    deadline_s: float
    sequence_no: int
    requested_profile: Optional[str] = None
    policy_version_id: Optional[str] = None
    full_size_bytes: int = 0
    retransmission_count: int = 0
    delivered: bool = False
    dropped: bool = False
    deadline_missed: bool = False
    drop_reason: Optional[str] = None
    classified_at: Optional[float] = None
    crypto_start_at: Optional[float] = None
    crypto_end_at: Optional[float] = None
    queue_enter_at: Optional[float] = None
    queue_leave_at: Optional[float] = None
    tx_start_at: Optional[float] = None
    tx_end_at: Optional[float] = None
    ack_wait_start_at: Optional[float] = None
    ack_received_at: Optional[float] = None
    delivered_at: Optional[float] = None
    dropped_at: Optional[float] = None
    component_times: Dict[str, float] = field(
        default_factory=lambda: {
            "classification_time_s": 0.0,
            "crypto_time_s": 0.0,
            "queue_time_s": 0.0,
            "tx_time_s": 0.0,
            "ack_time_s": 0.0,
        }
    )
    lifecycle_events: List[Dict[str, object]] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)
    current_attempt_queue_enter_at: Optional[float] = None
    current_attempt_no: int = 0

    def mark_event(self, name: str, at: float, **extra: object) -> None:
        self.lifecycle_events.append({"event": name, "at": at, **extra})
        if hasattr(self, name) and getattr(self, name) is None:
            setattr(self, name, at)

    @property
    def completed_at(self) -> Optional[float]:
        if self.ack_received_at is not None:
            return self.ack_received_at
        if self.delivered_at is not None:
            return self.delivered_at
        if self.dropped_at is not None:
            return self.dropped_at
        return None

    @property
    def total_latency_s(self) -> Optional[float]:
        completed_at = self.completed_at
        if completed_at is None:
            return None
        return completed_at - self.generated_at

    def evaluate_deadline(self) -> None:
        total_latency = self.total_latency_s
        self.deadline_missed = total_latency is not None and total_latency > self.deadline_s

    def to_record(self) -> Dict[str, object]:
        total_latency = self.total_latency_s
        return {
            "message_id": self.message_id,
            "src": self.src,
            "dst": self.dst,
            "message_class": self.message_class.value,
            "payload_bytes": self.payload_bytes,
            "full_size_bytes": self.full_size_bytes,
            "generated_at": self.generated_at,
            "deadline_s": self.deadline_s,
            "sequence_no": self.sequence_no,
            "policy_version_id": self.policy_version_id,
            "retransmission_count": self.retransmission_count,
            "delivered": self.delivered,
            "dropped": self.dropped,
            "deadline_missed": self.deadline_missed,
            "drop_reason": self.drop_reason,
            "classified_at": self.classified_at,
            "crypto_start_at": self.crypto_start_at,
            "crypto_end_at": self.crypto_end_at,
            "queue_enter_at": self.queue_enter_at,
            "queue_leave_at": self.queue_leave_at,
            "tx_start_at": self.tx_start_at,
            "tx_end_at": self.tx_end_at,
            "ack_wait_start_at": self.ack_wait_start_at,
            "ack_received_at": self.ack_received_at,
            "delivered_at": self.delivered_at,
            "dropped_at": self.dropped_at,
            "classification_time_s": self.component_times["classification_time_s"],
            "crypto_time_s": self.component_times["crypto_time_s"],
            "queue_time_s": self.component_times["queue_time_s"],
            "tx_time_s": self.component_times["tx_time_s"],
            "ack_time_s": self.component_times["ack_time_s"],
            "total_latency_s": total_latency,
            "lifecycle_events_json": json.dumps(self.lifecycle_events, ensure_ascii=False),
            "metadata_json": json.dumps(self.metadata, ensure_ascii=False),
        }
