from dataclasses import dataclass
from enum import Enum


class PrimitiveType(Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STR = "str"
    OBJECT = "dict[str, Any]"
    ANY = "Any"
    NONE = "None"


@dataclass
class Schema:
    title: str


@dataclass
class UnionType:
    any_of: list["PrimitiveType | ArrayType | Schema"]


@dataclass
class ArrayType:
    items: "PrimitiveType | ArrayType | UnionType | Schema"


@dataclass
class SimpleSchema(Schema):
    type: PrimitiveType | ArrayType | UnionType
    enum: list | None = None
    format: str | None = None


@dataclass
class ComplexSchema(Schema):
    properties: dict[str, Schema]
    required_properties: list[str]


@dataclass
class EnumSchema(Schema):
    enum_values: list[str]


class BodySchema(Enum):
    JSON = "application/json"
    FORM = "application/x-www-form-urlencoded"


@dataclass
class Variable:
    required: bool
    type: Schema
    body_schema: BodySchema | None


class ParameterPosition(Enum):
    QUERY = 1
    PATH = 2


@dataclass
class Parameter(Variable):
    name: str
    position: ParameterPosition


class RequestMethod(Enum):
    GET = "get"
    POST = "post"
    PATCH = "patch"
    DELETE = "delete"
    PUT = "put"


@dataclass
class Request:
    method: RequestMethod
    summary: str | None
    description: str | None
    operation_id: str | None
    parameters: list[Parameter]
    responses: dict[int, Schema | None]
    tags: list[str]
    body: Variable | None = None


@dataclass
class Path:
    endpoint: str
    requests: list[Request]


@dataclass
class Server:
    title: str
    version: str
    urls: list[str]
    paths: list[Path]
    schemas: dict[str, Schema]
