import random
import unittest
from pathlib import Path

import simpy

from secure_delivery.config import ExperimentConfig
from secure_delivery.crypto.engine import CryptoEngine
from secure_delivery.metrics.collector import MetricsCollector
from secure_delivery.models.enums import MessageClass
from secure_delivery.models.message import SecureMessage
from secure_delivery.policy.backends import FilePolicyBackend
from secure_delivery.policy.manager import PolicyManager
from secure_delivery.scheduler.gateway import GatewayScheduler


class SchedulerAggregationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        policy_path = str(Path("configs/policies/baseline_policies.json").resolve())
        config = ExperimentConfig.from_dict(
            {
                "run_id": "scheduler_test",
                "scenario": "C",
                "scenario_family": "C",
                "load_profile": "test",
                "seed": 7,
                "duration_s": 1.0,
                "queue_discipline": "drr",
                "classification_delay_s": 0.0001,
                "crypto_workers": 1,
                "grace_period_s": 0.2,
                "channel": {
                    "bandwidth_bps": 64000,
                    "propagation_delay_s": 0.02,
                    "loss_probability": 0.0,
                    "buffer_size": 10,
                },
                "ack": {
                    "delay_s": 0.0,
                    "loss_probability": 0.0,
                },
                "aggregation": {
                    "max_messages": 6,
                    "max_payload_bytes": 3072,
                    "hold_time_s": 0.0,
                    "member_overhead_bytes": 12,
                },
                "crypto_engine": {
                    "mode": "synthetic",
                    "priority_mode": "class",
                },
                "policy_backend": {
                    "backend_type": "file",
                    "path": policy_path,
                },
                "initial_policy_version": "scenario_c_priority_protected",
                "policy_updates": [],
                "replay_window_size": 64,
                "sources": [],
            }
        )

        self.env = simpy.Environment()
        self.policy_manager = PolicyManager(FilePolicyBackend(policy_path))
        self.policy_manager.switch_version("scenario_c_priority_protected", at_time=0.0, reason="test")
        self.gateway = GatewayScheduler(
            env=self.env,
            config=config,
            policy_manager=self.policy_manager,
            crypto_engine=CryptoEngine(config.crypto_engine),
            metrics=MetricsCollector(
                run_id=config.run_id,
                scenario=config.scenario,
                scenario_family=config.scenario_family,
                load_profile=config.load_profile,
                seed=config.seed,
                duration_s=config.duration_s,
            ),
            randomizer=random.Random(config.seed),
        )

    def test_estimated_drr_service_bytes_include_telemetry_aggregation(self) -> None:
        self.gateway.class_queues[MessageClass.TELEMETRY].items.extend(
            [
                self._message("telemetry-1", MessageClass.TELEMETRY, 512, 1),
                self._message("telemetry-2", MessageClass.TELEMETRY, 512, 2),
            ]
        )

        class_policy = self.policy_manager.get_class_policy(MessageClass.TELEMETRY)
        profile = self.policy_manager.security_profiles[class_policy.security_profile]
        single_size = self.gateway._compute_batch_full_size(profile, 512, 1)
        estimated_size = self.gateway._estimate_batch_service_bytes(MessageClass.TELEMETRY)

        self.assertGreater(estimated_size, single_size)

    def test_telemetry_aggregation_is_suppressed_when_higher_priority_backlog_exists(self) -> None:
        self.gateway.class_queues[MessageClass.TELEMETRY].items.extend(
            [
                self._message("telemetry-1", MessageClass.TELEMETRY, 512, 1),
                self._message("telemetry-2", MessageClass.TELEMETRY, 512, 2),
            ]
        )
        self.gateway.class_queues[MessageClass.CRITICAL].items.append(
            self._message("critical-1", MessageClass.CRITICAL, 64, 1)
        )

        class_policy = self.policy_manager.get_class_policy(MessageClass.TELEMETRY)
        profile = self.policy_manager.security_profiles[class_policy.security_profile]
        single_size = self.gateway._compute_batch_full_size(profile, 512, 1)
        estimated_size = self.gateway._estimate_batch_service_bytes(MessageClass.TELEMETRY)

        self.assertEqual(estimated_size, single_size)

    def _message(
        self,
        message_id: str,
        message_class: MessageClass,
        payload_bytes: int,
        sequence_no: int,
    ) -> SecureMessage:
        return SecureMessage(
            message_id=message_id,
            src=f"source_{message_class.value}",
            dst="receiver",
            message_class=message_class,
            payload_bytes=payload_bytes,
            generated_at=0.0,
            deadline_s=1.0,
            sequence_no=sequence_no,
        )


if __name__ == "__main__":
    unittest.main()
