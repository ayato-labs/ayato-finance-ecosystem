import pytest
import uuid
from loguru import logger
from src.core.tracing import trace_execution

@trace_execution
def sample_func(a, b):
    return a + b

@trace_execution
def failing_func():
    raise ValueError("Expected failure")

def test_trace_execution_success():
    """Test that the decorator correctly handles successful execution and logging."""
    result = sample_func(1, 2)
    assert result == 3

def test_trace_execution_failure():
    """Test that the decorator correctly handles and logs failures, then re-raises."""
    with pytest.raises(ValueError, match="Expected failure"):
        failing_func()

def test_trace_execution_complex_args():
    """Test with complex data structures to ensure serialization doesn't crash logging."""
    @trace_execution
    def complex_func(data):
        return len(data)
    
    large_data = {"key": [i for i in range(100)], "meta": {"id": uuid.uuid4()}}
    result = complex_func(large_data)
    assert result == 2
