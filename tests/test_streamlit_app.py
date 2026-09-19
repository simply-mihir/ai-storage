"""Smoke tests for the Streamlit application."""

from streamlit.testing.v1 import AppTest

_APP_PATH = "../app/streamlit_app.py"


def test_app_loads():
    at = AppTest.from_file(_APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception


def test_tab_count():
    at = AppTest.from_file(_APP_PATH, default_timeout=30)
    at.run()
    assert len(at.tabs) == 7
