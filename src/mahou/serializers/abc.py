from typing import Generic, TypeVar


T = TypeVar("T")


class Serializer(Generic[T]):
    def serilize(self, _: T) -> str:
        raise NotImplementedError()
