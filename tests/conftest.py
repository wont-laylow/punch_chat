import pytest

pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(autouse=True)
def suppress_logging(monkeypatch):
    """Lower logging during tests to reduce noise."""
    import logging
    logging.getLogger().setLevel(logging.WARNING)
    yield
