from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path
from typing import Dict, List

from secure_delivery.config import ExperimentConfig, load_experiment_config
from secure_delivery.crypto.engine import CryptoEngine
from secure_delivery.experiments.analysis import aggregate_batch_results
from secure_delivery.metrics.collector import MetricsCollector
from secure_delivery.policy.backends import EvmPolicyBackend, FilePolicyBackend
from secure_delivery.policy.manager import PolicyManager
from secure_delivery.scheduler.gateway import GatewayScheduler
from secure_delivery.traffic.sources import build_sources


def _build_policy_backend(config: ExperimentConfig):
    if config.policy_backend.backend_type == "file":
        return FilePolicyBackend(config.policy_backend.path)
    if config.policy_backend.backend_type == "evm":
        return EvmPolicyBackend()
    raise ValueError(f"Unsupported policy backend: {config.policy_backend.backend_type}")


def run_experiment(config_path: str, output_dir: str) -> Dict[str, object]:
    config = load_experiment_config(config_path)
    return run_experiment_config(config, config_path=config_path, output_dir=output_dir)


def run_experiment_config(
    config: ExperimentConfig,
    config_path: str,
    output_dir: str,
    replicate_index: int = 0,
    base_run_id: str | None = None,
) -> Dict[str, object]:
    import simpy

    env = simpy.Environment()
    metrics = MetricsCollector(
        run_id=config.run_id,
        scenario=config.scenario,
        scenario_family=config.scenario_family,
        load_profile=config.load_profile,
        seed=config.seed,
        duration_s=config.duration_s,
        config_name=Path(config_path).stem,
    )
    policy_manager = PolicyManager(_build_policy_backend(config))
    policy_manager.switch_version(config.initial_policy_version, at_time=0.0, reason="initial")
    crypto_engine = CryptoEngine(config.crypto_engine)
    gateway = GatewayScheduler(
        env=env,
        config=config,
        policy_manager=policy_manager,
        crypto_engine=crypto_engine,
        metrics=metrics,
        randomizer=random.Random(config.seed),
    )

    for source in build_sources(config, gateway):
        env.process(source.run(env))

    for update in config.policy_updates:
        env.process(_schedule_policy_update(env, policy_manager, update.at_time_s, update.version_id))

    env.run(until=config.duration_s + config.grace_period_s)

    metrics.extend_policy_events(policy_manager.export_events())
    metrics.extend_replay_events(gateway.export_replay_events())

    manifest = {
        "run_id": config.run_id,
        "scenario": config.scenario,
        "scenario_family": config.scenario_family,
        "load_profile": config.load_profile,
        "seed": config.seed,
        "replicate_index": replicate_index,
        "base_run_id": base_run_id or config.run_id,
        "config_path": str(Path(config_path).resolve()),
        "duration_s": config.duration_s,
        "grace_period_s": config.grace_period_s,
        "notes": config.notes,
        "queue_discipline": config.queue_discipline.value,
        "channel": {
            "bandwidth_bps": config.channel.bandwidth_bps,
            "propagation_delay_s": config.channel.propagation_delay_s,
            "loss_probability": config.channel.loss_probability,
            "buffer_size": config.channel.buffer_size,
        },
        "ack": {
            "delay_s": config.ack.delay_s,
            "loss_probability": config.ack.loss_probability,
        },
        "crypto_engine": {
            "mode": config.crypto_engine.mode,
            "measured_stub_scale": config.crypto_engine.measured_stub_scale,
            "priority_mode": config.crypto_engine.priority_mode,
        },
        "policy": policy_manager.export_manifest(),
        "sources": [
            {
                "source_id": source.source_id,
                "message_class": source.message_class.value,
                "generator": source.generator,
                "payload_bytes": source.payload_bytes,
            }
            for source in config.sources
        ],
    }

    files = metrics.export_csv(output_dir, manifest=manifest)
    return {
        "summary": metrics.build_run_summary(),
        "files": files,
        "manifest": manifest,
    }


def run_batch(
    config_dir: str,
    output_root: str,
    replicates: int = 1,
    seed_step: int = 1,
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    config_paths = sorted(Path(config_dir).rglob("*.json"))
    for config_path in config_paths:
        base_config = load_experiment_config(str(config_path))
        for replicate_index in range(replicates):
            seed = base_config.seed + replicate_index * seed_step
            run_suffix = f"{base_config.run_id}_seed_{seed}"
            run_dir = Path(output_root) / run_suffix
            replicate_config = dataclasses.replace(base_config, seed=seed, run_id=run_suffix)
            result = run_experiment_config(
                replicate_config,
                config_path=str(config_path),
                output_dir=str(run_dir),
                replicate_index=replicate_index,
                base_run_id=base_config.run_id,
            )
            results.append(
                {
                    "config": str(config_path),
                    "replicate_index": replicate_index,
                    "seed": seed,
                    "summary": result["summary"],
                    "files": result["files"],
                }
            )

    batch_manifest_path = Path(output_root) / "batch_manifest.json"
    batch_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with batch_manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    aggregate_files = aggregate_batch_results(output_root)
    return {
        "runs": results,
        "aggregate_files": aggregate_files,
    }


def _schedule_policy_update(env, policy_manager: PolicyManager, at_time_s: float, version_id: str):
    if at_time_s > 0:
        yield env.timeout(at_time_s)
    policy_manager.switch_version(version_id, at_time=env.now, reason="scheduled")
