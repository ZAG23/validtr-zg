"""Tests for RunResponse harness_projection field."""

from api.routes.run import RunResponse, StackResponse


def test_run_response_has_projection_field_default_empty():
    resp = RunResponse(
        run_id="abc",
        score=90.0,
        passed=False,
        total_attempts=1,
        best_attempt=1,
        stack=StackResponse(),
        dimensions=[],
        attempts=[],
        artifact_count=0,
        artifacts={},
    )
    assert resp.harness_projection.rows == []
    dumped = resp.model_dump()
    assert "harness_projection" in dumped
    assert dumped["harness_projection"]["rows"] == []
