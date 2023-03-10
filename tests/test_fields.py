from typing import Any, Optional, Sequence

import pytest as pytest

from xsettings.fields import SettingsField, generate_setting_fields
from xsettings.retreivers import SettingsRetrieverProtocol
from xsettings import BaseSettings


@pytest.mark.parametrize(
    argnames="field_name,new_value,should_change",
    argvalues=[
        ("name", "new_name", True),
        ("required", False, True),
        ("converter", int, True),
        ("type_hint", int, True),
        ("retriever", "new_retriever", True),
        ("default_value", "new_default", True),
        ("source_class", "new_source", False),
        ("source_name", "new_name", False),
    ],
)
def test_merge(field_name, new_value, should_change):
    field1 = SettingsField()
    field2 = SettingsField()
    setattr(field2, field_name, new_value)
    old_value = getattr(field1, field_name)
    field1.merge(field2)

    after_value = getattr(field1, field_name)
    if should_change:
        assert after_value == new_value
    else:
        assert after_value == old_value


def test_skip_attrs_no_typehint_on_properties():
    class TestClass:
        def method(self):
            pass

        @property
        def my_property_field(self):
            return None

        _private = None

    with pytest.raises(AssertionError, match='Must have type-hint for field.+my_property_field'):
        generate_setting_fields(TestClass.__dict__)


def test_verify_retriever_on_property_field():
    @property
    def prop_field(self) -> Optional[str]:
        return None

    class TestClass(BaseSettings):
        def method(self):
            pass

        my_property_field = prop_field
        _private = None

    # Make sure the generated field property-retriever has my property assigned to it.
    assert (
        TestClass._setting_fields['my_property_field'].retriever.property_retriever == prop_field
    )


def test_verify_retriever_on_normal_field():
    with pytest.raises(AssertionError, match='Invalid retriever for field .*some_field'):
        class TestClass(BaseSettings):
            def method(self):
                pass

            some_field: str = SettingsField(retriever="retriever")

            @property
            def my_property_field(self) -> str:
                return None

            _private = None


def test_property_as_retreiver():
    def my_default_retreiver(*, field: SettingsField, settings: 'BaseSettings'):
        return f"field.name={field.name}"

    class TestSettings(BaseSettings, default_retrievers=[my_default_retreiver]):
        my_str_field: str

        @property
        def my_prop(self) -> str:
            return "retreiving-it-my-self"

    # Ensure that a normal property uses the default_retriever...
    assert TestSettings.grab().my_str_field == "field.name=my_str_field"

    # But a normal property uses its self as its own retreiver...
    assert TestSettings.grab().my_prop == "retreiving-it-my-self"


def test_attrs_default_no_typehint():
    class TestClass(BaseSettings):
        val = 1

    fields = TestClass._setting_fields
    expected_field = SettingsField(
        name="val",
        type_hint=int,
        source_name="val",
        default_value=1,
        required=True,
        source_class=TestClass
    )
    assert fields["val"] == expected_field


def test_attrs_default_with_typehint():
    class TestClass(BaseSettings):
        val: str = 1

    fields = TestClass._setting_fields
    expected_field = SettingsField(
        name="val",
        type_hint=str,
        source_name="val",
        default_value=1,
        required=True,
        source_class=TestClass
    )
    assert fields["val"] == expected_field


def test_attrs_no_default():
    class TestClass(BaseSettings):
        val: str

    fields = TestClass._setting_fields
    expected_field = SettingsField(
        name="val", type_hint=str, source_name="val", required=True, source_class=TestClass
    )
    assert fields["val"] == expected_field


def test_attrs_merge():
    class Retriever(SettingsRetrieverProtocol):
        def get(self, field: SettingsField, *, settings: BaseSettings) -> Any:
            pass

    new_retriever = Retriever()

    class TestClass(BaseSettings):
        val: str = SettingsField(
            name="name",
            required="required",
            converter="converter",
            type_hint="type_hint",
            retriever=new_retriever,
            default_value="default_value",
            source_name="source_name",
        )

    fields = TestClass._setting_fields
    expected_field = SettingsField(
        name="name",
        required="required",
        converter="converter",
        type_hint="type_hint",
        retriever=new_retriever,
        default_value="default_value",
        source_name="val",
        source_class=TestClass
    )
    assert fields["val"] == expected_field


def test_retriever_type():
    with pytest.raises(AssertionError):
        class TestClass(BaseSettings):
            val: str = SettingsField(retriever="abc")


def test_with_generic_typehint():
    class SomeSettings(BaseSettings):
        generic_settings_field: Sequence[str]

    SomeSettings.grab().generic_settings_field = ['a', '1', '!']

    assert SomeSettings.grab().generic_settings_field == ['a', '1', '!']
    assert type(SomeSettings.grab().generic_settings_field) is list
