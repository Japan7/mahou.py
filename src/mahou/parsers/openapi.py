import json
from typing import cast, override

from mahou.models.openapi import (
    ArrayType,
    BodySchema,
    ComplexSchema,
    EnumSchema,
    Parameter,
    ParameterPosition,
    Path,
    PrimitiveType,
    Request,
    RequestMethod,
    Schema,
    Server,
    SimpleSchema,
    UnionType,
    Variable,
)
from mahou.parsers.abc import Parser


class OpenAPIParser(Parser[Server]):
    def __init__(self):
        self.parsed_schemas = {}

    @override
    def parse(self, input: str) -> Server:
        return self.server_from_json(json.loads(input))

    def server_from_json(self, input: dict) -> Server:
        if "servers" not in input:
            urls = ["/"]
        else:
            urls = [server["url"] for server in input["servers"]]

        server = Server(
            title=input["info"]["title"],
            version=input["info"]["version"],
            urls=urls,
            paths=[],
            schemas={},
        )

        server.schemas = self.schemas_from_json(input["components"]["schemas"])
        server.paths = self.paths_from_json(input["paths"])

        return server

    def schemas_from_json(self, input: dict) -> dict[str, Schema]:
        self.parsed_schemas = {}
        for name, json_schema in input.items():
            if name not in self.parsed_schemas:
                self.parsed_schemas[name] = self.schema_from_json(json_schema, input)

        return self.parsed_schemas

    def schema_from_json(self, json_schema: dict, input) -> Schema:
        if "enum" in json_schema:
            return EnumSchema(
                title=json_schema["title"],
                enum_values=json_schema["enum"],
            )
        else:
            schema = ComplexSchema(
                title=json_schema["title"], properties={}, required_properties=[]
            )
            if "required" in json_schema:
                schema.required_properties = json_schema["required"]
            for name, json_property in json_schema["properties"].items():
                if "$ref" in json_property:
                    ref_schema_title = json_property["$ref"].split("/")[-1]
                    if ref_schema_title in self.parsed_schemas:
                        property = self.parsed_schemas[ref_schema_title]
                    else:
                        property = self.schema_from_json(input[ref_schema_title], input)
                elif "anyOf" in json_property:
                    property = SimpleSchema(
                        title=json_property.get("title", None),
                        type=self.union_type_from_json(json_property["anyOf"], input),
                    )
                else:
                    if "type" in json_property:
                        json_type = json_property["type"]
                        if json_type == "array":
                            property_type = self.array_type_from_json(
                                json_property["items"], input
                            )
                        else:
                            property_type = self.primitive_type_from_json(json_type)
                    else:
                        property_type = PrimitiveType.ANY
                    property = SimpleSchema(
                        title=json_property["title"],
                        type=property_type,
                        format=json_property.get("format", None),
                        enum=json_property.get("enum", None),
                    )

                schema.properties[name] = property

            return schema

    def union_type_from_json(self, json_union: dict, input: dict) -> UnionType:
        any_of = []
        for t in json_union:
            if "$ref" in t:
                ref_schema_title = t["$ref"].split("/")[-1]
                if ref_schema_title in self.parsed_schemas:
                    any_of.append(self.parsed_schemas[ref_schema_title])
                else:
                    any_of.append(self.schema_from_json(input[ref_schema_title], input))
            else:
                json_type = t["type"]
                if json_type == "array":
                    any_of.append(self.array_type_from_json(t["items"], input))
                else:
                    item_type = self.primitive_type_from_json(json_type)
                    if "format" in t or "enum" in t:
                        item_type = SimpleSchema(
                            title=t.get("title", None),
                            type=item_type,
                            format=t.get("format", None),
                            enum=t.get("enum", None),
                        )
                    any_of.append(item_type)

        return UnionType(any_of=any_of)

    def array_type_from_json(self, json_array: dict, input: dict) -> ArrayType:
        if "$ref" in json_array:
            ref_schema_title = json_array["$ref"].split("/")[-1]
            if ref_schema_title in self.parsed_schemas:
                items = cast(ComplexSchema, self.parsed_schemas[ref_schema_title])
            else:
                items = cast(
                    ComplexSchema, self.schema_from_json(input[ref_schema_title], input)
                )
        elif "anyOf" in json_array:
            items = self.union_type_from_json(json_array["anyOf"], input)
        elif json_array["type"] == "array":
            items = self.array_type_from_json(json_array["items"], input)
        else:
            items = self.primitive_type_from_json(json_array["type"])

        return ArrayType(items=items)

    def paths_from_json(self, input: dict) -> list[Path]:
        paths = []
        for endpoint, requests in input.items():
            paths.append(
                Path(endpoint=endpoint, requests=self.requests_from_json(requests))
            )

        return paths

    def requests_from_json(self, input: dict) -> list[Request]:
        requests = []
        for request_method, request_json in input.items():
            request = Request(
                method=RequestMethod(request_method),
                summary=request_json.get("summary", None),
                description=request_json.get("description", None),
                operation_id=request_json["operationId"],
                parameters=self.request_parameters_from_json(
                    request_json["parameters"] if "parameters" in request_json else {}
                ),
                responses=self.request_responses_from_json(request_json["responses"]),
                tags=[],
            )
            if "tags" in request_json:
                request.tags = request_json["tags"]
            if "requestBody" in request_json:
                request.body = self.request_body_from_json(request_json["requestBody"])
            requests.append(request)

        return requests

    def request_body_from_json(self, input: dict) -> Variable:
        content = input["content"]
        body_schema = list(content.keys())[0]
        return Variable(
            required=input["required"],
            type=self.lookup_schema_from_json(content[body_schema]["schema"]),
            body_schema=BodySchema(body_schema),
        )

    def request_parameters_from_json(self, input: dict) -> list[Parameter]:
        parameters = []
        for parameter_json in input:
            parameter = Parameter(
                name=parameter_json["name"],
                required=parameter_json["required"],
                position=(
                    ParameterPosition.QUERY
                    if parameter_json["in"] == "query"
                    else ParameterPosition.PATH
                ),
                type=self.lookup_schema_from_json(parameter_json["schema"]),
                body_schema=None,
            )
            parameters.append(parameter)

        return parameters

    def request_responses_from_json(self, input: dict) -> dict[int, Schema | None]:
        responses = {}
        for response_code, response_json in input.items():
            if (
                "content" in response_json
                and response_json["content"]["application/json"]["schema"]
            ):
                responses[int(response_code)] = self.lookup_schema_from_json(
                    response_json["content"]["application/json"]["schema"]
                )
            else:
                responses[int(response_code)] = None

        return responses

    def lookup_schema_from_json(self, input: dict) -> Schema:
        if "$ref" in input:
            ref_schema_title = input["$ref"].split("/")[-1]
            return self.parsed_schemas[ref_schema_title]
        elif "anyOf" in input:
            return SimpleSchema(
                title=input["title"],
                type=self.lookup_union_type_from_json(input["anyOf"]),
            )
        else:
            if "type" in input:
                json_type = input["type"]
                if json_type == "array":
                    schema_type = self.lookup_array_type_from_json(input["items"])
                else:
                    schema_type = self.primitive_type_from_json(json_type)
            else:
                schema_type = PrimitiveType.ANY

            schema = SimpleSchema(
                title=input["title"],
                type=schema_type,
                format=input.get("format", None),
                enum=input.get("enum", None),
            )
            return schema

    def lookup_union_type_from_json(self, json_union: dict) -> UnionType:
        any_of = []
        for t in json_union:
            if "$ref" in t:
                ref_schema_title = t["$ref"].split("/")[-1]
                any_of.append(self.parsed_schemas[ref_schema_title])
            else:
                json_type = t["type"]
                if json_type == "array":
                    any_of.append(self.lookup_array_type_from_json(t["items"]))
                else:
                    item_type = self.primitive_type_from_json(json_type)
                    if "format" in t or "enum" in t:
                        item_type = SimpleSchema(
                            title=t.get("title", None),
                            type=item_type,
                            format=t.get("format", None),
                            enum=t.get("enum", None),
                        )
                    any_of.append(item_type)

        return UnionType(any_of=any_of)

    def lookup_array_type_from_json(self, json_array: dict) -> ArrayType:
        if "$ref" in json_array:
            ref_schema_title = json_array["$ref"].split("/")[-1]
            items = cast(ComplexSchema, self.parsed_schemas[ref_schema_title])
        elif "anyOf" in json_array:
            items = self.lookup_union_type_from_json(json_array["anyOf"])
        elif json_array["type"] == "array":
            items = self.lookup_array_type_from_json(json_array["items"])
        else:
            items = self.primitive_type_from_json(json_array["type"])

        return ArrayType(items=items)

    def primitive_type_from_json(self, json_type: str) -> PrimitiveType:
        if json_type == "integer":
            return PrimitiveType.INT
        elif json_type == "number":
            return PrimitiveType.FLOAT
        elif json_type == "boolean":
            return PrimitiveType.BOOL
        elif json_type == "string":
            return PrimitiveType.STR
        elif json_type == "object":
            return PrimitiveType.OBJECT
        elif json_type == "null":
            return PrimitiveType.NONE
        else:
            raise NotImplementedError(f"Unknown primitive type {json_type}")
