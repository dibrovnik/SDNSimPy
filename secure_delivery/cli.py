from __future__ import annotations

import argparse
import json
from pathlib import Path

from secure_delivery.experiments.runner import run_batch, run_experiment
from secure_delivery.plots.builder import build_plots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="secure-delivery")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_experiment_parser = subparsers.add_parser("run-experiment", help="Run a single experiment config")
    run_experiment_parser.add_argument("--config", required=True, help="Path to experiment JSON config")
    run_experiment_parser.add_argument("--output-dir", required=True, help="Directory for CSV/JSON results")

    run_batch_parser = subparsers.add_parser("run-batch", help="Run every experiment config in a directory")
    run_batch_parser.add_argument("--config-dir", required=True, help="Directory with JSON configs")
    run_batch_parser.add_argument("--output-root", required=True, help="Root directory for batch results")

    build_plots_parser = subparsers.add_parser("build-plots", help="Build plots from a run output directory")
    build_plots_parser.add_argument("--input-dir", required=True, help="Directory containing CSV results")
    build_plots_parser.add_argument("--output-dir", required=True, help="Directory for generated plots")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run-experiment":
        result = run_experiment(args.config, args.output_dir)
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-batch":
        result = run_batch(args.config_dir, args.output_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "build-plots":
        result = build_plots(args.input_dir, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
