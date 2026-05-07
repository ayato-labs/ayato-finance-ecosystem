import uuid
import pytest
from src.infra.tracing import trace_execution, current_trace_id


def test_trace_execution_generates_id():
    """Unit: trace_execution should generate a TraceID and set it in ContextVar."""

    @trace_execution
    def sample_func():
        return current_trace_id.get()

    tid = sample_func()
    assert tid != "root"
    try:
        uuid.UUID(tid)
    except ValueError:
        pytest.fail("TraceID is not a valid UUID")


def test_trace_execution_preserves_nested_id():
    """Unit: Nested traced calls should share the same TraceID."""

    @trace_execution
    def inner():
        return current_trace_id.get()

    @trace_execution
    def outer():
        tid_outer = current_trace_id.get()
        tid_inner = inner()
        return tid_outer, tid_inner

    outer_id, inner_id = outer()
    assert outer_id == inner_id
    assert outer_id != "root"
