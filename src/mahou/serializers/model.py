import re

import black
from jinja2 import Environment, PackageLoader, select_autoescape

from mahou.models.openapi import (ArrayType, ComplexSchema, EnumSchema, PrimitiveType, Schema,
                                  SimpleSchema, UnionType)
from mahou.serializers.abc import Serializer


class OpenAPIModelSerializer(Serializer[list[Schema]]):
    def serialize(self, input: list[Schema]) -> str:
        enum_forbidden_chars = re.compile('[^a-zA-Z0-9_]')

        enums = []
        dataclasses = []
        need_typing = {}

        for schema in input:
            if isinstance(schema, EnumSchema):
                enum = {'name': schema.title, 'elements': []}
                enum['elements'] = [{'name': enum_forbidden_chars.sub('_', v), 'value': f"'{v}'"}
                                    for v in schema.enum_values]
                if enum['name'] not in [e['name'] for e in enums]:
                    enums.append(enum)
            elif isinstance(schema, ComplexSchema):
                dataclass = {'name': schema.title, 'required_elements': [],
                             'optional_elements': []}
                for property_name, property_schema in schema.properties.items():
                    serialized_type = ''
                    if isinstance(property_schema, SimpleSchema):
                        property_type = property_schema.type
                        if isinstance(property_type, PrimitiveType):
                            serialized_type = property_type.value
                            if property_type == PrimitiveType.ANY:
                                need_typing['any'] = True
                        elif isinstance(property_type, ArrayType):
                            items = property_type.items
                            if isinstance(items, UnionType):
                                serialized_type = ' | '.join([t.value for t in items.any_of])
                                if PrimitiveType.ANY in items.any_of:
                                    need_typing['any'] = True
                            elif isinstance(items, ComplexSchema):
                                serialized_type = f"'{items.title}'"
                            serialized_type = f'list[{serialized_type}]'
                    else:
                        serialized_type = f"'{property_schema.title}'"

                    if property_name in schema.required_properties:
                        dataclass['required_elements'].append({'name': property_name,
                                                               'type': serialized_type})
                    else:
                        dataclass['optional_elements'].append({'name': property_name,
                                                               'type': serialized_type})
                        need_typing['optional'] = True

                if dataclass['name'] not in [d['name'] for d in dataclasses]:
                    dataclasses.append(dataclass)

        jinja_env = Environment(loader=PackageLoader('mahou'), autoescape=select_autoescape())
        template = jinja_env.get_template('model.py.jinja')

        return black.format_file_contents(template.render(enums=enums, dataclasses=dataclasses,
                                                          need_typing=need_typing),
                                          fast=False, mode=black.FileMode())
