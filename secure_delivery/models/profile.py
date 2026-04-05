from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Optional


@dataclass
class SecurityProfile:
    name: str
    algorithm: str
    overhead_s: float
    per_byte_s: float
    verify_overhead_s: float
    rekey_overhead_s: float
    header_bytes: int
    tag_bytes: int
    aux_bytes: int = 0
    anti_replay: bool = False
    ack_required: bool = False
    batching_allowed: bool = False
    drop_before_encrypt: bool = False
    rekey_every_n_messages: Optional[int] = None
    lookup_table: Dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SecurityProfile":
        lookup_table_payload = payload.get("lookup_table", {})
        lookup_table = {
            int(key): float(value)
            for key, value in dict(lookup_table_payload).items()
        }
        return cls(
            name=str(payload["name"]),
            algorithm=str(payload["algorithm"]),
            overhead_s=float(payload.get("overhead_s", 0.0)),
            per_byte_s=float(payload.get("per_byte_s", 0.0)),
            verify_overhead_s=float(payload.get("verify_overhead_s", 0.0)),
            rekey_overhead_s=float(payload.get("rekey_overhead_s", 0.0)),
            header_bytes=int(payload.get("header_bytes", 0)),
            tag_bytes=int(payload.get("tag_bytes", 0)),
            aux_bytes=int(payload.get("aux_bytes", 0)),
            anti_replay=bool(payload.get("anti_replay", False)),
            ack_required=bool(payload.get("ack_required", False)),
            batching_allowed=bool(payload.get("batching_allowed", False)),
            drop_before_encrypt=bool(payload.get("drop_before_encrypt", False)),
            rekey_every_n_messages=int(payload["rekey_every_n_messages"])
            if payload.get("rekey_every_n_messages") is not None
            else None,
            lookup_table=lookup_table,
        )
