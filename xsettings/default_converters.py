from decimal import Decimal
from typing import Callable, Dict, Any, Type
import datetime as dt
from dateutil import tz
import ciso8601
from xbool import bool_value


def to_bool(value):
    return bool_value(value)


def to_date(value):
    return dt.datetime.strptime(str(value), '%Y-%m-%d').date()


def to_datetime(value):
    # Should pretty much always be a string, so check for that first.
    if isinstance(value, str):
        return ciso8601.parse_datetime(value)

    if isinstance(value, dt.datetime):
        return value

    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=tz.tzutc())

    raise ValueError(
        f"Tried to convert a datetime from unsupported BaseSettings value ({value})."
    )


def to_decimal(value):
    if isinstance(value, float):
        # If we don't convert to string first, we could end up with an
        # undesirable binaryFloat --> Decimal conversion.
        # Converting it to a string first seems to preserve the original non-binary meaning better.
        value = str(value)

    return Decimal(value)


DEFAULT_CONVERTERS: Dict[Type, Callable[[Any], Any]] = {
    Decimal: to_decimal,
    dt.date: to_date,
    dt.datetime: to_datetime,
    bool: to_bool,
}
"""
Map of a basic type to it's default converter function;
used by settings to convert to/from basic types.
"""
