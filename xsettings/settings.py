"""

See doc-comments for `Settings` below.


"""

from typing import Dict, Any, Union, TypeVar, Protocol, Optional, Iterable, List, Type

from xinject import Dependency
from xloop import xloop
from xsentinels import Default

from xsettings.fields import generate_setting_fields, SettingsField, SettingsClassProperty

T = TypeVar("T")

# Tell pdoc3 to document the normally private method __call__.
__pdoc__ = {
    "SettingsRetrieverCallable.__call__": True,
    "SettingsRetriever.__call__": True,
}


# It's both an attribute and a value error
# (attribute is missing and/or value has some other issue)
# `AttributeError` helps pdoc3 know that there is no value safely
# (ie: it will continue to generate docs).
class SettingsValueError(ValueError, AttributeError):
    pass


# todo: remove use of `SettingsRetrieverCallable`

class SettingsRetriever(Protocol):

    """
    The purpose of the base SettingsRetrieverCallable is to define the base-interface for
    retrieving settings values.

    The retriever can be any callable, by default `xsettings.settings.Settings` will use
    an instance of `SettingsRetriever`. It provides a default retriever implementation,
    see that class for more details on what happens by default.
    """

    def __call__(self, *, field: SettingsField, settings: 'Settings') -> Any:
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


