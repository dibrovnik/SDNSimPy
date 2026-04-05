from __future__ import annotations

from typing import Dict, List

from secure_delivery.config import CryptoEngineConfig
from secure_delivery.models.profile import SecurityProfile


class CryptoEngine:
    def __init__(self, config: CryptoEngineConfig) -> None:
        self.config = config
        self.profile_counters: Dict[str, int] = {}

    def compute_full_size(self, profile: SecurityProfile, payload_bytes: int, members: int = 1) -> int:
        return payload_bytes + profile.header_bytes + profile.tag_bytes + profile.aux_bytes + max(0, members - 1)

    def compute_crypto_time(self, profile: SecurityProfile, payload_bytes: int) -> float:
        mode = self.config.mode.lower()
        counter = self.profile_counters.get(profile.name, 0) + 1
        self.profile_counters[profile.name] = counter

        if mode == "synthetic":
            return self._synthetic_cost(profile, payload_bytes, counter)
        if mode == "lookup_table":
            return self._lookup_cost(profile, payload_bytes, counter)
        if mode == "measured_stub":
            return self._synthetic_cost(profile, payload_bytes, counter) * self.config.measured_stub_scale
        raise ValueError(f"Unsupported crypto engine mode: {self.config.mode}")

    def _synthetic_cost(self, profile: SecurityProfile, payload_bytes: int, counter: int) -> float:
        total = profile.overhead_s + profile.per_byte_s * payload_bytes + profile.verify_overhead_s
        if profile.rekey_every_n_messages and counter % profile.rekey_every_n_messages == 0:
            total += profile.rekey_overhead_s
        return total

    def _lookup_cost(self, profile: SecurityProfile, payload_bytes: int, counter: int) -> float:
        points = profile.lookup_table or {
            int(key): value for key, value in self.config.lookup_tables.get(profile.name, {}).items()
        }
        if not points:
            return self._synthetic_cost(profile, payload_bytes, counter)

        sorted_sizes: List[int] = sorted(points.keys())
        if payload_bytes <= sorted_sizes[0]:
            total = points[sorted_sizes[0]]
        elif payload_bytes >= sorted_sizes[-1]:
            total = points[sorted_sizes[-1]]
        else:
            total = points[sorted_sizes[-1]]
            for index in range(len(sorted_sizes) - 1):
                left = sorted_sizes[index]
                right = sorted_sizes[index + 1]
                if left <= payload_bytes <= right:
                    left_value = points[left]
                    right_value = points[right]
                    ratio = (payload_bytes - left) / float(right - left)
                    total = left_value + ratio * (right_value - left_value)
                    break

        if profile.rekey_every_n_messages and counter % profile.rekey_every_n_messages == 0:
            total += profile.rekey_overhead_s
        return total
