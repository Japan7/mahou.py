import tempfile
from collections import defaultdict
from typing import TypedDict, override

from jinja2 import Environment, PackageLoader, select_autoescape

from mahou.models.openapi import (
    ArrayType,
    BodySchema,
    ParameterPosition,
    PrimitiveType,
    Schema,
    Server,
    SimpleSchema,
    UnionType,
)
from mahou.serializers.abc import Serializer
from mahou.utils import ruff_fix, ruff_format

STR_FORMATS = {
    "uuid": "UUID",
    "date-time": "datetime",
}

STR_FORMATS_IMPORTS = {
    "UUID": "from uuid import UUID",
    "datetime": "from datetime import datetime",
}

FORM_IMPORT = "from dataclasses import asdict"


class ServerDefinition(TypedDict):
    name: str
    url: str


class OpenAPIaiohttpClientSerializer(Serializer[Server]):
    def __init__(self):
        self.need_typing = {}
        self.model_types = set()
        self.extra_imports = set()

    @override
    def serialize(self, input: Server) -> str:
        servers: list[ServerDefinition] = []
        modules = defaultdict(list)

        if len(input.urls) == 1:
            servers.append({"name": "", "url": input.urls[0]})
        else:
            for url in input.urls:
                servers.append({"name": url[1:].replace("/", "_"), "url": url})

        for path in input.paths:
            for request in path.requests:
                operation = {
                    "name": request.operation_id,
                    "method": request.method.value,
                    "endpoint": path.endpoint,
                    "required_arguments": [],
                    "optional_arguments": [],
                    "responses_success": {},
                    "responses_error": {},
                    "query_parameters": [],
                    "path_parameters": [],
                    "body": False,
                }

                for parameter in request.parameters:
                    serialized_type = self.serialize_type(parameter.type)

                    argument = {"name": parameter.name, "type": serialized_type}
                    if parameter.required:
                        operation["required_arguments"].append(argument)
                    else:
                        operation["optional_arguments"].append(argument)

                    if parameter.position is ParameterPosition.QUERY:
                        operation["query_parameters"].append(parameter.name)
                    else:
                        operation["path_parameters"].append(parameter.name)

                if request.body:
                    argument = {
                        "name": "body",
                        "type": self.serialize_type(request.body.type),
                    }
                    operation["body"] = True
                    if request.body.required:
                        operation["required_arguments"].append(argument)
                    else:
                        operation["optional_arguments"].append(argument)
                    operation["body_schema"] = (
                        request.body.body_schema.name
                        if request.body.body_schema
                        else None
                    )
                    if request.body.body_schema is BodySchema.FORM:
                        self.extra_imports.add(FORM_IMPORT)

                for response_code, response_type in request.responses.items():
                    if response_code > 199 and response_code < 300:
                        operation["responses_success"][
                            response_code
                        ] = self.serialize_type(response_type)
                    else:
                        operation["responses_error"][
                            response_code
                        ] = self.serialize_type(response_type)

                for tag in request.tags:
                    modules[tag].append(operation)

        jinja_env = Environment(
            loader=PackageLoader("mahou"), autoescape=select_autoescape()
        )
        template = jinja_env.get_template("aiohttp_client.py.jinja")

        rendered = template.render(
            servers=servers,
            modules=modules,
            need_typing=self.need_typing,
            model_types=self.model_types,
            extra_imports=self.extra_imports,
        )

        # FIXME: I'm lazy
        rendered = rendered.replace(" | None | None", " | None")

        with tempfile.NamedTemporaryFile("w") as fp:
            fp.write(rendered)
            ruff_fix(fp.name)
            ruff_format(fp.name)
            with open(fp.name, "r") as fp2:
                return fp2.read()

    def serialize_type(self, parsed_type: Schema | None) -> str:
        if not parsed_type:
            return PrimitiveType.NONE.value

        return self.serialize_schema_type(parsed_type)

    def serialize_schema_type(self, schema_type: Schema) -> str:
        if isinstance(schema_type, SimpleSchema):
            parsed_type = schema_type.type
            if schema_type.enum:
                serialized_type = (
                    f'Literal[{",".join([repr(v) for v in schema_type.enum])}]'
                )
            elif isinstance(parsed_type, PrimitiveType):
                if parsed_type is PrimitiveType.STR and schema_type.format is not None:
                    match = STR_FORMATS.get(schema_type.format, None)
                    if match is not None:
                        serialized_type = match
                        extra_import = STR_FORMATS_IMPORTS.get(match, None)
                        if extra_import is not None:
                            self.extra_imports.add(extra_import)
                    else:  # fallback
                        serialized_type = PrimitiveType.ANY.value
                else:
                    serialized_type = parsed_type.value
                if parsed_type is PrimitiveType.ANY:
                    self.need_typing["any"] = True
            elif isinstance(parsed_type, ArrayType):
                serialized_type = self.serialize_array_type(parsed_type)
            elif isinstance(parsed_type, UnionType):
                serialized_type = self.serialize_union_type(parsed_type)
            else:
                raise RuntimeError("Unknown type")
        else:
            serialized_type = schema_type.title
            self.model_types.add(serialized_type)

        return serialized_type

    def serialize_union_type(self, union_type: UnionType) -> str:
        serialized_type_array = []
        for t in union_type.any_of:
            if isinstance(t, PrimitiveType):
                serialized_type_array.append(t.value)
                if t is PrimitiveType.ANY:
                    self.need_typing["any"] = True
            elif isinstance(t, ArrayType):
                serialized_type_array.append(self.serialize_array_type(t))
            elif isinstance(t, Schema):
                serialized_type_array.append(self.serialize_schema_type(t))
            else:
                raise RuntimeError("Unknown type")

        return " | ".join(serialized_type_array)

    def serialize_array_type(self, array_type: ArrayType) -> str:
        items = array_type.items
        if isinstance(items, PrimitiveType):
            serialized_type = items.value
            if items is PrimitiveType.ANY:
                self.need_typing["any"] = True
        elif isinstance(items, ArrayType):
            serialized_type = self.serialize_array_type(items)
        elif isinstance(items, UnionType):
            serialized_type = self.serialize_union_type(items)
        elif isinstance(items, Schema):
            serialized_type = self.serialize_schema_type(items)
        else:
            raise RuntimeError("Unknown type")

        return f"list[{serialized_type}]"
