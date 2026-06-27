"""Tests for recommender/skill_scanner.py — the optional SkillSpector integration."""

from recommender import skill_scanner


class TestDisabledByDefault:
    """SkillSpector isn't a pip dependency; scanning must no-op unless explicitly enabled."""

    def test_scanning_disabled_without_opt_in(self, monkeypatch):
        monkeypatch.delenv("VALIDTR_SCAN_SKILLS", raising=False)
        monkeypatch.setattr(skill_scanner, "_skillspector_graph", object())
        assert skill_scanner.scanning_enabled() is False

    def test_scanning_disabled_without_package(self, monkeypatch):
        monkeypatch.setenv("VALIDTR_SCAN_SKILLS", "1")
        monkeypatch.setattr(skill_scanner, "_skillspector_graph", None)
        assert skill_scanner.scanning_enabled() is False

    def test_scan_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.delenv("VALIDTR_SCAN_SKILLS", raising=False)
        assert skill_scanner.scan("foo", "some content") is None

    def test_is_high_risk_false_for_none(self):
        assert skill_scanner.is_high_risk(None) is False


class TestRiskThreshold:
    def test_is_high_risk_above_threshold(self):
        assert skill_scanner.is_high_risk({"risk_score": 95, "severity": "CRITICAL"})

    def test_is_high_risk_below_threshold(self):
        assert not skill_scanner.is_high_risk({"risk_score": 10, "severity": "LOW"})


class TestScanWiring:
    def test_scan_invokes_graph_and_cleans_up_tempfile(self, monkeypatch, tmp_path):
        monkeypatch.setenv("VALIDTR_SCAN_SKILLS", "1")

        captured = {}

        class _FakeGraph:
            def invoke(self, payload):
                captured["payload"] = payload
                import os
                assert os.path.exists(payload["input_path"])
                return {"risk_score": 42, "severity": "MEDIUM"}

        monkeypatch.setattr(skill_scanner, "_skillspector_graph", _FakeGraph())
        result = skill_scanner.scan("my-skill", "---\nname: my-skill\n---\nbody")

        assert result == {"risk_score": 42, "severity": "MEDIUM"}
        assert captured["payload"]["use_llm"] is True
        import os
        assert not os.path.exists(captured["payload"]["input_path"])

    def test_scan_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setenv("VALIDTR_SCAN_SKILLS", "1")

        class _FailingGraph:
            def invoke(self, payload):
                raise RuntimeError("boom")

        monkeypatch.setattr(skill_scanner, "_skillspector_graph", _FailingGraph())
        assert skill_scanner.scan("my-skill", "content") is None
