import json
import time
from typing import Any


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


class FakeModels:
    def __init__(self, return_values: list[str] | None = None):
        self.return_values = return_values or []
        self.call_count = 0

    def generate_content(self, model: str, contents: str, config: Any = None) -> FakeResponse:
        self.call_count += 1
        if self.call_count <= len(self.return_values):
            val = self.return_values[self.call_count - 1]
            if val == "__HUNG__":
                # Simulate a long-running call that would trigger a timeout if not handled
                time.sleep(1)  # In unit tests, we want this small but detectable
            return FakeResponse(val)
        return FakeResponse(json.dumps({"mappings": []}))


class FakeGeminiClient:
    """
    A mock-less Fake Client for google-genai SDK.
    Simulates: client.models.generate_content(...)
    """

    def __init__(self, return_values: list[str] | None = None):
        self.models = FakeModels(return_values)


def create_mapping_response(mappings: list[dict[str, Any]]) -> str:
    """Helper to create valid JSON responses for the fake client."""
    return json.dumps({"mappings": mappings})
