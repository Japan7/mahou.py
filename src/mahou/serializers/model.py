import os
import re
import subprocess
import tempfile

import autoflake
import isort
from jinja2 import Environment, PackageLoader, select_autoescape
from ruff.__main__ import find_ruff_bin

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

                    if property_name in schema.required_properties:
                        dataclass["required_elements"].append(
                            {"name": property_name, "type": serialized_type}
                        )
                    else:
                        dataclass["optional_elements"].append(
                            {"name": property_name, "type": serialized_type}
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

        imports_fixed = isort.code(
            autoflake.fix_code(rendered, remove_all_unused_imports=True)
        )

        with tempfile.NamedTemporaryFile("w") as fp:
            fp.write(imports_fixed)

            ruff = find_ruff_bin()
            completed_process = subprocess.run([os.fsdecode(ruff), "format", fp.name])
            if completed_process.returncode != 0:
                raise RuntimeError("Ruff failed to format the generated code")

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
