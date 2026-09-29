from experiment_controller.config import ExperimentConfig


def test_from_dict_parses_prd_example():
    config = ExperimentConfig.from_dict({
        "experiment": {"name": "benchmark-001"},
        "dataset": {"file": "data/sample.csv"},
        "protocol": "binary",
        "workers": {"language": "cpp", "count": 4},
        "strategy": {"type": "moving_average"},
        "replay": {"mode": "maximum"},
    })
    assert config.name == "benchmark-001"
    assert config.dataset_file == "data/sample.csv"
    assert config.protocol == "binary"
    assert config.worker_language == "cpp"
    assert config.worker_count == 4
    assert config.strategy == "moving_average"
    assert config.replay_mode == "maximum"


def test_defaults_applied_when_optional_sections_missing():
    config = ExperimentConfig.from_dict({
        "experiment": {"name": "minimal"},
        "dataset": {"file": "data/sample.csv"},
    })
    assert config.protocol == "json"
    assert config.worker_language == "python"
    assert config.worker_count == 1
    assert config.strategy == "passthrough"
    assert config.replay_mode == "maximum"


def test_rejects_invalid_protocol():
    import pytest
    with pytest.raises(ValueError):
        ExperimentConfig(name="x", dataset_file="d.csv", protocol="xml")


def test_rejects_invalid_worker_count():
    import pytest
    with pytest.raises(ValueError):
        ExperimentConfig(name="x", dataset_file="d.csv", worker_count=0)
