from abc import ABC, abstractmethod


class Parser[T](ABC):
    @abstractmethod
    def parse(self, input: str) -> T:
        raise NotImplementedError()
