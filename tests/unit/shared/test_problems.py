import sys
from pathlib import Path

# The V2 runtime is a top-level `src` package without an editable install, so
# expose the repository root when pytest is invoked from the worktree.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.shared.errors.problems import Problem


def test_problem_serializes_approved_fields() -> None:
    problem = Problem(
        code="RESOURCE_NOT_FOUND",
        status=404,
        title="Resource not found",
        detail="The resource is unavailable",
        retryable=False,
    )
    assert problem.model_dump()["code"] == "RESOURCE_NOT_FOUND"
    assert problem.model_dump()["status"] == 404


def test_problem_default_context_is_empty() -> None:
    problem = Problem(
        code="INTERNAL",
        status=500,
        title="Internal",
        detail="detail",
        retryable=True,
    )
    assert problem.model_dump()["context"] == {}


def test_problem_preserves_optional_context() -> None:
    problem = Problem(
        code="INTERNAL",
        status=500,
        title="Internal",
        detail="detail",
        retryable=True,
        context={"run_id": "run-123"},
    )
    assert problem.model_dump()["context"] == {"run_id": "run-123"}
