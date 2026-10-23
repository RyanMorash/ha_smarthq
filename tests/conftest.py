"""Pytest fixtures for the SmartHQ integration."""

from __future__ import annotations

from pathlib import Path
from shutil import copytree

import pytest
from pytest_homeassistant_custom_component.common import get_test_config_dir

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom integrations from this repository."""
    return


@pytest.fixture
def hass_config_dir(tmp_path: Path) -> str:
    """Point Home Assistant at a config dir that contains this integration."""
    copytree(get_test_config_dir(), tmp_path, symlinks=True, dirs_exist_ok=True)
    custom = tmp_path / "custom_components"
    custom.mkdir(exist_ok=True)
    link = custom / "smarthq"
    if not link.exists():
        link.symlink_to(
            Path(__file__).resolve().parents[1] / "custom_components" / "smarthq"
        )
    return str(tmp_path)
