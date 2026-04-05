from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from secure_delivery.config import ExperimentConfig, SourceConfig
from secure_delivery.models.message import SecureMessage


@dataclass
class TrafficSource:
    config: SourceConfig
    gateway: "GatewayScheduler"
    randomizer: random.Random

    def run(self, env: "simpy.Environment"):
        if self.config.start_time_s > 0:
            yield env.timeout(self.config.start_time_s)

        sequence_no = 0
        while True:
            if self.config.stop_time_s is not None and env.now > self.config.stop_time_s:
                break
            if env.now > self.gateway.duration_s:
                break

            sequence_no += 1
            deadline_s = self.config.deadline_s
            message = SecureMessage(
                message_id=f"{self.config.source_id}-{sequence_no}",
                src=self.config.source_id,
                dst=self.config.dst,
                message_class=self.config.message_class,
                payload_bytes=self.config.payload_bytes,
                generated_at=env.now,
                deadline_s=deadline_s if deadline_s is not None else 0.0,
                sequence_no=sequence_no,
            )
            message.mark_event("generated_at", env.now)
            self.gateway.submit(message)

            next_interval = self._next_interval()
            if next_interval is None:
                break
            yield env.timeout(next_interval)

    def _next_interval(self) -> Optional[float]:
        generator = self.config.generator.lower()
        if generator == "periodic":
            if self.config.interval_s is None:
                raise ValueError(f"interval_s is required for periodic source {self.config.source_id}")
            return self.config.interval_s
        if generator == "poisson":
            if self.config.rate_per_sec is None:
                raise ValueError(f"rate_per_sec is required for poisson source {self.config.source_id}")
            return self.randomizer.expovariate(self.config.rate_per_sec)
        if generator == "burst":
            raise RuntimeError("Burst source must use BurstTrafficSource")
        raise ValueError(f"Unsupported generator: {self.config.generator}")


@dataclass
class BurstTrafficSource(TrafficSource):
    def run(self, env: "simpy.Environment"):
        if self.config.start_time_s > 0:
            yield env.timeout(self.config.start_time_s)

        sequence_no = 0
        burst_size = self.config.burst_size or 1
        burst_interval_s = self.config.burst_interval_s
        if burst_interval_s is None:
            raise ValueError(f"burst_interval_s is required for burst source {self.config.source_id}")

        while True:
            if self.config.stop_time_s is not None and env.now > self.config.stop_time_s:
                break
            if env.now > self.gateway.duration_s:
                break

            for _ in range(burst_size):
                sequence_no += 1
                message = SecureMessage(
                    message_id=f"{self.config.source_id}-{sequence_no}",
                    src=self.config.source_id,
                    dst=self.config.dst,
                    message_class=self.config.message_class,
                    payload_bytes=self.config.payload_bytes,
                    generated_at=env.now,
                    deadline_s=self.config.deadline_s if self.config.deadline_s is not None else 0.0,
                    sequence_no=sequence_no,
                )
                message.mark_event("generated_at", env.now)
                self.gateway.submit(message)
                if self.config.intra_burst_gap_s > 0:
                    yield env.timeout(self.config.intra_burst_gap_s)

            yield env.timeout(burst_interval_s)


def build_sources(config: ExperimentConfig, gateway: "GatewayScheduler") -> List[TrafficSource]:
    sources: List[TrafficSource] = []
    for index, source_config in enumerate(config.sources):
        randomizer = random.Random(config.seed + 1009 * (index + 1))
        if source_config.generator.lower() == "burst":
            sources.append(BurstTrafficSource(source_config, gateway, randomizer))
        else:
            sources.append(TrafficSource(source_config, gateway, randomizer))
    return sources
