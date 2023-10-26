from typing import Generic, TypeVar


T = TypeVar("T")


class Parser(Generic[T]):
    def parse(self, _: str) -> T:
        raise NotImplementedError()
