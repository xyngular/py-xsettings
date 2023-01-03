from xsentinels.sentinel import Sentinel
from typing import Any, Protocol
from .settings import SettingsField, Settings


# class TryNextRetriever(Sentinel):
#     pass


# todo: remove use of `SettingsRetrieverCallable`

class SettingsRetriever(Protocol):

    """
    The purpose of the base SettingsRetrieverCallable is to define the base-interface for
    retrieving settings values.

    The retriever can be any callable, by default `xsettings.settings.Settings` will use
    an instance of `SettingsRetriever`. It provides a default retriever implementation,
    see that class for more details on what happens by default.
    """

    def __call__(self, *, field: SettingsField, settings: Settings) -> Any:
        """
        This is how the Settings field, when retrieving its value, will call us.
        You must override this (or simply use a normal function with the same parameters).

        This convention gives flexibility: It allows simple methods to be retrievers,
        or more complex objects to be them too (via __call__).

        Args:
            field: Field we need to retrieve.
            settings: Related Settings object that has the field we are retrieving.

        Returns: Retrieved value, or None if no value can be found.
            By default, we return `None` (as we are a basic/abstract retriever)
        """
        raise NotImplementedError(
            "Abstract Method - Must implement `__call__` function with correct arguments."
        )


class PropertyRetriever(SettingsRetriever):
    """
    What is used to wrap a `@property` on a Settings subclass.
    We don't use the default retriever for any defined properties on a Settings subclass,
    we instead use `PropertyRetriever`; as the property it's self is considered the 'retriever'.

    Will first check the property getter function when retrieving a value before
    doing anything else (such as using the default_value for the field, etc, etc).
    """
    property_retriever: property

    def __init__(self, property_retriever: property):
        self.property_retriever = property_retriever

    def __call__(self, *, field: SettingsField, settings: 'Settings') -> Any:
        return self.property_retriever.__get__(settings, type(settings))
