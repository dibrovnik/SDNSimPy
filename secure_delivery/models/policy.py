from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List

from secure_delivery.models.enums import MessageClass


@dataclass
class ClassPolicy:
    message_class: MessageClass
    priority: int
    weight: int
    max_retransmissions: int
    aggregation_enabled: bool
    drop_allowed: bool
    deadline_s: float
    security_profile: str
    authorized_sources: List[str] = field(default_factory=list)

    def is_authorized(self, source_id: str) -> bool:
        return not self.authorized_sources or source_id in self.authorized_sources

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["message_class"] = self.message_class.value
        return payload

    @classmethod
    def from_dict(cls, message_class: MessageClass, payload: Dict[str, object]) -> "ClassPolicy":
        return cls(
            message_class=message_class,
            priority=int(payload["priority"]),
            weight=int(payload.get("weight", 1)),
            max_retransmissions=int(payload.get("max_retransmissions", 0)),
            aggregation_enabled=bool(payload.get("aggregation_enabled", False)),
            drop_allowed=bool(payload.get("drop_allowed", False)),
            deadline_s=float(payload.get("deadline_s", 0.0)),
            security_profile=str(payload["security_profile"]),
            authorized_sources=[str(item) for item in payload.get("authorized_sources", [])],
        )


@dataclass
class PolicyVersion:
    version_id: str
    description: str
    class_policies: Dict[MessageClass, ClassPolicy]

    def to_dict(self) -> Dict[str, object]:
        return {
            "version_id": self.version_id,
            "description": self.description,
            "class_policies": {
                message_class.value: policy.to_dict()
                for message_class, policy in self.class_policies.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "PolicyVersion":
        class_policies_payload = dict(payload["class_policies"])
        class_policies = {
            MessageClass.from_value(name): ClassPolicy.from_dict(MessageClass.from_value(name), dict(details))
            for name, details in class_policies_payload.items()
        }
        return cls(
            version_id=str(payload["version_id"]),
            description=str(payload.get("description", "")),
            class_policies=class_policies,
        )
