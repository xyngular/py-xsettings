# It's both an attribute and a value error
# (attribute is missing and/or value has some other issue)
# `AttributeError` helps pdoc3 know that there is no value safely
# (ie: it will continue to generate docs).
class SettingsValueError(ValueError, AttributeError):
    pass
