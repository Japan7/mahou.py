from abc import ABC, abstractmethod


class Parser[T](ABC):
    @abstractmethod
    def parse(self, _: str) -> T:
        raise NotImplementedError()
