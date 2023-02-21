---
title: Getting Started
---

## Install

```bash
# via pip
pip install xloop

# via poetry
poetry add xloop
```

## Introduction

Helps document and centralizing settings in a python project/library.

Facilitates looking up BaseSettings from `retrievers`, such as an environmental variable retriever.

Converts and standardizes any retrieved values to the type-hint on the setting attribute (such as bool, int, datetime, etc).

Interface to provide own custom retrievers, to grab settings/configuration from wherever you want.

Retrievers can be stacked, so multiple ones can be consulted when retrieving a setting.

## Quick Start

```python
from xsettings import EnvVarSettings, SettingsField
from xsettings.errors import SettingsValueError
from typing import Optional
import dataclasses
import os

# Used to showcase looking up env-vars automatically:
os.environ['app_version'] = '1.2.3'

# Used to showcase complex setting types:
@dataclasses.dataclass
class DBConfig:
    @classmethod
    def from_dict(cls, values: dict):
        return DBConfig(**values)

    user: str
    host: str
    password: str


# Some defined settings:
class MySettings(EnvVarSettings):
    app_env: str = 'dev'
    app_version: str
    api_endpoint_url: str
    
    some_number: int

    # For Full Customization, allocate SettingsField,
    # In this case an alternate setting lookup-name
    # if you want the attribute name to differ from lookup name:
    token: Optional[str] = SettingsField(name='API_TOKEN')

    # Or if you wanted a custom-converter for a more complex obj:
    db_config: DBConfig = SettingsField(
        converter=DBConfig.from_dict
    )

# BaseSettings subclasses are singleton-like dependencies that are
# also injectables and lazily-created on first-use.
# YOu can use a special `BaseSettings.grab()` class-method to
# get the current settings object.
#
# So you can grab the current MySettings object lazily via
# its `grab` class method:
MySettings.grab().some_number = 3

assert MySettings.grab().some_number == 3

# You can also use a proxy-object, it will lookup and use
# the current settings object each time its used:
my_settings = MySettings.proxy()

# Here I showcase setting a dict here and using the converter
# I defined on the SettingsField to convert it for me:
my_settings.db_config = {
    'user': 'my-user',
    'password': 'my-password',
    'host': 'my-host'
}


expected = DBConfig(
    user='my-user',
    password='my-password',
    host='my-host'
)

# The dict gets converted automatically to the DBConfig obj:
assert MySettings.grab().db_config == expected

# If you set a setting with the same/exact type as
# it's type-hint, then it won't call the converter:
my_settings.db_config = expected

# It's the same exact object-instance still (ie: not changed/converted):
assert my_settings.db_config is expected


# Will use the default value of `dev` (default value on class)
# since it was not set to anything else and there is no env-var for it:
assert my_settings.app_env == 'dev'

# EnvVarSettings (superclass) is configured to use the EnvVar retriever,
# and so it will find this in the environmental vars since it was not
# explicitly set to anything on settings object:
assert my_settings.app_version == '1.2.3'

# Any BaseSettings subclass can use dependency-injection:
assert my_settings.token is None

with MySettings(token='my-token'):
    assert my_settings.token == 'my-token'

    # Parent is still consulted for any settings unset on child but set on parent:
    assert my_settings.db_config == expected

    # Can set settings like you expect,
    # this will go into the child created in above `with` statement:
    my_settings.app_env = 'prod'

    assert my_settings.app_env == 'prod'

# After `with` child is not the current settings object anymore,
# reverts back to what it was before:
assert my_settings.token is None

try:
    # If a setting is undefined and required (ie: not-optional),
    # and it was not set to anything nor is there a default or an env-var for it;
    # BaseSettings will raise an exception when getting it:
    print(my_settings.api_endpoint_url)
except SettingsValueError as e:
    assert True
else:
    assert False

try:
    # `SettingsValueError` inherits from both AttributeError and ValueError,
    # as the error could be due to either aspect; so you can also do an except
    # for either standard error:
    print(my_settings.api_endpoint_url)
except ValueError as e:
    assert True
else:
    assert False
```


