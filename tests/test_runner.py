import json
import tempfile
import unittest
from pathlib import Path

from secure_delivery.experiments.runner import run_experiment


class ExperimentRunnerTestCase(unittest.TestCase):
    def test_run_experiment_exports_csv_files(self) -> None:
        policy_path = Path("configs/policies/baseline_policies.json").resolve()
        config = {
            "run_id": "test_run",
            "scenario": "test",
            "seed": 7,
            "duration_s": 1.0,
            "queue_discipline": "fifo",
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
                "delay_s": 0.0,
                "loss_probability": 0.0
            },
            "aggregation": {
                "max_messages": 2,
                "max_payload_bytes": 1024,
                "hold_time_s": 0.0,
                "member_overhead_bytes": 8
            },
            "crypto_engine": {
                "mode": "synthetic"
            },
            "policy_backend": {
                "backend_type": "file",
                "path": str(policy_path)
            },
            "initial_policy_version": "scenario_a_uniform_fifo",
            "policy_updates": [],
            "replay_window_size": 32,
            "sources": [
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
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            output_dir = Path(temp_dir) / "output"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = run_experiment(str(config_path), str(output_dir))

            self.assertIn("summary", result)
            self.assertTrue((output_dir / "messages.csv").exists())
            self.assertTrue((output_dir / "runs.csv").exists())
            self.assertGreaterEqual(result["summary"]["messages_total"], 1)


if __name__ == "__main__":
    unittest.main()
