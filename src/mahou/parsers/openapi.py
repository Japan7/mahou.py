import json

from mahou.models.openapi import (ArrayType, ComplexSchema, PrimitiveType, SimpleSchema,
                                  EnumSchema, Schema, Server, UnionType)
from mahou.parsers.abc import Parser


class OpenAPIParser(Parser[Server]):
    def parse(self, input: str) -> Server:
        return self.server_from_json(json.loads(input))

    def server_from_json(self, input: dict) -> Server:
        server = Server(title=input['info']['title'],
                        version=input['info']['version'],
                        urls=[server['url'] for server in input['servers']],
                        paths=[],
                        schemas={})

        server.schemas = self.schemas_from_json(input['components']['schemas'])

        return server

    def schemas_from_json(self, input: dict) -> dict[str, Schema]:
        schemas = {}

        def schema_from_json(json_schema: dict) -> Schema:
            if 'enum' in json_schema:
                return EnumSchema(title=json_schema['title'],
                                  description=json_schema['description'],
                                  enum_values=json_schema['enum'])
            else:
                schema = ComplexSchema(title=json_schema['title'],
                                       properties={},
                                       required_properties=[])
                if 'required' in json_schema:
                    schema.required_properties = json_schema['required']
                for name, json_property in json_schema['properties'].items():
                    if '$ref' in json_property:
                        ref_schema_title = json_property['$ref'].split('/')[-1]
                        if ref_schema_title in schemas:
                            property = schemas[ref_schema_title]
                        else:
                            property = schema_from_json(input[ref_schema_title])
                    else:
                        if 'type' in json_property:
                            json_type = json_property['type']
                            if json_type == 'array':
                                json_items = json_property['items']
                                if '$ref' in json_items:
                                    ref_schema_title = (json_items['$ref'].split('/')[-1])
                                    if ref_schema_title in schemas:
                                        items = schemas[ref_schema_title]
                                    else:
                                        items = schema_from_json(input[ref_schema_title])
                                else:
                                    any_of = []
                                    for t in json_items['anyOf']:
                                        any_of.append(self.primitive_type_from_json(t['type']))
                                    items = UnionType(any_of=any_of)

                                property_type = ArrayType(items=items)
                            else:
                                property_type = self.primitive_type_from_json(json_type)
                        else:
                            property_type = PrimitiveType.ANY
                        property = SimpleSchema(title=json_property['title'],
                                                type=property_type)
                        if 'format' in json_property:
                            property.format = json_property['format']

                    schema.properties[name] = property

                return schema

        for name, json_schema in input.items():
            if name not in schemas:
                schemas[name] = schema_from_json(json_schema)

        return schemas

    def primitive_type_from_json(self, json_type: str) -> PrimitiveType:
        if json_type == 'integer':
            return PrimitiveType.INT
        elif json_type == 'number':
            return PrimitiveType.FLOAT
        elif json_type == 'boolean':
            return PrimitiveType.BOOL
        elif json_type == 'string':
            return PrimitiveType.STR
        else:
            raise NotImplementedError(f'Unknown primitive type {json_type}')
