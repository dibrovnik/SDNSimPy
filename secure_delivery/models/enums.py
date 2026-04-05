from __future__ import annotations

from enum import Enum


class MessageClass(str, Enum):
    CRITICAL = "critical"
    CONTROL = "control"
    TELEMETRY = "telemetry"
    BACKGROUND = "background"

    @classmethod
    def from_value(cls, value: str) -> "MessageClass":
        normalized = value.lower().strip()
        for item in cls:
            if item.value == normalized:
                return item
        raise ValueError(f"Unknown message class: {value}")


class QueueDiscipline(str, Enum):
    FIFO = "fifo"
    STRICT_PRIORITY = "strict_priority"
    DRR = "drr"
    WEIGHTED_PRIORITY = "weighted_priority"

    @classmethod
    def from_value(cls, value: str) -> "QueueDiscipline":
        normalized = value.lower().strip()
        aliases = {
            "weighted_priority": cls.WEIGHTED_PRIORITY,
            "drr": cls.DRR,
            "strict_priority": cls.STRICT_PRIORITY,
            "fifo": cls.FIFO,
        }
        if normalized not in aliases:
            raise ValueError(f"Unknown queue discipline: {value}")
        return aliases[normalized]


MESSAGE_CLASS_ORDER = [
    MessageClass.CRITICAL,
    MessageClass.CONTROL,
    MessageClass.TELEMETRY,
    MessageClass.BACKGROUND,
]
