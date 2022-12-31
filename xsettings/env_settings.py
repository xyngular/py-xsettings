import os
from typing import Any

from xsettings.fields import SettingsField
from xsettings.settings import SettingsRetriever, Settings


class EnvSettingsRetriever(SettingsRetriever):
    def __call__(self, *, field: SettingsField, settings: 'Settings') -> Any:
        return os.environ.get(field.name)


class EnvSettings(Settings, retrievers=EnvSettingsRetriever()):
    pass
