"""

See doc-comments for `Settings` below.


"""

from typing import Dict, Any, Union, TypeVar

from xinject import Dependency
from xsentinels import Default

from xsettings.fields import generate_setting_fields, SettingsField, SettingsClassProperty

T = TypeVar("T")


# It's both an attribute and a value error
# (attribute is missing and/or value has some other issue)
# `AttributeError` helps pdoc3 know that there is no value safely
# (ie: it will continue to generate docs).
class SettingsValueError(ValueError, AttributeError):
    pass


class SettingsRetrieverCallable:

    """
    The purpose of the base SettingsRetrieverCallable is to define the base-interface for
    retrieving settings values.

    The retriever can be any callable, by default `xsettings.settings.Settings` will use
    an instance of `SettingsRetriever`. It provides a default retriever implementation,
    see that class for more details on what happens by default.
    """

    def __call__(self, field: SettingsField, /, *, settings: 'Settings') -> Any:
        """
        This is how the Settings field, when retrieving its value, will call us.
        You must override this (or simply use a normal function with the same parameters).

        Args:
            field: Field we need to retrieve.
            settings: Related Settings object that has the field we are retrieving.

        Returns: Retrieved value, or None if no value can be found.
        """
        raise NotImplementedError(
            "You must implement `__call__` in your `SettingsRetrieverCallable` interface."
        )


class SettingsRetriever(SettingsRetrieverCallable):
    """
    The purpose of the base SettingsRetriever is to define the base-interface for retrieving
    settings values along with a default/basic implementation.

    If a setting is required (default) and there is no default value provided,
    we will raise an `SettingsValueError` (which inherits from standard ValueError).

    (Note To Kevin: You used a standard `ValueError`... I guess I was thinking it might be nice
    to distinguish it, so I am using a SettingsValueError that inherits from ValueError).

    Retriever object to use to retrieve settings from some source.
    By default, it's the base `SettingsRetriever` which has basic logic in it that handles:

    - default values
    - missing values

    Subclasses would normally just need to override the `SettingsRetriever.retrieve_value`
    method and retrieve the setting value requested.

    But they can also override other methods to customize the behavior more if needed.
    """

    def __call__(self, field: SettingsField, /, *, settings: 'Settings') -> Any:
        """
        This is how the Settings field, when retrieving its value, will call us.
        We turn around and simply call our `get` method.
        Args:
            field: Field we need to retrieve.
            settings: Related Settings object that has the field we are retrieving.

        Returns: Retrieved value, or None if no value can be found.
        """
        return self.get(field, settings=settings)

    def get(self, field: SettingsField, /, *, settings: 'Settings') -> Any:
        """
        This is the standard 'get' method for `SettingsRetriever` subclasses.

        We will first call `self.retrieve_value`.

        If that returns a None, we next check for a `default_value` on the field and use that.
        If the `default_value` is a property (has a `__get__`), we will call `__get__` on
        the `default_value` and use the returned value.

        If we still have a None value after all that, we call `handle_missing_value`.
        Normally `handle_missing_value` will raise an exception if the field is required
        (fields are required by default). You can override the method to change the behavior
        if you wish

        Args:
            field: Field we need to retrieve.
            settings: Related Settings object that has the field we are retrieving.

        Returns: Retrieved value, or None if no value can be found.
        """
        value = self.retrieve_value(field)
        if value is None:
            value = field.default_value
            if value and hasattr(value, '__get__'):
                value = value.__get__(settings, type(settings))
        if value is None:
            value = self.handle_missing_value(field, context_msg='while retrieving value')
        return value

    def retrieve_value(self, field: SettingsField) -> Any:
        return None

    def handle_missing_value(self, field: SettingsField, context_msg: str = None) -> Any:
        if field.required:
            # Data-classes will print out all their fields by default, should give good info!
            msg = f"Missing value for {field}"
            if context_msg:
                msg = f"{msg}, {context_msg}"

            raise SettingsValueError(f'{msg}.')
        return None


class PropertyRetriever(SettingsRetriever):
    """
    What is used to wrap a `@property` on a Settings subclass.
    We don't use the default retrieve for properties, we instead use `PropertyRetriever`,
    as the property it's self is basically the 'retriever'.

    Will first check the property getter function when retrieving a value before
    doing anything else (such as using the default_value for the field, etc, etc).
    """
    property_retriever: property

    def __init__(self, property_retriever: property):
        self.property_retriever = property_retriever

    def get(self, field: SettingsField, /, *, settings: 'Settings') -> Any:
        """ Have to override `get` instead of `retrieve_value` to get `settings` param;
            which is needed by the property to know what instance it's being called on.
        """
        value = self.property_retriever.__get__(settings, type(settings))
        if value is not None:
            return value
        return super().get(field, settings=settings)


def _assert_settings_field_inheritance_not_allowed(bases):
    for base in bases:
        if getattr(base, '_setting_fields', None):
            raise AssertionError("Settings Field inheritance not supported")


