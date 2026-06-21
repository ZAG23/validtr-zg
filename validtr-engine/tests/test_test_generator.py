"""Tests for TestGenerator._parse_junit_xml."""

import os
import tempfile

import pytest

from models.test_result import TestStatus
from test_generator.engine import TestGenerator


def _write_junit(tmp_path: str, xml: str) -> str:
    path = os.path.join(tmp_path, "junit.xml")
    with open(path, "w") as f:
        f.write(xml)
    return path


class TestParseJunitXml:
    """Tests for _parse_junit_xml method."""

    @pytest.fixture
    def generator(self):
        """Create a TestGenerator with a fake provider (not used for parsing)."""

        class FakeProvider:
            pass

        return TestGenerator(provider=FakeProvider())

    @pytest.fixture
    def tmp_path(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    def test_parse_mixed_results(self, generator, tmp_path):
        xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="5">
  <testcase classname="tests.test_example" name="test_add" time="0.01"/>
  <testcase classname="tests.test_example" name="test_subtract" time="0.02">
    <failure message="assert 1 == 2">boom</failure>
  </testcase>
  <testcase classname="tests.test_example" name="test_multiply" time="0.01"/>
  <testcase classname="tests.test_example" name="test_divide" time="0.0">
    <error message="ZeroDivisionError">setup failed</error>
  </testcase>
  <testcase classname="tests.test_example" name="test_modulo" time="0.0">
    <skipped message="not implemented"/>
  </testcase>
</testsuite></testsuites>"""
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "runner log")
        assert result.total == 5
        assert result.passed == 2
        assert result.failed == 1
        assert result.errors == 1
        assert result.skipped == 1
        assert result.pass_rate == pytest.approx(2 / 5)
        assert result.runner_output == "runner log"

    def test_parse_all_passed(self, generator, tmp_path):
        xml = """<testsuite name="pytest" tests="3">
  <testcase classname="t" name="test_a"/>
  <testcase classname="t" name="test_b"/>
  <testcase classname="t" name="test_c"/>
</testsuite>"""
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "")
        assert result.total == 3
        assert result.passed == 3
        assert result.failed == 0
        assert result.pass_rate == 1.0

    def test_parse_all_failed(self, generator, tmp_path):
        xml = """<testsuite tests="2">
  <testcase name="test_x"><failure message="x">e</failure></testcase>
  <testcase name="test_y"><failure message="y">e</failure></testcase>
</testsuite>"""
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "")
        assert result.total == 2
        assert result.passed == 0
        assert result.failed == 2
        assert result.pass_rate == 0.0

    def test_parse_no_tests_collected(self, generator, tmp_path):
        xml = '<testsuite name="pytest" tests="0"></testsuite>'
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "no tests ran")
        assert result.total == 0
        assert result.pass_rate == 0.0
        assert result.tests == []

    def test_missing_report_is_error(self, generator, tmp_path):
        # No file written: a crashed/uncollectable run produces no report.
        missing = os.path.join(tmp_path, "does-not-exist.xml")
        result = generator._parse_junit_xml(missing, "traceback here")
        assert result.total == 1
        assert result.errors == 1
        assert result.tests[0].status == TestStatus.ERROR
        assert result.pass_rate == 0.0
        assert result.runner_output == "traceback here"

    def test_malformed_report_is_error(self, generator, tmp_path):
        result = generator._parse_junit_xml(_write_junit(tmp_path, "<not-xml"), "log")
        assert result.errors == 1
        assert result.tests[0].status == TestStatus.ERROR

    def test_parse_preserves_test_names(self, generator, tmp_path):
        xml = """<testsuite tests="2">
  <testcase classname="tests.test_models.TestTask" name="test_create"/>
  <testcase classname="tests.test_models.TestTask" name="test_validate">
    <failure message="bad">e</failure>
  </testcase>
</testsuite>"""
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "")
        names = [t.name for t in result.tests]
        assert "tests.test_models.TestTask::test_create" in names
        assert "tests.test_models.TestTask::test_validate" in names

    def test_parse_statuses_correct(self, generator, tmp_path):
        xml = """<testsuite tests="4">
  <testcase name="test_one"/>
  <testcase name="test_two"><failure message="f">e</failure></testcase>
  <testcase name="test_three"><error message="er">e</error></testcase>
  <testcase name="test_four"><skipped message="s"/></testcase>
</testsuite>"""
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "")
        status_map = {t.name: t.status for t in result.tests}
        assert status_map["test_one"] == TestStatus.PASSED
        assert status_map["test_two"] == TestStatus.FAILED
        assert status_map["test_three"] == TestStatus.ERROR
        assert status_map["test_four"] == TestStatus.SKIPPED

    def test_duration_parsed(self, generator, tmp_path):
        xml = '<testsuite tests="1"><testcase name="t" time="0.25"/></testsuite>'
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "")
        assert result.tests[0].duration_ms == 250

    def test_pass_rate_calculation(self, generator, tmp_path):
        xml = """<testsuite tests="5">
  <testcase name="test_1"/>
  <testcase name="test_2"/>
  <testcase name="test_3"/>
  <testcase name="test_4"><failure message="f">e</failure></testcase>
  <testcase name="test_5"><skipped message="s"/></testcase>
</testsuite>"""
        result = generator._parse_junit_xml(_write_junit(tmp_path, xml), "")
        assert result.total == 5
        assert result.pass_rate == pytest.approx(3 / 5)
