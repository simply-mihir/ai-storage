"""Tests for deprecated environment variable alias resolution."""

from __future__ import annotations

import warnings
from unittest.mock import patch

import pytest

from storage_advisor.integrations.bedrock import _env_with_alias


class TestEnvAlias:
    """Verify that old env var names resolve with a deprecation warning."""

    def test_new_name_takes_precedence(self):
        with patch.dict("os.environ", {"LLM_MODEL_ID": "new-model"}):
            assert _env_with_alias("LLM_MODEL_ID") == "new-model"

    def test_old_name_resolves_when_new_absent(self):
        with patch.dict("os.environ", {"BEDROCK_MODEL_ID": "old-model"}, clear=True):
            with pytest.warns(DeprecationWarning, match="BEDROCK_MODEL_ID.*LLM_MODEL_ID"):
                result = _env_with_alias("LLM_MODEL_ID")
            assert result == "old-model"

    def test_new_name_preferred_over_old(self):
        env = {"LLM_FALLBACK_KEY": "new-key", "GROQ_API_KEY": "old-key"}
        with patch.dict("os.environ", env):
            result = _env_with_alias("LLM_FALLBACK_KEY")
            assert result == "new-key"

    def test_fallback_key_alias_warns(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "old-key"}, clear=True):
            with pytest.warns(DeprecationWarning, match="GROQ_API_KEY.*LLM_FALLBACK_KEY"):
                result = _env_with_alias("LLM_FALLBACK_KEY")
            assert result == "old-key"

    def test_returns_default_when_both_absent(self):
        with patch.dict("os.environ", {}, clear=True):
            result = _env_with_alias("LLM_MODEL_ID", "default-val")
            assert result == "default-val"

    def test_returns_none_when_no_default(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _env_with_alias("LLM_FALLBACK_KEY") is None

    def test_no_warning_when_new_name_set(self):
        with patch.dict("os.environ", {"LLM_MODEL_ID": "m"}, clear=True):
            with warnings.catch_warnings():
                warnings.simplefilter("error", DeprecationWarning)
                _env_with_alias("LLM_MODEL_ID")
