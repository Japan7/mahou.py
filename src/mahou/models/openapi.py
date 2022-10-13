from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union


class PrimitiveType(Enum):
    INT = 'int'
    FLOAT = 'float'
    BOOL = 'bool'
    STR = 'str'
    ANY = 'Any'


@dataclass
class Schema():
    title: str


@dataclass
class UnionType():
    any_of: list[Union[PrimitiveType, 'ArrayType', Schema]]


@dataclass
class ArrayType():
    items: Union[UnionType, 'ComplexSchema', PrimitiveType, 'ArrayType']


@dataclass
class SimpleSchema(Schema):
    type: PrimitiveType | ArrayType | UnionType
    enum: Optional[list[Any]] = None
    format: Optional[str] = None


@dataclass
class ComplexSchema(Schema):
    properties: dict[str, Schema]
    required_properties: list[str]


@dataclass
class EnumSchema(Schema):
    enum_values: list[str]
    description: str


@dataclass
class Variable():
    required: bool
    type: Schema


class ParameterPosition(Enum):
    QUERY = 1
    PATH = 2


@dataclass
class Parameter(Variable):
    name: str
    position: ParameterPosition


class RequestMethod(Enum):
    GET = 'get'
    POST = 'post'
    PATCH = 'patch'
    DELETE = 'delete'
    PUT = 'put'


@dataclass
class Request():
    method: RequestMethod
    summary: Optional[str]
    operation_id: Optional[str]
    parameters: list[Parameter]
    responses: dict[int, Optional[Schema]]
    tags: list[str]
    body: Optional[Variable] = None


@dataclass
class Path():
    endpoint: str
    requests: list[Request]


@dataclass
class Server():
    title: str
    version: str
    urls: list[str]
    paths: list[Path]
    schemas: dict[str, Schema]
