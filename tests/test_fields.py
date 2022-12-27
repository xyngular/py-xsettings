from typing import Any

import pytest as pytest

from xsettings.fields import SettingsField, generate_setting_fields
from xsettings.settings import SettingsRetriever, Settings


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
        generate_setting_fields(TestClass.__dict__, default_retriever="retriever")


def test_verify_retreiver_on_property_field():
    class TestClass:
        def method(self):
            pass

        @property
        def my_property_field(self) -> str:
            return None

        _private = None

    # Properties don't use the default_retreiver, so we should be fine
    # (ie: `default_retriever` is unused).
    generate_setting_fields(TestClass.__dict__, default_retriever="retriever")


def test_verify_retreiver_on_normal_field():
    class TestClass:
        def method(self):
            pass

        some_field: str

        @property
        def my_property_field(self) -> str:
            return None

        _private = None

    with pytest.raises(AssertionError, match='Invalid retriever for field'):
        generate_setting_fields(TestClass.__dict__, default_retriever="retriever")


class Retriever(SettingsRetriever):
    def get(self, field: SettingsField, *, settings: Settings) -> Any:
        pass


retriever = Retriever()


def test_property_as_retreiver():
    def my_default_retreiver(field: SettingsField, /, *, settings: 'Settings'):
        return f"field.name={field.name}"

    class TestSettings(Settings, default_retriever=my_default_retreiver):
        my_str_field: str

        @property
        def my_prop(self) -> str:
            return "retreiving-it-my-self"

    # Ensure that a normal property uses the default_retriever...
    assert TestSettings.grab().my_str_field == "field.name=my_str_field"

    # But a normal property uses it's self as it's own retreiver...
    assert TestSettings.grab().my_prop == "retreiving-it-my-self"


def test_attrs_default_no_typehint():
    class TestClass:
        val = 1

    fields = generate_setting_fields(TestClass.__dict__, default_retriever=retriever)
    expected_field = SettingsField(
        name="val",
        type_hint=int,
        retriever=retriever,
        source_name="val",
        default_value=1,
        required=True
    )
    assert fields["val"] == expected_field


def test_attrs_default_with_typehint():
    class TestClass:
        val: str = 1

    fields = generate_setting_fields(TestClass.__dict__, default_retriever=retriever)
    expected_field = SettingsField(
        name="val",
        type_hint=str,
        retriever=retriever,
        source_name="val",
        default_value=1,
        required=True
    )
    assert fields["val"] == expected_field


def test_attrs_no_default():
    class TestClass:
        val: str

    fields = generate_setting_fields(TestClass.__dict__, default_retriever=retriever)
    expected_field = SettingsField(
        name="val", type_hint=str, retriever=retriever, source_name="val", required=True
    )
    assert fields["val"] == expected_field


def test_attrs_merge():
    new_retriever = Retriever()

    class TestClass:
        val: str = SettingsField(
            name="name",
            required="required",
            converter="converter",
            type_hint="type_hint",
            retriever=new_retriever,
            default_value="default_value",
            source_name="source_name",
        )

    fields = generate_setting_fields(TestClass.__dict__, default_retriever=retriever)
    expected_field = SettingsField(
        name="name",
        required="required",
        converter="converter",
        type_hint="type_hint",
        retriever=new_retriever,
        default_value="default_value",
        source_name="val",
    )
    assert fields["val"] == expected_field


def test_retriever_type():
    class TestClass:
        val: str

    with pytest.raises(AssertionError):
        generate_setting_fields(TestClass.__dict__, default_retriever="abc")
