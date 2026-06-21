import json
import os

from estimator.harness_report import HarnessReport, read_harness_report

SAMPLE = {
    "system_prompt_tokens": 412,
    "measured_input_tokens": 8123,
    "measured_output_tokens": 1004,
    "turns": 4,
    "mcp_server_names": ["filesystem", "github"],
    "skill_names": ["k8skill"],
}


def test_read_valid_report(tmp_path):
    path = os.path.join(tmp_path, "harness-report.json")
    with open(path, "w") as f:
        json.dump(SAMPLE, f)
    report = read_harness_report(path)
    assert isinstance(report, HarnessReport)
    assert report.system_prompt_tokens == 412
    assert report.measured_total_tokens == 8123 + 1004
    assert report.turns == 4
    assert report.mcp_server_names == ["filesystem", "github"]
    assert report.skill_names == ["k8skill"]


def test_missing_file_returns_none(tmp_path):
    assert read_harness_report(os.path.join(tmp_path, "nope.json")) is None


def test_malformed_file_returns_none(tmp_path):
    path = os.path.join(tmp_path, "harness-report.json")
    with open(path, "w") as f:
        f.write("{not json")
    assert read_harness_report(path) is None


def test_partial_report_fills_defaults(tmp_path):
    path = os.path.join(tmp_path, "harness-report.json")
    with open(path, "w") as f:
        json.dump({"system_prompt_tokens": 100}, f)
    report = read_harness_report(path)
    assert report.system_prompt_tokens == 100
    assert report.measured_total_tokens == 0
    assert report.turns == 1  # default
    assert report.mcp_server_names == []
