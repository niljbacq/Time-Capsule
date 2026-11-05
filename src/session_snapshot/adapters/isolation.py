from typing import Callable, TypeVar

from session_snapshot.adapters.base import AdapterError
from session_snapshot.models.results import OpResult, Reason

T = TypeVar("T")


def guarded(
    adapter_id: str,
    operation: str,
    fn: Callable[..., T],
    *args,
    **kwargs,
) -> tuple[T | None, OpResult | None]:
    """Run one adapter call. Returns (value, None) on success or (None, failed_result).

    Any exception from the adapter becomes a FAILED result so that one broken
    adapter can never stop the rest of a save or restore.
    """
    try:
        return fn(*args, **kwargs), None
    except AdapterError as exc:
        details = {**exc.details, "adapter_id": adapter_id, "operation": operation}
        return None, OpResult.failed(exc.reason, exc.message, **details)
    except Exception as exc:  # noqa: BLE001 - isolation boundary, by design
        return None, OpResult.failed(
            Reason.ADAPTER_ERROR,
            f"{adapter_id}.{operation} raised {type(exc).__name__}: {exc}",
            adapter_id=adapter_id,
            operation=operation,
            exception=type(exc).__name__,
        )
