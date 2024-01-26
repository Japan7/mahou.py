import re
import tempfile

from jinja2 import Environment, PackageLoader, select_autoescape

from mahou.models.openapi import (
    ArrayType,
    ComplexSchema,
    EnumSchema,
    PrimitiveType,
    Schema,
    SimpleSchema,
    UnionType,
)
from mahou.serializers.abc import Serializer
from mahou.utils import alias_invalid_id, ruff_fix, ruff_format

STR_FORMATS = {
    "uuid": "UUID",
    "date-time": "datetime",
}

STR_FORMATS_IMPORTS = {
    "UUID": "from uuid import UUID",
    "datetime": "from datetime import datetime",
}


class OpenAPIModelSerializer(Serializer[list[Schema]]):
    def __init__(self):
        self.need_typing = {}
        self.extra_imports = set()

    def serialize(self, input: list[Schema]) -> str:
        enum_forbidden_chars = re.compile("[^a-zA-Z0-9_]")

        enums = []
        dataclasses = []

        for schema in input:
            if isinstance(schema, EnumSchema):
                enum = {"name": schema.title, "elements": []}
                enum["elements"] = [
                    {"name": enum_forbidden_chars.sub("_", v), "value": f"'{v}'"}
                    for v in schema.enum_values
                ]
                if enum["name"] not in [e["name"] for e in enums]:
                    enums.append(enum)
            elif isinstance(schema, ComplexSchema):
                dataclass = {
                    "name": schema.title,
                    "required_elements": [],
                    "optional_elements": [],
                }
                for property_name, property_schema in schema.properties.items():
                    serialized_type = self.serialize_type(property_schema)
                    name, alias = alias_invalid_id(property_name)
                    dataclass[
                        "required_elements"
                        if property_name in schema.required_properties
                        else "optional_elements"
                    ].append(
                        {
                            "name": name,
                            "type": serialized_type,
                            "alias": alias,
                        }
                    )
                if dataclass["name"] not in [d["name"] for d in dataclasses]:
                    dataclasses.append(dataclass)
            else:
                raise RuntimeError("Unknown schema")

        jinja_env = Environment(
            loader=PackageLoader("mahou"), autoescape=select_autoescape()
        )
        template = jinja_env.get_template("model.py.jinja")

        rendered = template.render(
            enums=enums,
            dataclasses=dataclasses,
            need_typing=self.need_typing,
            extra_imports=self.extra_imports,
        )

        # FIXME: I'm lazy
        rendered = rendered.replace(" | None | None", " | None")
        rendered = rendered.replace("' | None", " | None'")

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
        serialized_type = f"'{schema_type.title}'"
        if isinstance(schema_type, SimpleSchema):
            parsed_type = schema_type.type
            if schema_type.enum:
                serialized_type = (
                    f'Literal[{",".join([repr(v) for v in schema_type.enum])}]'
                )
                self.need_typing["literal"] = True
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
