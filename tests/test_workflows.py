import hashlib
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


def test_wirenboard_sms_rule_is_documented_and_included() -> None:
    rule = Path("wirenboard/send_sms.js")
    docs = Path("home-assistant-app/DOCS.md").read_text(encoding="utf-8")

    assert rule.is_file()
    assert 'defineVirtualDevice("sms_sender"' in rule.read_text(encoding="utf-8")
    assert "обязательно" in docs.casefold()
    assert "send_sms.js" in docs


def test_brand_assets_are_included() -> None:
    wb = Path("hotspot/assets/wb.svg").read_text(encoding="utf-8")
    unifi = Path("hotspot/assets/unifi.png").read_bytes()

    assert "<svg" in wb
    assert "<script" not in wb.lower()
    assert "javascript:" not in wb.lower()
    assert unifi.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(unifi).hexdigest() == (
        "b0588853cf91a58aa0dfdeaf724b6d4fae6a0202cfe523ba08a17bd7b89c6f53"
    )
    usb = Path("hotspot/assets/usb.png").read_bytes()
    assert usb.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(usb).hexdigest() == (
        "c4af073cdc0903e532298d37a22315ba7908970553bf044f642615223276c7bd"
    )
