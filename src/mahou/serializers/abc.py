from abc import ABC, abstractmethod


class Serializer[T](ABC):
    @abstractmethod
    def serialize(self, input: T) -> str:
        raise NotImplementedError()
