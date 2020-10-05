"""
taken from

http://www.djangosnippets.org/snippets/377/

and adapted to LDObject
"""


import json
from django.db import models

from . import LDObject


class LDObjectField(models.TextField):
    """
    LDObject is a generic textfield that neatly serializes/unserializes
    JSON objects seamlessly.

    deserialization_params added on 2011-01-09 to provide additional hints at deserialization time
    """

    def __init__(self, type_hint=None, **kwargs):
        self.type_hint = type_hint
        super(LDObjectField, self).__init__(**kwargs)

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        """Convert our string value to LDObject after we load it from the DB"""

        # did we already convert this?
        if not isinstance(value, str):
            return value

        if value is None:
            return None

        # in some cases, we're loading an existing array or dict,
        # we skip this part but instantiate the LD object
        if isinstance(value, str):
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                raise Exception("value is not JSON parseable, that's bad news")
        else:
            parsed_value = value

        if parsed_value is not None:
            "we give the wrapped object back because we're not dealing with serialization types"
            return_val = LDObject.fromDict(parsed_value, type_hint=self.type_hint).wrapped_obj
            return return_val
        else:
            return None

    def get_prep_value(self, value, *args, **kwargs):
        """Convert our JSON object to a string before we save"""
        if isinstance(value, str):
            return value

        if value is None:
            return None

        # instantiate the proper LDObject to dump it appropriately
        ld_object = LDObject.instantiate(value, datatype=self.type_hint)
        return ld_object.serialize()

    def value_to_string(self, obj, *args, **kwargs):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value, *args, **kwargs)
