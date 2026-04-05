import json
import tempfile
import unittest
from pathlib import Path

from secure_delivery.experiments.analysis import compare_metric, export_article_tables
from secure_delivery.experiments.runner import run_batch


class AnalysisToolsTestCase(unittest.TestCase):
    def test_compare_metric_and_article_export_include_batch_statistics(self) -> None:
        policy_path = Path("configs/policies/baseline_policies.json").resolve()
        base_config = {
            "seed": 41,
            "duration_s": 0.6,
            "classification_delay_s": 0.0001,
            "crypto_workers": 1,
            "grace_period_s": 0.2,
            "channel": {
                "bandwidth_bps": 64000,
                "propagation_delay_s": 0.01,
                "loss_probability": 0.0,
                "buffer_size": 10,
            },
            "ack": {
                "delay_s": 0.01,
                "loss_probability": 0.0,
            },
            "aggregation": {
                "max_messages": 2,
                "max_payload_bytes": 1024,
                "hold_time_s": 0.0,
                "member_overhead_bytes": 8,
            },
            "crypto_engine": {
                "mode": "synthetic",
            },
            "policy_backend": {
                "backend_type": "file",
                "path": str(policy_path),
            },
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
                    "interval_s": 0.2,
                }
            ],
        }

        scenarios = [
            (
                "A",
                {
                    **base_config,
                    "run_id": "scenario_a_test",
                    "scenario": "A",
                    "scenario_family": "A",
                    "load_profile": "test",
                    "queue_discipline": "fifo",
                    "initial_policy_version": "scenario_a_uniform_fifo",
                    "crypto_engine": {
                        "mode": "synthetic",
                        "priority_mode": "uniform",
                    },
                },
            ),
            (
                "B",
                {
                    **base_config,
                    "run_id": "scenario_b_test",
                    "scenario": "B",
                    "scenario_family": "B",
                    "load_profile": "test",
                    "queue_discipline": "strict_priority",
                    "initial_policy_version": "scenario_b_priority_uniform",
                    "crypto_engine": {
                        "mode": "synthetic",
                        "priority_mode": "uniform",
                    },
                },
            ),
            (
                "C",
                {
                    **base_config,
                    "run_id": "scenario_c_test",
                    "scenario": "C",
                    "scenario_family": "C",
                    "load_profile": "test",
                    "queue_discipline": "drr",
                    "initial_policy_version": "scenario_c_priority_protected",
                    "crypto_engine": {
                        "mode": "synthetic",
                        "priority_mode": "class",
                    },
                },
            ),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "configs"
            output_root = Path(temp_dir) / "batch"
            article_dir = Path(temp_dir) / "article"
            config_dir.mkdir()

            for scenario_name, config in scenarios:
                (config_dir / f"{scenario_name.lower()}.json").write_text(
                    json.dumps(config),
                    encoding="utf-8",
                )

            run_batch(str(config_dir), str(output_root), replicates=2, seed_step=1)

            metric_rows = compare_metric(str(output_root), "control_latency_mean_s")
            self.assertTrue(metric_rows)
            self.assertTrue(all("stddev" in row for row in metric_rows))
            self.assertTrue(all("ci95_low" in row for row in metric_rows))
            self.assertTrue(all(int(row["count"]) == 2 for row in metric_rows))

            exported = export_article_tables(str(output_root), str(article_dir))
            self.assertTrue(Path(exported["critical_performance"]).exists())
            self.assertTrue(Path(exported["scenario_deltas"]).exists())

            delta_rows = Path(exported["scenario_deltas"]).read_text(encoding="utf-8")
            self.assertIn("critical_latency_improvement_ratio", delta_rows)
            self.assertIn("C", delta_rows)


if __name__ == "__main__":
    unittest.main()
