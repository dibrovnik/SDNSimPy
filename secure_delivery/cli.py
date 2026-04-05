from __future__ import annotations

import argparse
import json

from secure_delivery.experiments.analysis import compare_metric, export_article_tables
from secure_delivery.experiments.runner import run_batch, run_experiment
from secure_delivery.experiments.sweep import run_parameter_sweep
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
    run_batch_parser.add_argument("--replicates", type=int, default=1, help="How many seed replicates to run per config")
    run_batch_parser.add_argument("--seed-step", type=int, default=1, help="Seed increment between replicates")

    run_sweep_parser = subparsers.add_parser("run-sweep", help="Generate and run an expanded parameter sweep")
    run_sweep_parser.add_argument("--base-config-dir", required=True, help="Directory with base experiment JSON configs")
    run_sweep_parser.add_argument("--matrix", required=True, help="Path to sweep matrix JSON")
    run_sweep_parser.add_argument("--output-root", required=True, help="Root directory for generated configs and results")
    run_sweep_parser.add_argument("--replicates", type=int, default=1, help="How many seed replicates to run per generated config")
    run_sweep_parser.add_argument("--seed-step", type=int, default=1, help="Seed increment between replicates")

    build_plots_parser = subparsers.add_parser("build-plots", help="Build plots from a run output directory")
    build_plots_parser.add_argument("--input-dir", required=True, help="Directory containing CSV results")
    build_plots_parser.add_argument("--output-dir", required=True, help="Directory for generated plots")

    compare_metric_parser = subparsers.add_parser("compare-metric", help="Compare a metric across scenarios in a batch")
    compare_metric_parser.add_argument("--input-root", required=True, help="Batch output root directory")
    compare_metric_parser.add_argument("--metric", required=True, help="Metric column from batch_runs.csv")
    compare_metric_parser.add_argument("--output", help="Optional explicit output CSV path")

    export_article_parser = subparsers.add_parser(
        "export-article",
        help="Export article tables from a batch output root",
    )
    export_article_parser.add_argument("--input-root", required=True, help="Batch output root directory")
    export_article_parser.add_argument("--output-dir", required=True, help="Directory for article-ready CSV tables")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run-experiment":
        result = run_experiment(args.config, args.output_dir)
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-batch":
        result = run_batch(args.config_dir, args.output_root, replicates=args.replicates, seed_step=args.seed_step)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-sweep":
        result = run_parameter_sweep(
            args.base_config_dir,
            args.matrix,
            args.output_root,
            replicates=args.replicates,
            seed_step=args.seed_step,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "build-plots":
        result = build_plots(args.input_dir, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "compare-metric":
        result = compare_metric(args.input_root, args.metric, output_path=args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "export-article":
        result = export_article_tables(args.input_root, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
