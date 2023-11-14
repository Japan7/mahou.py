from abc import ABC, abstractmethod


class Serializer[T](ABC):
    @abstractmethod
    def serialize(self, _: T) -> str:
        raise NotImplementedError()
