from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List


class ReplayWindow:
    def __init__(self, size: int = 64) -> None:
        self.size = size
        self.max_seen = -1
        self.accepted: Deque[int] = deque()
        self.accepted_lookup = set()
        self.incidents: List[Dict[str, object]] = []

    def accept(self, sequence_no: int, at_time: float, source_id: str, stream_id: str) -> bool:
        if sequence_no in self.accepted_lookup:
            self.incidents.append(
                {
                    "time_s": at_time,
                    "event": "replay_detected",
                    "source_id": source_id,
                    "stream_id": stream_id,
                    "sequence_no": sequence_no,
                }
            )
            return False

        if self.max_seen >= 0 and sequence_no < self.max_seen - self.size:
            self.incidents.append(
                {
                    "time_s": at_time,
                    "event": "replay_out_of_window",
                    "source_id": source_id,
                    "stream_id": stream_id,
                    "sequence_no": sequence_no,
                }
            )
            return False

        self.accepted.append(sequence_no)
        self.accepted_lookup.add(sequence_no)
        self.max_seen = max(self.max_seen, sequence_no)

        while len(self.accepted) > self.size:
            expired = self.accepted.popleft()
            self.accepted_lookup.remove(expired)

        return True

    def export_events(self) -> List[Dict[str, object]]:
        return list(self.incidents)
