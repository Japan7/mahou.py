from collections import defaultdict

import black
import isort
from jinja2 import Environment, PackageLoader, select_autoescape

from mahou.models.openapi import (ArrayType, ComplexSchema, ParameterPosition,
                                  PrimitiveType, Schema, Server, SimpleSchema, UnionType)
from mahou.serializers.abc import Serializer


class OpenAPIaiohttpClientSerializer(Serializer[list[Server]]):
    def __init__(self):
        self.need_typing = {}
        self.model_types = set()

    def serialize(self, input: Server) -> str:
        servers = []
        modules = defaultdict(list)

        for url in input.urls:
            servers.append({'name': url[1:].replace('/', '_'), 'url': url})

        for path in input.paths:
            for request in path.requests:
                operation = {'name': request.operation_id,
                             'method': request.method.value,
                             'endpoint': path.endpoint,
                             'required_arguments': [],
                             'optional_arguments': [],
                             'responses_success': {},
                             'responses_error': {},
                             'query_parameters': [],
                             'path_parameters': [],
                             'body': False}

                for parameter in request.parameters:
                    serialized_type = self.serialize_type(parameter.type)

                    argument = {'name': parameter.name, 'type': serialized_type}
                    if parameter.required:
                        operation['required_arguments'].append(argument)
                    else:
                        operation['optional_arguments'].append(argument)
                        self.need_typing['optional'] = True

                    if parameter.position == ParameterPosition.QUERY:
                        operation['query_parameters'].append(parameter.name)
                    else:
                        operation['path_parameters'].append(parameter.name)

                if request.body:
                    argument = {'name': 'body', 'type': self.serialize_type(request.body.type)}
                    operation['body'] = True
                    if request.body.required:
                        operation['required_arguments'].append(argument)
                    else:
                        operation['optional_arguments'].append(argument)
                        self.need_typing['optional'] = True

                for response_code, response_type in request.responses.items():
                    if response_code > 199 and response_code < 300:
                        operation['responses_success'][response_code] = self.serialize_type(
                            response_type
                        )
                    else:
                        operation['responses_error'][response_code] = self.serialize_type(
                            response_type
                        )

                for tag in request.tags:
                    modules[tag].append(operation)

        jinja_env = Environment(loader=PackageLoader('mahou'), autoescape=select_autoescape())
        template = jinja_env.get_template('aiohttp_client.py.jinja')

        return isort.code(
            black.format_file_contents(template.render(
                servers=servers,
                modules=modules,
                need_typing=self.need_typing,
                model_types=self.model_types),
                                       fast=False,
                                       mode=black.FileMode()))

    def serialize_type(self, parsed_type: Schema | None) -> str:
        if not parsed_type:
            return 'None'

        return self.serialize_schema_type(parsed_type)

    def serialize_schema_type(self, schema_type: Schema) -> str:
        serialized_type = ''
        if isinstance(schema_type, SimpleSchema):
            parsed_type = schema_type.type
            if isinstance(parsed_type, PrimitiveType):
                serialized_type = parsed_type.value
                if parsed_type == PrimitiveType.ANY:
                    self.need_typing['any'] = True
            elif isinstance(parsed_type, ArrayType):
                serialized_type = self.serialize_array_type(parsed_type)
            elif isinstance(parsed_type, UnionType):
                serialized_type = self.serialize_union_type(parsed_type)
        else:
            serialized_type = schema_type.title
            self.model_types.add(serialized_type)

        return serialized_type

    def serialize_union_type(self, union_type: UnionType) -> str:
        serialized_type_array = []
        for t in union_type.any_of:
            if isinstance(t, PrimitiveType):
                serialized_type_array.append(t.value)
                if t == PrimitiveType.ANY:
                    self.need_typing['any'] = True
            elif isinstance(t, ComplexSchema):
                serialized_type_array.append(t.title)
                self.model_types.add(t.title)
            elif isinstance(t, ArrayType):
                serialized_type_array.append(self.serialize_array_type(t))

        self.need_typing['union'] = True
        return f'Union[{",".join(serialized_type_array)}]'

    def serialize_array_type(self, array_type: ArrayType) -> str:
        items = array_type.items
        serialized_type = ''
        if isinstance(items, UnionType):
            serialized_type = self.serialize_union_type(items)
        elif isinstance(items, ComplexSchema):
            serialized_type = self.serialize_schema_type(items)
        elif isinstance(items, PrimitiveType):
            serialized_type = items.value
            if items == PrimitiveType.ANY:
                self.need_typing['any'] = True

        return f'list[{serialized_type}]'
