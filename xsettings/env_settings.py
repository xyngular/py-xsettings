import os
from typing import Any

from xsettings.fields import SettingsField
from xsettings.settings import Settings
from xsettings.retreivers import SettingsRetriever


class EnvSettingsRetriever(SettingsRetriever):
    def __call__(self, *, field: SettingsField, settings: 'Settings') -> Any:
        return os.environ.get(field.name)


class EnvSettings(Settings, default_retrievers=EnvSettingsRetriever()):
    pass
