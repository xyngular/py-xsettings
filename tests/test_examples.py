
def test_quick_start_readme_example():
    from xsettings import EnvVarSettings, SettingsField
    from xsettings.errors import SettingsValueError
    from typing import Optional
    import dataclasses
    import os

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

    # Settings subclasses are singleton-like dependencies that are
    # also injectables and lazily-created on first-use.
    # YOu can use a special `Settings.grab()` class-method to
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

    # EnvSettings (superclass) is configured to use the EnvVar retriever,
    # and so it will find this in the environmental vars since it was not
    # explicitly set to anything on settings object:
    assert my_settings.app_version == '1.2.3'

    # Any Settings subclass can use dependency-injection:
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
        # Settings will raise an exception when getting it:
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


def test_class_lazy_attr_forward_ref():
    from xsettings import Settings, EnvVarSettings
    import os

    class MySettings(Settings):
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
    class MyOtherSettings(Settings):
        my_setting_attr: str = MyEnvSettings.my_table_name

    my_other_settings = MyOtherSettings.proxy()
    assert my_other_settings.my_setting_attr == 'env-table-name'

    os.environ['MY_TABLE_NAME'] = 'env-table-2'
    assert my_other_settings.my_setting_attr == 'env-table-2'


def test_change_default_example():
    from xsettings import Settings, SettingsField

    class MySettings(Settings):
        a: int
        b: int = 1

    # Change default value later on;
    # Now the `MySettings.a` will have a
    # default/fallback value of `2`:
    MySettings.a = 2

    class MyOtherSettings(Settings):
        some_other_setting: str

    # You can also set a lazy-ref as setting field's
    # default value after it's class is created.
    # (also if the type-hint's don't match it will convert
    #  the value as needed like you would expect.
    MyOtherSettings.some_other_setting = MySettings.b

    # It's a str now, since `MyOtherSettings.some_other_setting`
    # has a str typehint:
    assert MyOtherSettings.grab().some_other_setting == '1'


def test_read_only_props_1():
    from xsettings import Settings
    from decimal import Decimal

    class MySettings(Settings):
        @property
        def some_setting(self) -> Decimal:
            return "1.34"

    assert MySettings.grab().some_setting == Decimal("1.34")


def test_read_only_props_2():
    from xsettings import Settings
    from decimal import Decimal

    class MySettings(Settings):
        # Does not matter if this is before or after the property,
        # Python stores type annotations in a separate area vs
        # normal class attribute values in Python.
        some_setting: Decimal

        @property
        def some_setting(self):
            return "1.34"

    assert MySettings.grab().some_setting == Decimal("1.34")


def test_forward_ref_example():
    from xsettings import Settings
    from decimal import Decimal

    class MySettings(Settings):
        # Does not matter if this is before or after the property,
        # Python stores type annotations in a separate area
        # vs normal class attribute values in Python.
        some_setting: Decimal

        @property
        def some_setting(self) -> Decimal:
            return "1.34"

    class OtherSettings(Settings):
        other_setting: str = MySettings.some_setting

    assert OtherSettings.grab().other_setting == "1.34"


def test_index_doc_example():
    from xsettings import Settings, SettingsField

    def my_retriever(*, field: SettingsField, settings: Settings):
        return f"retrieved-{field.name}"

    class MySettings(Settings, default_retrievers=my_retriever):
        some_setting: str

    assert MySettings.grab().some_setting == 'retrieved-some_setting'
