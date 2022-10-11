from jinja2 import Environment, PackageLoader, select_autoescape

from mahou.models.openapi import ArrayType, ComplexSchema, PrimitiveType, Server, SimpleSchema, UnionType
from mahou.serializers.abc import Serializer


class OpenAPIaiohttpClientSerializer(Serializer[list[Server]]):
    def serialize(self, input: Server) -> str:
        servers = []
        operations = []
        need_typing = {}
        model_types = set()

        for url in input.urls:
            servers.append({'name': url[1:].replace('/', '_'), 'url': url})

        for path in input.paths:
            for request in path.requests:
                operation = {'name': request.operation_id,
                             'required_arguments': [],
                             'optional_arguments': [],
                             'response_type': 'None'}

                for parameter in request.parameters:
                    serialized_type = ''
                    if isinstance(parameter.type, SimpleSchema):
                        parameter_type = parameter.type.type
                        if isinstance(parameter_type, PrimitiveType):
                            serialized_type = parameter_type.value
                            if parameter_type == PrimitiveType.ANY:
                                need_typing['any'] = True
                        elif isinstance(parameter_type, ArrayType):
                            items = parameter_type.items
                            if isinstance(items, UnionType):
                                serialized_type = ' | '.join([t.value for t in items.any_of])
                                if PrimitiveType.ANY in items.any_of:
                                    need_typing['any'] = True
                            elif isinstance(items, ComplexSchema):
                                serialized_type = items.title
                                model_types.add(serialized_type)
                            serialized_type = f'list[{serialized_type}]'
                    else:
                        serialized_type = parameter.type.title
                        model_types.add(serialized_type)

                    argument = {'name': parameter.name, 'type': serialized_type}
                    if parameter.required:
                        operation['required_arguments'].append(argument)
                    else:
                        operation['optional_arguments'].append(argument)

                operations.append(operation)

        jinja_env = Environment(loader=PackageLoader('mahou'), autoescape=select_autoescape())
        template = jinja_env.get_template('aiohttp_client.py.jinja')

        return template.render(servers=servers, operations=operations,
                               need_typing=need_typing, model_types=model_types).strip()
