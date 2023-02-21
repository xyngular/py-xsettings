from xsentinels.sentinel import Sentinel
from typing import Any, Protocol, Callable
from .settings import SettingsField, BaseSettings
import os

# Tell pdoc3 to document the normally private method __call__.
__pdoc__ = {
    "SettingsRetrieverProtocol.__call__": True,
}


class SettingsRetrieverProtocol(Protocol):
    """
    The purpose of the base SettingsRetrieverProtocol is to define the base-interface for
    retrieving settings values.

    The retriever can be any callable, by default `xsettings.settings.BaseSettings` will
    not use a default retriever; normally a subclass or some sort of generic
    base-subclass of `xsettings.settings.BaseSettings` will be used to specify a default
    retriever to use.

    A retriever can also be specified per-field via `xsettings.fields.SettingsField.retriever`.

    Retrievers are tried in a specific order, the first one with a non-None retrieved value
    is the one that is used.

    You can also add one or more retrievers to this `instance` of settings via the
    `xsettings.setting.BaseSettings.add_instance_retrievers` method
    (won't modify default_retrievers for the entire class, only modifies this specific instance).

    .. note:: As a side-note, values set directly on Setting instances are first checked for and
        used if one is found.
        Checks self first, if not found will next check `xinject.context.XContext.dependency_chain`
        (looking at each instance currently in the dependency-chain, see link for details).

        If value can't be found the retrievers are next checked.

    After the individual field retrievers are consulted, instance retrievers are checked next
    before finally checking the default-retrievers for the entire class.

    They are checked in the order added.

    Child dependencies (of the same exactly class/type) in the
    `xinject.context.XContext.dependency_chain` will also check these instance-retrievers.

    The dependency chain is checked in the expected order of first consulting self,
     then the chain in most recent parent first order.

    For more details on how parent/child dependencies work see
    `xinject.context.XContext.dependency_chain`.

    After the dependency-chain is checked, the default-retrievers are checked
    in python's `mro` (method-resolution-order), checking its own class first
    before checking any super-classes for default-retrievers.
    """

    def __call__(self, *, field: SettingsField, settings: BaseSettings) -> Any:
        """
        This is how the BaseSettings field, when retrieving its value, will call us.
        You must override this (or simply use a normal function with the same parameters).

        This convention gives flexibility: It allows simple methods to be retrievers,
        or more complex objects to be them too (via __call__).

        Args:
            field: Field we need to retrieve.
            settings: Related BaseSettings object that has the field we are retrieving.

        Returns: Retrieved value, or None if no value can be found.
            By default, we return `None` (as we are a basic/abstract retriever)
        """
        raise NotImplementedError(
            "Abstract Method - Must implement `__call__` function with correct arguments."
        )


class EnvVarRetriever(SettingsRetrieverProtocol):
    """ Used to  """
    def __call__(self, *, field: SettingsField, settings: 'BaseSettings') -> Any:
        environ = os.environ

        # First try to get field using the same case as the original field name:
        value = environ.get(field.name, None)
        if value is not None:
            return value

        # If we did not get any value back (not even a blank-string),
        # attempt lookup by upper-casing the name
        # (as upper-case is extremely common for env-vars):
        return environ.get(field.name.upper())


