"""
Padrão Result monádico para tratamento explícito e seguro de erros sem quebras por exceções não tratadas.
"""

from typing import TypeVar, Generic, Union, Callable

T = TypeVar("T")
E = TypeVar("E")


class Success(Generic[T]):
    """Representa um resultado bem-sucedido contendo um valor."""
    __slots__ = ("_value",)

    def __init__(self, value: T) -> None:
        self._value = value

    @property
    def value(self) -> T:
        return self._value

    @property
    def is_success(self) -> bool:
        return True

    @property
    def is_failure(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self._value

    def __repr__(self) -> str:
        return f"Success({self._value!r})"


class Failure(Generic[E]):
    """Representa uma falha contendo um erro ou mensagem."""
    __slots__ = ("_error",)

    def __init__(self, error: E) -> None:
        self._error = error

    @property
    def error(self) -> E:
        return self._error

    @property
    def is_success(self) -> bool:
        return False

    @property
    def is_failure(self) -> bool:
        return True

    def unwrap(self) -> T:
        raise ValueError(f"Tentativa de desempacotar um Failure: {self._error!r}")

    def __repr__(self) -> str:
        return f"Failure({self._error!r})"


Result = Union[Success[T], Failure[E]]
