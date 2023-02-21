from xsettings.settings import BaseSettings
from .retreivers import EnvVarRetriever


class EnvVarSettings(BaseSettings, default_retrievers=EnvVarRetriever()):
    """
    Base subclass of `xsettings.settings.BaseSettings` with the default retriever
    set as the `xsettings.retrievers.EnvVarRetriever`.

    This means when a settings field is defined without a retriever
    it will use the `xsettings.retrievers.EnvVarRetriever` by default to retriever its value.

    The `xsettings.retrievers.EnvVarRetriever` will check `os.environ` dict for the values.

    It first tries with the plain name of the field.

    If a value is not found (not even an empty string) it will next try looking up the env-var
    by upper-casing the name
    (as it's extremely common to use all upper-case vars for environmental var names).

    If it still can't be found then None will be returned and the system will look
    at the next retriever and/or the default value for the field as necessary/needed.
    """
    pass