# Overview

The settings library is seperated into a few core components.

- BaseSettings
- SettingsField
- SettingsRetrieverProtocol

# BaseSettings

This is the core class that BaseSettings implementations will inherit from.
BaseSettings can be used as source for external settings / variables that a given 
application / library needs in order to function. It provides future
developers an easy way to see what these external variables are and
where they are derived from.

In its simplest form a BaseSettings class implementation is simply a class 
similar to a `@dataclass` that inherits from a given BaseSettings base class. 

Example BaseSettings File

```python
from xsettings import BaseSettings, SettingsField


class MySettings(BaseSettings):
    a: int
    b: int = 1
    c = "1"

    # For Full Customization, allocate SettingsField:
    d: str = SettingsField(...) 
```

Each of these attributes will be converted to a SettingsField object to
control future value lookup. Each part on the attribute (name, type_hint, 
default_value) will be reflected in the SettingsField. If you want more
customization you can set a SettingsField() as your default value and the
fields set in that will be overridden in the main SettingsField object.

## BaseSettings usage

### Class/Lazy Attribute Lookup

Referencing the attribute at the class level will return a `SettingsClassProperty`
rather than a SettingsField (or the default value). This is useful when you want
to do property chaining, or you want to use a property as a property in another
class

```python
from xsettings import BaseSettings, EnvVarSettings
import os


class MySettings(BaseSettings):
    table_name: str


MySettings.grab().table_name = "the-t-name"


class MyTable:
    class Meta:
        #  Here, we set a forward-ref class property
        #  to be whatever the current setting of `MySettings.table_name`
        #  will be (it's a property and will look it up each time
        #  its asked for).
        table_name = MySettings.table_name


# Forward-ref is resolved via lazy-forward-ref,
# each time it's asked for:
assert MyTable.Meta.table_name == 'the-t-name'

with MySettings(table_name='alt-table-name'):
    assert MyTable.Meta.table_name == 'alt-table-name'


# Inherit from EnvVarSettings, so it will retrieve our settings
# via environmental variables
# (will use env-vars on-demand if value is not set directly on it).
class MyEnvSettings(EnvVarSettings):
    my_table_name: str


os.environ['MY_TABLE_NAME'] = 'env-table-name'

#  We can directly set the setting on MySettings to a lazy-prop-ref
#  and so now this setting will reflect what's the current value
#  in `MyEnvSettings.my_table_name` is; and `MyEnvSettings` will
#  retrieve its value from environmental variables
#  since it inherits from `EnvVarSettings`.
#  
MySettings.grab().table_name = MyEnvSettings.my_table_name

assert MySettings.grab().table_name == 'env-table-name'


# Example 3, default value of settings field can be a lazy-property-ref
class MyOtherSettings(BaseSettings):
    my_setting_attr: str = MyEnvSettings.my_table_name


my_other_settings = MyOtherSettings.proxy()
assert my_other_settings.my_setting_attr == 'env-table-name'

os.environ['MY_TABLE_NAME'] = 'env-table-2'
assert my_other_settings.my_setting_attr == 'env-table-2'

```

### Change Default Value

You can now (as of v1.3) change the default value on an already created BaseSettings subclass:

```python
from xsettings import BaseSettings, SettingsField


class MySettings(BaseSettings):
    a: int
    b: int = 1


# Change default value later on;
# Now the `MySettings.a` will have a
# default/fallback value of `2`:
MySettings.a = 2


class MyOtherSettings(BaseSettings):
    some_other_setting: str


# You can also set a lazy-ref as setting field's
# default value after it's class is created.
# (also if the type-hint's don't match it will convert
#  the value as needed like you would expect.
MyOtherSettings.some_other_setting = MySettings.b

# It's a str now, since `MyOtherSettings.some_other_setting`
# has a str typehint:
assert MyOtherSettings.grab().some_other_setting == '1'
```

### Setting New Setting on Class Attributes

You can't create new settings attributes/fields on a BaseSettings subclass after the class
is created (only during class creation).

