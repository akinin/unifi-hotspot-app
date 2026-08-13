from pathlib import Path

import yaml


def test_github_workflows_are_valid_yaml() -> None:
    workflows = sorted(Path(".github/workflows").glob("*.yaml"))

    assert workflows
    for workflow in workflows:
        parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict), f"{workflow} must contain a YAML mapping"


def test_home_assistant_ingress_entry_is_relative() -> None:
    config = yaml.safe_load(Path("home-assistant-app/config.yaml").read_text(encoding="utf-8"))

    assert config["ingress"] is True
    assert config["ingress_entry"] == "admin/"
    assert not config["ingress_entry"].startswith("/")
