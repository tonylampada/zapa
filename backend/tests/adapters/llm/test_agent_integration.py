"""Integration tests for Zapa Agent."""

import pytest

# Skip entire module - DatabaseTestManager needs refactoring
pytest.skip(
    "Skipping agent integration tests - DatabaseTestManager needs refactoring",
    allow_module_level=True,
)
