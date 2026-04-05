import json
import tempfile
import unittest
from pathlib import Path

from secure_delivery.experiments.sweep import generate_sweep_configs


class SweepGenerationTestCase(unittest.TestCase):
    def test_generate_sweep_configs_creates_variants_with_absolute_policy_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_config_dir = root / "configs"
            policies_dir = root / "policies"
            generated_dir = root / "generated"
            matrix_path = root / "matrix.json"
            base_config_dir.mkdir()
            policies_dir.mkdir()

            (policies_dir / "bundle.json").write_text(
                json.dumps({"metadata": {}, "security_profiles": {}, "policy_versions": []}),
                encoding="utf-8",
            )
            (base_config_dir / "one.json").write_text(
                json.dumps(
                    {
                        "run_id": "scenario_a_normal",
                        "scenario": "A",
                        "scenario_family": "A",
                        "load_profile": "normal",
                        "seed": 1,
                        "duration_s": 1.0,
                        "queue_discipline": "fifo",
                        "classification_delay_s": 0.0001,
                        "crypto_workers": 1,
                        "grace_period_s": 0.1,
                        "channel": {
                            "bandwidth_bps": 64000,
                            "propagation_delay_s": 0.01,
                            "loss_probability": 0.0,
                            "buffer_size": 10,
                        },
                        "ack": {"delay_s": 0.0, "loss_probability": 0.0},
                        "aggregation": {
                            "max_messages": 1,
                            "max_payload_bytes": 0,
                            "hold_time_s": 0.0,
                            "member_overhead_bytes": 0,
                        },
                        "crypto_engine": {"mode": "synthetic", "priority_mode": "uniform"},
                        "policy_backend": {
                            "backend_type": "file",
                            "path": "../policies/bundle.json",
                        },
                        "initial_policy_version": "v1",
                        "policy_updates": [],
                        "replay_window_size": 32,
                        "notes": "base",
                        "sources": [],
                    }
                ),
                encoding="utf-8",
            )
            matrix_path.write_text(
                json.dumps(
                    {
                        "dimensions": {
                            "bandwidth_bps": [64000, 128000],
                            "buffer_size": [10],
                            "loss_probability": [0.0],
                        },
                        "filters": {
                            "scenario_families": ["A"],
                            "load_profiles": ["normal"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            generated = generate_sweep_configs(str(base_config_dir), str(matrix_path), str(generated_dir))

            self.assertEqual(len(generated), 2)
            first_payload = json.loads(Path(generated[0]).read_text(encoding="utf-8"))
            self.assertTrue(Path(first_payload["policy_backend"]["path"]).is_absolute())
            self.assertIn("Sweep overrides", first_payload["notes"])
            self.assertIn("bw64k", first_payload["run_id"])


if __name__ == "__main__":
    unittest.main()