def _load_default_retriever(bases, default_retriever):
    if default_retriever:
        return default_retriever

    # Look for a retrieve in base classes.
    for base in bases:
        if default_retriever := getattr(base, '_default_retriever', None):
            return default_retriever

    # Fallback to using a SettingsRetriever instance.
    return SettingsRetriever()


class _SettingsMeta(type):
    """Represents the class-type instance/obj of the `Settings` class.
    Any attributes in this object will be class-level attributes of
    a class or subclass of `Settings`.

    ie: A `_SettingsMeta` instance is created each time a new Settings or Settings subclass
        type/class is created (it represents the class/type its self).
    """

    # This will be a class-attribute on the normal Settings class.
    _setting_fields: Dict[str, SettingsField] = None
    _default_retriever: SettingsRetrieverCallable = None

    def __new__(
        mcls,
        name,
        bases,
        attrs: Dict[str, Any],
        *,
        default_retriever: SettingsRetrieverCallable = None,
        **kwargs,
    ):
        """
        The instance of `mcls` is a Settings class or subclass
        (not Settings object, the class its self).

        Objective in this method is to create a set of SettingsField object(s) for use by the new
        Settings sub-class, and set their default-settings correctly if the user did not
        provide an explict setting.

        Args:
            name: Name of the new class
            bases: Base-classes, in left-to-right order.
            attrs: Attributes provided on class at class definition time.

            default_retriever: Used to retrieve values for a `SettingsField` if Field has
                no set retriever (ie: not set directly be user).

                This can be passed in like so:
                `class MySettings(Settings, default_retriever=...)`

            **kwargs: Any extra arguments get supplied to the super-class-type.
        """
        if __name__ == attrs['__module__']:
            # Skip any Settings classes created in this module
            cls = super().__new__(mcls, name, bases, attrs, **kwargs)  # noqa
            return cls

        _assert_settings_field_inheritance_not_allowed(bases)

        default_retriever = _load_default_retriever(bases, default_retriever)
        setting_fields = generate_setting_fields(attrs, default_retriever)
        attrs["_default_retriever"] = default_retriever
        attrs["_setting_fields"] = setting_fields

        for k in setting_fields.keys():
            attrs.pop(k, None)

        # This creates the new Settings class/subclass.
        cls = super().__new__(mcls, name, bases, attrs, **kwargs)  # noqa

        for field in setting_fields.values():
            field.source_class = cls

        return cls

    def __getattr__(self, key: str):
        """
        We will return a `ClassProperty` object setup to retrieve the value asked for as
        a type of forward-reference/pointer. It will, when set into an object or class,
        retrieve the value from self for `key` when it's asked too.

        Example:

        >>> class MySettings(Settings):
        ...    my_url_setting: str
        >>>
        >>> class SomeClass:
        ...    some_attr = MySettings.my_url_setting
        >>>
        >>> MySettings.grab().my_url_setting = "my-url"
        >>> assert SomeClass.some_attr == "my-url"
        """
        if key.startswith("_"):
            return super().__getattr__(key)

        setting_fields = self._setting_fields
        if key not in setting_fields:
            raise AttributeError(
                f"Have no class-attribute or defined SettingsField for "
                f"attribute name ({key}) on Settings subclass ({self})."
            )

        @SettingsClassProperty
        def lazy_retriever(calling_cls):
            return getattr(self.grab(), key)

        return lazy_retriever

    def __setattr__(self, key: str, value: Union[SettingsField, Any]):
        """
        Setting any public-attribute on class is currently only supported for changing
        an existing field's default value.

        We may do something more with this in the future, for now leaving other
        use-cases unsupported (such as creating new setting fields on already created subclasses).
        """
        if key.startswith("_"):
            return super().__setattr__(key, value)

        # Set default value of an existing field with `key` attribute-name:
        existing_settings_field = self._setting_fields.get(key)
        if existing_settings_field:
            existing_settings_field.default_value = value
            return

        # Right now we don't support making new SettingField's after the Settings subclass
        # has been created. We could decide to do that in the future, but for now we
        # are keeping things simpler.
        raise AttributeError(
            f"Setting new fields on Settings subclass unsupported currently, attempted to "
            f"set key ({key}) with value ({value})."
        )


