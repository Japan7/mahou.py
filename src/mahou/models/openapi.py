from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PrimitiveType(Enum):
    INT = 'int'
    FLOAT = 'float'
    BOOL = 'bool'
    STR = 'str'
    ANY = 'Any'


@dataclass
class UnionType():
    any_of: list[PrimitiveType]


@dataclass
class Schema():
    title: str


@dataclass
class ArrayType():
    items: UnionType | Schema


@dataclass
class SimpleSchema(Schema):
    type: PrimitiveType | ArrayType
    format: Optional[str] = None


@dataclass
class ComplexSchema(Schema):
    properties: dict[str, Schema]
    required_properties: list[str]


@dataclass
class EnumSchema(Schema):
    enum_values: list[str]
    description: str


class ParameterPosition(Enum):
    QUERY = 1
    PATH = 2


@dataclass
class Parameter():
    name: str
    position: ParameterPosition
    required: bool
    type: Schema


class RequestMethod(Enum):
    GET = 1
    POST = 2


@dataclass
class Request():
    method: RequestMethod
    summary: Optional[str]
    operation_id: Optional[str]
    parameters: list[Parameter]


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
