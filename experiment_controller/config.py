"""Experiment configuration (PRD section 28): parses the experiment YAML/dict config."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import yaml


@dataclass
class ExperimentConfig:
    name: str
    dataset_file: str
    protocol: str = "json"  # "json" | "binary"
    worker_language: str = "python"  # "python" | "cpp"
    worker_count: int = 1
    strategy: str = "passthrough"
    strategy_kwargs: dict = field(default_factory=dict)
    replay_mode: str = "maximum"  # "original" | "accelerated" | "maximum"
    speed_multiplier: float = 1.0
    heartbeat_interval: float = 5.0
    completion_timeout: float = 30.0
    cpp_worker_binary: str = "workers/cpp/build/pulsex_cpp_worker"
    random_seed: int | None = None

    def __post_init__(self):
        if self.protocol not in ("json", "binary"):
            raise ValueError(f"protocol must be 'json' or 'binary', got {self.protocol!r}")
        if self.worker_language not in ("python", "cpp"):
            raise ValueError(f"worker_language must be 'python' or 'cpp', got {self.worker_language!r}")
        if self.worker_count < 1:
            raise ValueError("worker_count must be >= 1")

    @staticmethod
    def from_dict(d: dict) -> "ExperimentConfig":
        workers = d.get("workers", {})
        strategy = d.get("strategy", {})
        replay = d.get("replay", {})
        return ExperimentConfig(
            name=d["experiment"]["name"],
            dataset_file=d["dataset"]["file"],
            protocol=d.get("protocol", "json"),
            worker_language=workers.get("language", "python"),
            worker_count=workers.get("count", 1),
            strategy=strategy.get("type", "passthrough"),
            strategy_kwargs=strategy.get("kwargs", {}),
            replay_mode=replay.get("mode", "maximum"),
            speed_multiplier=replay.get("speed_multiplier", 1.0),
            heartbeat_interval=workers.get("heartbeat_interval", 5.0),
            completion_timeout=d.get("completion_timeout", 30.0),
            cpp_worker_binary=workers.get("cpp_binary", "workers/cpp/build/pulsex_cpp_worker"),
            random_seed=d.get("random_seed"),
        )

    @staticmethod
    def from_yaml(path: str) -> "ExperimentConfig":
        with open(path) as f:
            return ExperimentConfig.from_dict(yaml.safe_load(f))

    def as_dict(self) -> dict:
        return asdict(self)
