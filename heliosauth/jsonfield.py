"""
taken from

http://www.djangosnippets.org/snippets/377/
"""


import json

from django.db import models
from django.core.serializers.json import DjangoJSONEncoder


class JSONField(models.TextField):
    """
    JSONField is a generic textfield that neatly serializes/unserializes
    JSON objects seamlessly.

    deserialization_params added on 2011-01-09 to provide additional hints at deserialization time
    """

    def __init__(self, json_type=None, deserialization_params=None, **kwargs):
        self.json_type = json_type
        self.deserialization_params = deserialization_params
        super(JSONField, self).__init__(**kwargs)

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        """Convert our string value to JSON after we load it from the DB"""

        if self.json_type:
            if isinstance(value, self.json_type):
                return value

        if isinstance(value, dict) or isinstance(value, list):
            return value

        if value == "" or value is None:
            return None

        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            raise Exception("not JSON")

        if self.json_type and parsed_value:
            parsed_value = self.json_type.fromJSONDict(parsed_value, **self.deserialization_params)

        return parsed_value

    # we should never look up by JSON field anyways.
    # def get_prep_lookup(self, lookup_type, value)

    def get_prep_value(self, value, *args, **kwargs):
        """Convert our JSON object to a string before we save"""
        if isinstance(value, str):
            return value

        if value is None:
            return None

        if self.json_type and isinstance(value, self.json_type):
            the_dict = value.toJSONDict()
        else:
            the_dict = value

        return json.dumps(the_dict, cls=DjangoJSONEncoder)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)