class Settings(Dependency, metaclass=_SettingsMeta, default_retriever=SettingsRetriever()):
    """
    Base Settings class. For all class properties defined there will be a corresponding
    _settings_field["name"] = SettingsField created value that will control how this value is
    read and manipulated.

    The purpose of the Settings class is to allow a library or project/service to define a
    number of settings that are needed in order to function. You define a number of Settings
    propertiess to indicate what settings are available to use in the project.

    You define a Settings and properties very similar to how you define a dataclass. You specify
    a property name, type_hint, and default_value.

    >>> class MySettings(Settings):
    ...    name: type_hint = default_value

    A default `SettingsField` will be configured using the name, type_hint, and default_value as
    follows -- `SettingsField(name=name, type_hint=type_hint, converter=type_hint,
    default_value=default_value, resolver=default_resolver)`

    This functionality can be overridden by setting the default_value to a custom `SettingsField`.
    The custom `SettingsField` will be merged with the default `SettingsField` overriding any
    fields that were defined in the custom SettingsField.

    It's important to note that while we are setting these attributes on the class they will not
    remain as attributes on the class. The _SettingsMeta will take each attribute and convert
    them to a SettingsField and then place them in the class's _setting_fields attribute.

    Example of various ways to allocate a SettingsField on a Settings subclass:

    >>> class MySettings(Settings):
    ...     setting_1: int
    Allocates
    >>> SettingsField(name="setting_1", type_hint=int, resolver=SettingsResolver)

    >>> class MySettings(Settings):
    ...     setting_1: int = 3
    Allocates
    >>> SettingsField(name="setting_1", type_hint=int, resolver=SettingsResolver, default_value=3)

    >>> class MySettings(Settings):
    ...     setting_1 = 3
    Allocates
    >>> SettingsField(name="setting_1", type_hint=int, resolver=SettingsResolver, default_value=3)

    >>> class MySettings(Settings):
    ...     setting_1: int = SettingsField(name="other", required=False)
    Allocates
    >>> SettingsField(name="other", type_hint=int, resolver=SettingsResolver, required=False)

    ## Accessing Class (not instance) Attributes = Lazy Property Reference

    You can do lazy forward-refrences by simply asking the Settings class (not instance) for a
    attribute. Doing so will return a `SettingsClassProperty` that is a forward reference to the
    singleton instance class attribute.

    Examples of how you might use this

    >>> class MySettings(Settings):
    ...    my_url_setting: str
    >>> class MySubSettings(Settings):
    ...    my_field: str
    >>> class SomeClass:
    ...    some_attr = MySettings.my_url_setting
    >>>
    >>> MySettings.grab().my_url_setting = "my-url"
    >>> MySubSettings.grab().my_field = MySettings.my_url_setting
    >>>
    >>> assert SomeClass.some_attr == "my-url"
    >>> assert MySubSettings.grab().some_attr == "my-url"
    >>> assert MySettings.grab().some_attr == "my-url"

    ## Setting public Class Attributes after creation time not allowed
    Attempting to set a public class level attribute will result in an Error being raised.

    ## Settings Attribute (Property) Inheritance not allowed
    To keep things as simple as possible we don't allow SettingsClass attribute inheritance. You
    can however create a parent class that defines methods / @properties that can be inherited.
    Trying to set a regular (non-method/non-property/public) attribute will raise an error.

    ## Accessing Instance Properties = Get Value and Convert
    When calling MySettings.grab().my_setting the Settings class will attempt to retrieve and
    convert the corresponding value. Getting the the source value and converting the value is
    controlled by the SettingsField. Here is how it works.

    Start by attempting to retrieve a property from the class instance
    >>> MyClass.grab().my_setting

    The Settings class will do the following
    1. Attempt to retrieve a value.
       a. Lookup value from self via `object.__getattribute__(self, key)`
       b. If an AttributeError is thrown then lookup the value from the corresponding field
       via `self._settings_field[name].get_value()`
    2. Convert the retrieved value by calling `self._settings_field[name].convert_value(value)`

    .. todo:: We don't support property setters/deleters at the moment.
              We would need to implement a `__setattr__` here, where it would check
              for a property setter/getter on field object.
              (Consider a explicit `fget` and `fset` attribute on SettingsField at that point)
    """

    def __init__(self, **kwargs):
        """
        Set attributes to values that are passed via key-word arguments, these are the inital
        values for the settings instance your creating.
        """
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattribute__(self, key):
        if key.startswith("_"):
            return object.__getattribute__(self, key)

        attr_error = None
        value = None
        field: SettingsField = self._setting_fields.get(key)

        try:
            # Look for an attribute on self first.
            value = object.__getattribute__(self, key)
            if hasattr(value, "__get__"):
                value = value.__get__(self, type(self))
        except AttributeError as error:
            attr_error = error

        if field:
            # If we have a field, and current value is Default, or we got AttributeError,
            # we attempt to retrieve the value via the field's retriever.
            if attr_error or value is Default:
                value = field.retrieve_value(settings=self)

            value = field.convert_value(value)

            if value is None and field.required:
                raise SettingsValueError(
                    f'Field ({field}) is required and the value we have is `None` at this point; '
                    f'None is either directly assigned as an attribute to self or is in a '
                    f'superclass... If you want to force Settings to attempt to retrieve the '
                    f'value BUT you also need to have a value of some sort set on the attribute '
                    f'in either the instance or a superclass: set the value to '
                    f'`xsentinels.Default` instead of `None`, this value will force Settings to '
                    f'attempt to retrieve the value (retrieval could be a property retriever on'
                    f'your settings class, or a forward-ref to another settings class, or in the'
                    f'case of `ConfigRetreiver`, retrieving from Config.'
                )

        elif attr_error:
            raise AttributeError(
                f"Unable to retrieve settings attribute ({key}) from ({self}), "
                f"there was no defined class-level settings field and no value set for "
                f"attribute on object, see original exception for more details."
            ) from attr_error

        return value