You can set/change the default value for an existing settings attribute by simply assigning
to it as a class attribute (see topic [Change Default Value](#change-default-value)).

### Class Instance Attribute lookup

Setting classes inherit from `1xinject.Dependency` and as such are considered singletons.
Instances should not be created. Instead, to access an instance you should do
`MySettings.grab()`; or you can use an `MySettings.proxy()`, ie:

```python
my_settings = MySettings.proxy()

# Can use `my_settings` just like `MySettings.grab().table_name`,
print(my_settings.table_name)

# You can also import the `my_settings` proxy into other modules,
# for use elsewhere.
from my_project.settings import my_settings
print(my_settings.table_name)
```

Proxies are directly importable into other files, the proxy will lookup the current
dependency/singletone instance every time you access it for normal attributes and methods
(anything starting with a `_`/underscore is not proxied).

To lookup the value of a given settings simply reference it on the Singleton
instance via `MySettings.grab().table_name`. This will cause a lookup
to happen.

### Inheriting from Plain Classes

Currently, there is a something to watch out for when you also inherit from a plain class
for you BaseSettings subclass.

For now, we treat all plain super-class values on attributes as-if they were directly assigned
to the settings instance; ie: we will NOT try to 'retrieve' the value unless the value is
set to `xsentinels.Default` in either the instance or superclass (whatever value it finds via normal
python attribute retrieval rules).

You can use `xsentinels.Default` to force BaseSettings to lookup the value and/or use its default value if it
has one.

May in the future create a v2 of xsettings someday that will look at attributes directly
assigned to self, then and retrieved value, then any plain super-class set value.

(For a more clear example of this, see unit test method `test_super_class_with_default_value_uses_retriever`)

# SettingsField

Provides value lookup configuration and functionality. It controls
how a source value is retrieved `xsettings.fields.SettingsField.retriever` and
converted `xsettings.fields.SettingsField.converter`.

If there is not SettingsField used/generated for an attribute,
then it's just a normal attribute.

No special features of the BaseSettings class such as lazy/forward-references will work with them.

## How SettingsField is Generated

Right now, a SettingsField is only automatically generated for annotated attributes.

Also, one is generated for any `@property` functions
(you must define a return type-hint for property).

Normal functions currently DO NOT generate a field, also attributes without a type annotation
will also not automatically be generated.

Anything starting with an `_` will not have a field generated for it,
they are for use by properties/methods on the class and work like normal.

You can also generate your own SettingsField with custom options by creating
one and setting it on a class attribute, during the class creation process.

After a class is created, you can't change or add SettingFields to it anymore, currently.

Examples:

```python
from xsettings import BaseSettings, SettingsField


class MySettings(BaseSettings):
    custom_field: str = SettingsField(required=False)

    # SettingsField auto-generated for `a`:
    a: str

    # A Field is generated for `b`, the type-hint will be `type(2)`.
    b = 2

    # A field is NOT generated for anything that starts with an underscore (`_`),
    # They are considered internal attributes, and no Field is ever generated for them.
    _some_private_attr = 4

    # Field generated for `my_property`, it will be the fields 'retriever'.
    @property
    def my_property(self) -> str:
        return "hello"

    # No field is generated for `normal_method`:
    # Currently, any directly callable object/function as a class attribute value
    # will never allow you to have a Field generated for it.
    def normal_method(self):
        pass
```

# Converters

When BaseSettings gets a value due to someone asking for an attribute on it's self, it will
attempt to convert the value if the value does not match the type-hint.

To find a converter, we check these in order, first one found is what we use:

1. We first check `self.converter`.
2. Next, [`DEFAULT_CONVERTERS`](api/xsettings/default_converters.html#xsettings.default_converters.DEFAULT_CONVERTERS){target=_blank}
3. Finally, we fall back to using the type-hint (ie: `int(value)` or `str(value)`).
    - This also enables types that inherit from `Enum` to work:  
      ie: plain values will be converted into one of the enum's values.

If the retrieved value does not match the type-hint, it will run the converter by calling
it and passing the value to convert. The value to convert is whatever value was set,
retrieved. It can also be the field's default-value if noting is set/retreived.


# Properties

## Supports Read-Only Properties

The BaseSettings class also supports read-only properties, they are placed in a SettingField's
retriever (ie: `xsettings.fields.SettingField.retriever`).

When you access a value from a read-only property, when the value needs to be retrieved,
it will use the property as a way to fetch the 'storage' aspect of the field/attribute.

All other aspects of the process behave as it would for any other field.

This means in particular, after the field returns its value BaseSettings will check the returned values
type against the field's type_hint, and if needed will convert it if needed before handing it to 
the thing that originally requested the attribute/value.

It also means that, if the BaseSettings instance has a plain-value directly assigned to it,
that value will be used and the property will not be called at all
(since no value needs to be 'retrieved').

In effect, the property getter will only be called if a retrieved value is needed for the
attribute.

Here is an example below. Notice I have a type-hint for the return-type of the property.
This is used if there is no type-annotation defined for the field.

```python
from xsettings import BaseSettings
from decimal import Decimal


class MySettings(BaseSettings):
    @property
    def some_setting(self) -> Decimal:
        return "1.34"


assert MySettings.grab().some_setting == Decimal("1.34")
```

You can also define a type-annotation at the class level for the property like so:

```python
from xsettings import BaseSettings
from decimal import Decimal


class MySettings(BaseSettings):
    # Does not matter if this is before or after the property,
    # Python stores type annotations in a separate area
    # vs normal class attribute values in Python.
    some_setting: Decimal

    @property
    def some_setting(self):
        return "1.34"


assert MySettings.grab().some_setting == Decimal("1.34")
```

## Getter Properties Supported as a Forward/Lazy-Reference

You can get a forward-ref for a property field on a BaseSettings class,
just like any other field attribute on a BaseSettings class:

```python
from xsettings import BaseSettings
from decimal import Decimal


class MySettings(BaseSettings):
    # Does not matter if this is before or after the property,
    # Python stores type annotations in a separate area
    # vs normal class attribute values in Python.
    some_setting: Decimal

    @property
    def some_setting(self) -> Decimal:
        return "1.34"


class OtherSettings(BaseSettings):
    other_setting: str = MySettings.some_setting


assert OtherSettings.grab().other_setting == "1.34"
```

In the example above, I also illustrate that a forward-ref will still pay-attention
to the type-hint assigned to the field. It's still converted as you would expect,
in this case we convert a Decimal object into a str object when the value for
`other_setting` is asked for.

## Getter Property with Custom SettingsField

You can also specify a custom SettingsField and still use a property with it.
Below is an example. See `xsettings.fields.SettingsField.getter` for more details.

```python
from xsettings import BaseSettings, SettingsField


class MySettings(BaseSettings):
    # Does not matter if this is before or after the property,
    # Python stores type annotations in a separate area
    # vs normal class attribute values in
    # Python.
    some_setting: str = SettingsField(required=False)

    @some_setting.getter
    def some_setting(self):
        return "1.36"


assert MySettings.grab().some_setting == "1.36"
```


## Setter Properties Currently Unsupported

You can't currently have a setter defined for a property on a class.
This is something we CAN support without too much trouble, but have decided to
put off for a future, if we end up wanting to do it.

If you define a setter property on a BaseSettings class, it will currently raise an error.

# SettingsRetriever

Its responsibility is providing functionality to retrieve a variable from 
some sort of variable store.

The
[`SettingsRetrieverProtocol`](api/xsettings/retreivers.html#xsettings.retreivers.SettingsRetrieverProtocol){target=_blank}
provides the callable protocol.

You can set a default-retriever to be used as a fallback if 
no other value is set or other non-default retrievers can't find a value
by using a class-argument like so:

```python
from xsettings import BaseSettings


class MySettings(BaseSettings, default_retrievers=my_retriever):
    some_setting: str
```

# How Setting Field Values Are Resolved

## Summary

In General, this order is how things are resolved with more detail
to follow:

1. Value set directly on Setting-subclass instance.
   - via `MySettings.grab().some_setting = 'some-set-value`
2. Value set on a parent-instance in [`XContext.dependency_chain(for_type=SettingsSubclass)`](api/xinject/context.html#xinject.context.XContext.dependency_chain){target=_blank}.
   - BaseSettings can be used as context-managers via `with` and decorators `@`.
   - When a new BaseSettings instance is activated via decorator/with and previously active setting is in it's parent-chain
     which is resolved via it's dependency-chain
     ([`XContext.grab().dependency_chain(for_type=SettingsSubclass)`](api/xinject/context.html#xinject.context.XContext.dependency_chain){target=_blank}).
   - Example: `with MySetting(some_setting='parent-value'):`
3. Retrievers are consulted next.
    1. First, retriever set directly on field `xsettings.fields.SettingsField.retriever`.
       1. This can include any field properties `@property`, they are set as the field retriever.
    2. Next, instance retriever(s) set directly on the Setting object that is being asked for its field value is checked.
       1. via [`BaseSettings.add_instance_retrievers`](api/xsettings/settings.html#xsettings.settings.Settings.add_instance_retrievers){target=_blank}.
    3. Then any instance-retrievers in the dependency-chain are checked next (see step 2 above for more details).
    4. Default-retrievers assigned to the class(es) are next checked, in `mro` order.
4. Finally, any default-value for the field is consulted.
    - If the default-value is a property, or forward-ref then that is followed.
      - ie: `BaseSettings.some_attr = OtherSettings.another_attr_to_forward_ref_with`
      - This ^ will change the default value for `some_attr` to a forward-ref from another BaseSettings class.

Keep in mind that generally, if a value is a `property` (including forward-refs, which are also properties),
they are followed via the standard `__get__` mechanism (see earlier in document for forward-ref details).

## Resolution Details

Values set directly on Setting instances are first checked for and used if one is found.
Checks self first, if not found will next check
[`XContext.grab().dependency_chain(for_type=SettingsSubclass)`](api/xinject/context.html#xinject.context.XContext.dependency_chain){target=_blank}
(returns a list of each instance currently in the dependency-chain, each one is checked in order; see link for details).

```python
from xsettings import BaseSettings, SettingsField


def my_retriever(*, field: SettingsField, settings: BaseSettings):
    return f"retrieved-{field.name}"


class MySettings(BaseSettings, default_retrievers=my_retriever):
    some_setting: str


assert MySettings.grab().some_setting == 'retrieved-some_setting'
```

If value can't be found the retrievers are next checked.

Retrievers are tried in a specific order, the first one with a non-None retrieved value
is the one that is used.

After the individual field retrievers are consulted, instance retrievers are checked next
before finally checking the default-retrievers for the entire class.

You can also add one or more retrievers to this `instance` of settings via the
[`BaseSettings.add_instance_retrievers`](api/xsettings/settings.html#xsettings.settings.Settings.add_instance_retrievers){target=_blank}
method (won't modify default_retrievers for the entire class, only modifies this specific instance).

They are checked in the order added.

Child dependencies (of the same exactly class/type) in the
[`XContext.dependency_chain(for_type=SettingsSubclass)`](api/xinject/context.html#xinject.context.XContext.dependency_chain){target=_blank}
will also check these instance-retrievers.

The dependency chain is checked in the expected order of first consulting self,
 then the chain in most recent parent first order.

For more details on how parent/child dependencies work see
[`XContext.dependency_chain`](api/xinject/context.html#xinject.context.XContext.dependency_chain){target=_blank}.

After the dependency-chain is checked, the default-retrievers are checked
in python's `mro` (method-resolution-order), checking its own class first
before checking any super-classes for default-retrievers.

## Callable Defaults

If a default value is callable, when a default value is needed during field value resolution,
it will be called without any arguments and the returned value will be used.

Example:

```python
# todo: Think about a mutable callable default (such as list) with this feature...
```

# Things to Watch Out For

- If a field has not type-hint, but does have a normal (non-property) default-value,
  The type of the default-value will be used for type-hint.
- If a field has no converter, it will use the type-hint as the converter by default.
- Every field must have a type-hint, otherwise an exception will be raised.
