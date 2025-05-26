"""Fixtures for adapter tests."""
import pytest
import os


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


@pytest.fixture(autouse=True)
def integration_test_env(monkeypatch):
    """Auto-set integration test environment variables for tests."""
    # Ensure integration tests are off by default
    if "INTEGRATION_TEST_WHATSAPP" not in os.environ:
        monkeypatch.setenv("INTEGRATION_TEST_WHATSAPP", "false")