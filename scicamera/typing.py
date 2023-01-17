from __future__ import annotations

from concurrent.futures import Future
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class TypedFuture(Future, Generic[T]):
    def add_done_callback(
        self: TypedFuture, fn: Callable[[TypedFuture[T]], Any]
    ) -> None:
        ...

    def cancel(self: TypedFuture) -> bool:
        ...

    def cancelled(self: TypedFuture) -> bool:
        ...

    def done(self: TypedFuture) -> bool:
        ...

    def exception(self):
        ...

    def result(self: TypedFuture[T], timeout: float | None = ...) -> T:
        ...

    def running(self: TypedFuture[T]) -> bool:
        ...

    def set_result(self: TypedFuture[T], result: T) -> None:
        ...

    def set_running_or_notify_cancel(self: TypedFuture[T]) -> bool:
        ...

    def set_exception(self: TypedFuture[T], exception: Exception) -> None:
        ...