def _load_default_retriever(setting_subclasses_in_mro, default_retriever):
    if default_retriever:
        return default_retriever

    # Look for a retrieve in base classes.
    for base in setting_subclasses_in_mro:
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

    # This will be a class-attributes on the normal `Settings` class/subclasses.
    _setting_fields: Dict[str, SettingsField]
    _retrievers: List[SettingsRetriever]

    _there_is_plain_superclass: bool
    """ There is some other superclass, other then Settings/object/Dependency. """

    _setting_subclasses_in_mro: 'List[Type[Settings]]'
    """
    Includes self/cls plus all superclasses who are Settings subclasses in __mro__
    (but not Settings it's self); in the same order that they appears in __mro__.
    """

    def retrievers(cls, retriever: SettingsRetriever):
        cls._retrievers.append(retriever)

    def __new__(
        mcls,
        name,
        bases,
        attrs: Dict[str, Any],
        *,
        retrievers: Union[SettingsRetriever, Iterable[SettingsRetriever]] = None,
        skip_field_generation: bool = False,
        **kwargs,
    ):
        """
        The instance of `mcls` is a Settings class or subclass
        (not Settings object, the class its self).

        Objective in this method is to create a set of SettingsField object(s) for use by the new
        Settings subclass, and set their default-settings correctly if the user did not
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
        # These defaults may be altered later on in this method (after class is created)...
        attrs['_there_is_plain_superclass'] = False
        attrs['_setting_subclasses_in_mro'] = []
        attrs['_retrievers'] = list(xloop(retrievers))

        if skip_field_generation:
            # Skip doing anything special with any Settings classes created in our/this module;
            # They are abstract classes and are need to be sub-classed to do anything with them.
            attrs['_setting_fields'] = {}
            cls = super().__new__(mcls, name, bases, attrs, **kwargs)  # noqa
            return cls

        # W need to get base-types in mro order, before we create the class.
        types_in_mro = type(name, bases, {}, skip_field_generation=True).__mro__[1:]

        # And look through the __mro__ python determined while creating the class,
        # we cache the specific ones/information we need this one time so future operators
        # are simpler/faster.
        setting_subclasses_in_mro = []

        # We install can't include 'us' because our type has not been created yet.
        attrs['_setting_subclasses_in_mro'] = setting_subclasses_in_mro
        for c in types_in_mro:
            # Skip the ones that are always present, and don't need to examined...
            if c is Settings:
                continue
            if c is object:
                continue
            if c is Dependency:
                continue

            # We want to know the order if aby Settings subclasses that we are inheriting from.
            # Also want to know if there are any plain/non-setting classes in our parent hierarchy
            # (that are not object/Dependency, as they both will always be present).
            if issubclass(c, Settings):
                setting_subclasses_in_mro.append(c)
            else:
                attrs['_there_is_plain_superclass'] = True

        parent_fields = {}

        for c in reversed(setting_subclasses_in_mro):
            parent_fields.update(c._setting_fields)

        # default_retriever = _load_default_retriever(setting_subclasses_in_mro, default_retriever)
        setting_fields = generate_setting_fields(
            attrs, parent_fields
        )

        attrs["_setting_fields"] = setting_fields

        # Any attributes that were converted to fields we remove from class attributes,
        # they instead will be dynamically looked up lazily as-needed via their associated field.
        for k in setting_fields.keys():
            attrs.pop(k, None)

        # This creates the new Settings class/subclass.
        cls = super().__new__(mcls, name, bases, attrs, **kwargs)

        # Insert newly crated class into top of its setting subclasses list.
        cls._setting_subclasses_in_mro.insert(0, cls)

        # We now link source_class of each field to us; helps with debugging.
        for field in setting_fields.values():
            field.source_class = cls

        return cls

    def __getattr__(self, key: str) -> SettingsClassProperty:
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

        for c in self._setting_subclasses_in_mro:
            c: _SettingsMeta
            if key in c._setting_fields:
                break
            # We got to `Settings` without finding anything, Settings has no fields,
            # raise exception about how we could not find field.
            if c is Settings:
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

        field = None
        for c in self._setting_subclasses_in_mro:
            c: _SettingsMeta
            if field := c._setting_fields.get(key):
                break
            # We got to `Settings` without finding anything, Settings has no fields,
            # give-up searching for field.
            if c is Settings:
                break

        if not field:
            # Right now we don't support making new SettingField's after the Settings subclass
            # has been created. We could decide to do that in the future, but for now we
            # are keeping things simpler.
            raise AttributeError(
                f"Setting new fields on Settings subclass unsupported currently, attempted to "
                f"set key ({key}) with value ({value})."
            )

        # Set default value of an existing field with `key` attribute-name:
        field.default_value = value




class Settings(
    Dependency,
    metaclass=_SettingsMeta,
    retrievers=[],

    # Settings has no fields, it's a special abstract-type of class skip field generation.
    # You should never use this option in a Settings subclass.
    skip_field_generation=True
):
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
        already_retrieved_normal_value = False

        field: Optional[SettingsField] = None
        for c in type(self)._setting_subclasses_in_mro:
            c: _SettingsMeta
            # todo: use isinstance?
            if c is Settings:
                # We got to the 'Settings' base-class it's self, no need to go any further.
                break
            if field := c._setting_fields.get(key):
                # Found the field, break out of loop.
                break

        def get_normal_value():
            nonlocal value
            nonlocal attr_error

            # Keep track that we already attempted to get normal value.
            nonlocal already_retrieved_normal_value
            already_retrieved_normal_value = True

            try:
                # Look for an attribute on self first.
                value = object.__getattribute__(self, key)
                if hasattr(value, "__get__"):
                    value = value.__get__(self, type(self))
                attr_error = None
            except AttributeError as error:
                attr_error = error

        # We don't want to grab the value like normal if we are a field
        # and DON'T have a locally/instance value defined for attribute.
        # This helps Setting classes that are subclasses of Plain classes
        # attempt to retrieve the value via the field retriever/mechanism
        # before using that plain-classes, class attribute.
        #
        # Otherwise, the plain-class attribute would ALWAYS be used over the field,
        # making the subclasses field definition somewhat useless.
        if not self._there_is_plain_superclass or not field or key in self.__dict__:
            get_normal_value()

        try:
            if field:
                # If we have a field, and current value is Default, or we got AttributeError,
                # we attempt to retrieve the value via the field's retriever.
                if not already_retrieved_normal_value or attr_error or value is Default:
                    def self_and_parent_retrievers():
                        for parent_class in type(self)._setting_subclasses_in_mro:
                            for r in parent_class._retrievers:
                                yield r
                    for retriever in xloop(field.retriever, self_and_parent_retrievers()):
                        value = retriever(field=field, settings=self)
                        if value is not None:
                            break

                    if value is None:
                        value = field.default_value
                    if value and hasattr(value, '__get__'):
                        value = value.__get__(self, type(self))

                    if value is None:
                        if field.required:
                            # Data-classes will print out all their fields by default, should give good info!
                            raise SettingsValueError(f"Missing value for {field}, while retrieving value.")
                        value = None

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
                return value
        except SettingsValueError as e:
            # We had a field and could not retrieve the value, if we have not already attempted
            # to get the 'normal' value via our base-classes attributes, then attempt that...
            if already_retrieved_normal_value:
                # Just continue the original exception
                raise

            get_normal_value()
            if attr_error:
                # Could not get the normal value from superclass, raise original exception.
                # todo: for Python 3.11, we can raise both exceptions (e + attr_error)
                #       we actually have two separate trees of exceptions here!
                #       For now we are prioritizing field value retrieval exception
                #       as the 'from' exception and putting the plain-class attribute error
                #       inside this exception.,
                raise SettingsValueError(
                    f"After attempting to get field value "
                    f"(the 'from' exception with message [{e}]); "
                    f"I tried to get value from plain superclass and that was also unsuccessful "
                    f"and produced exception/error: ({attr_error}); "
                    f"for field ({field})."
                ) from e

            if value is None and field.required:
                raise SettingsValueError(
                    f"After attempting to get field value I next tried to get it from the plain "
                    f"superclass but got None (details: via 'from' exception with message {e}); "
                    f"for field ({field})."
                ) from e

            value = field.convert_value(value)
            if value is None and field.required:
                raise SettingsValueError(
                    f"After attempting to get field value I next tried to get it from the plain "
                    f"superclass, it came back with a value. But after running the `converter` on "
                    f"the retrieved value a None was the result and this field is required; "
                    f"for field ({field})."
                ) from e
            return value

        if attr_error:
            raise AttributeError(
                f"Unable to retrieve settings attribute ({key}) from ({self}), "
                f"there was no defined class-level settings field and no value set for "
                f"attribute on object, see original exception for more details."
            ) from attr_error

        return value



