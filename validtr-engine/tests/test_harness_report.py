import json
import os

from estimator.harness_report import HarnessReport, read_harness_report

SAMPLE = {
    "harness_overhead_tokens": 4213,
    "components": [
        {"kind": "system_prompt", "name": "system", "tokens": 412},
        {"kind": "mcp_server", "name": "filesystem", "tokens": 1840},
    ],
    "measured_input_tokens": 8123,
    "measured_output_tokens": 1004,
    "avg_output_tokens_per_turn": 251,
    "tokenizer": "anthropic",
}


def test_read_valid_report(tmp_path):
    path = os.path.join(tmp_path, "harness-report.json")
    with open(path, "w") as f:
        json.dump(SAMPLE, f)
    report = read_harness_report(path)
    assert isinstance(report, HarnessReport)
    assert report.harness_overhead_tokens == 4213
    assert report.measured_total_tokens == 8123 + 1004
    assert report.components[1].name == "filesystem"


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
        json.dump({"harness_overhead_tokens": 100}, f)
    report = read_harness_report(path)
    assert report.harness_overhead_tokens == 100
    assert report.measured_total_tokens == 0
    assert report.components == []
