import json
import tempfile
import unittest
from pathlib import Path

from secure_delivery.experiments.runner import run_experiment


class SecureDeliveryBehaviorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.policy_path = str(Path("configs/policies/baseline_policies.json").resolve())

    def test_reproducible_with_same_seed(self) -> None:
        config = self._base_config(
            run_id="reproducible",
            scenario="C",
            scenario_family="C",
            load_profile="test",
            seed=99,
        )
        config["sources"] = [
            {
                "source_id": "source_telemetry",
                "message_class": "telemetry",
                "generator": "poisson",
                "payload_bytes": 256,
                "dst": "receiver",
                "deadline_s": 1.5,
                "rate_per_sec": 3.0
            }
        ]

        first = self._run_temp_config(config)
        second = self._run_temp_config(config)

        self.assertEqual(first["summary"]["messages_total"], second["summary"]["messages_total"])
        self.assertEqual(first["summary"]["messages_dropped"], second["summary"]["messages_dropped"])
        self.assertAlmostEqual(first["summary"]["latency_mean_s"], second["summary"]["latency_mean_s"])
        self.assertAlmostEqual(first["summary"]["telemetry_latency_mean_s"], second["summary"]["telemetry_latency_mean_s"])

    def test_ack_loss_causes_retransmission_and_drop(self) -> None:
        config = self._base_config(
            run_id="ack_loss",
            scenario="C",
            scenario_family="C",
            load_profile="test",
            seed=101,
        )
        config["ack"]["loss_probability"] = 1.0
        config["duration_s"] = 0.6
        config["grace_period_s"] = 0.6
        config["sources"] = [
            {
                "source_id": "source_command",
                "message_class": "control",
                "generator": "periodic",
                "payload_bytes": 128,
                "dst": "receiver",
                "deadline_s": 0.45,
                "interval_s": 0.5
            }
        ]

        result = self._run_temp_config(config)

        self.assertGreater(result["summary"]["messages_dropped"], 0)
        self.assertGreater(result["summary"]["control_retransmissions_total"], 0)

    def test_drop_before_encrypt_background_with_zero_buffer(self) -> None:
        config = self._base_config(
            run_id="drop_before_encrypt",
            scenario="C",
            scenario_family="C",
            load_profile="test",
            seed=102,
        )
        config["channel"]["buffer_size"] = 0
        config["duration_s"] = 0.5
        config["grace_period_s"] = 0.2
        config["sources"] = [
            {
                "source_id": "source_background",
                "message_class": "background",
                "generator": "periodic",
                "payload_bytes": 1024,
                "dst": "receiver",
                "deadline_s": 6.0,
                "interval_s": 0.2
            }
        ]

        result = self._run_temp_config(config)

        self.assertEqual(result["summary"]["messages_delivered"], 0)
        self.assertGreater(result["summary"]["messages_dropped"], 0)
        self.assertEqual(result["summary"]["crypto_utilization"], 0.0)

    def test_deadline_miss_detected(self) -> None:
        config = self._base_config(
            run_id="deadline_miss",
            scenario="B",
            scenario_family="B",
            load_profile="test",
            seed=103,
        )
        config["initial_policy_version"] = "scenario_b_priority_uniform"
        config["queue_discipline"] = "strict_priority"
        config["duration_s"] = 0.5
        config["grace_period_s"] = 0.2
        config["sources"] = [
            {
                "source_id": "source_command",
                "message_class": "control",
                "generator": "periodic",
                "payload_bytes": 128,
                "dst": "receiver",
                "deadline_s": 0.0001,
                "interval_s": 0.2
            }
        ]

        result = self._run_temp_config(config)

        self.assertGreater(result["summary"]["deadline_missed"], 0)
        self.assertGreater(result["summary"]["control_deadline_missed_ratio"], 0.0)

    def test_uniform_crypto_priority_mode_is_loaded(self) -> None:
        config = self._base_config(
            run_id="uniform_crypto_priority",
            scenario="A",
            scenario_family="A",
            load_profile="test",
            seed=104,
        )
        config["queue_discipline"] = "fifo"
        config["crypto_engine"]["priority_mode"] = "uniform"
        config["initial_policy_version"] = "scenario_a_uniform_fifo"
        config["sources"] = [
            {
                "source_id": "source_command",
                "message_class": "control",
                "generator": "periodic",
                "payload_bytes": 128,
                "dst": "receiver",
                "deadline_s": 0.5,
                "interval_s": 0.2
            }
        ]

        result = self._run_temp_config(config)

        self.assertEqual(result["manifest"]["crypto_engine"]["priority_mode"], "uniform")

    def _run_temp_config(self, config: dict) -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            output_dir = Path(temp_dir) / "output"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            return run_experiment(str(config_path), str(output_dir))

    def _base_config(
        self,
        run_id: str,
        scenario: str,
        scenario_family: str,
        load_profile: str,
        seed: int,
    ) -> dict:
        return {
            "run_id": run_id,
            "scenario": scenario,
            "scenario_family": scenario_family,
            "load_profile": load_profile,
            "seed": seed,
            "duration_s": 1.0,
            "queue_discipline": "drr",
            "classification_delay_s": 0.0001,
            "crypto_workers": 1,
            "grace_period_s": 0.5,
            "channel": {
                "bandwidth_bps": 64000,
                "propagation_delay_s": 0.01,
                "loss_probability": 0.0,
                "buffer_size": 10
            },
            "ack": {
                "delay_s": 0.01,
                "loss_probability": 0.0
            },
            "aggregation": {
                "max_messages": 4,
                "max_payload_bytes": 2048,
                "hold_time_s": 0.0,
                "member_overhead_bytes": 8
            },
            "crypto_engine": {
                "mode": "synthetic"
            },
            "policy_backend": {
                "backend_type": "file",
                "path": self.policy_path
            },
            "initial_policy_version": "scenario_c_priority_protected",
            "policy_updates": [],
            "replay_window_size": 32,
            "notes": "test",
            "sources": []
        }


if __name__ == "__main__":
    unittest.main()
