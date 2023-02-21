from .settings import BaseSettings
from .fields import SettingsField
from .env_settings import EnvVarSettings


Settings = BaseSettings
"""
Deprecated; Use `BaseSettings` instead.

Here for backwards compatability, renamed original class from `Settings` to `BaseSettings`.
"""
