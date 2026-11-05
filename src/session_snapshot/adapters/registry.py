import re

from session_snapshot.adapters.base import SessionAdapter

ADAPTER_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class AdapterRegistrationError(Exception):
    """Raised when an adapter is invalid or its id is already registered."""


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SessionAdapter] = {}

    def register(self, adapter: SessionAdapter) -> None:
        adapter_id = getattr(adapter, "adapter_id", None)
        version = getattr(adapter, "version", None)
        cls = getattr(adapter, "compatibility_class", None)

        if not isinstance(adapter_id, str) or not ADAPTER_ID_RE.match(adapter_id):
            raise AdapterRegistrationError(f"invalid adapter id: {adapter_id!r}")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise AdapterRegistrationError(
                f"adapter {adapter_id!r}: version must be an integer >= 1"
            )
        if cls not in (1, 2):
            raise AdapterRegistrationError(
                f"adapter {adapter_id!r}: compatibility_class must be 1 or 2"
            )
        if adapter_id in self._adapters:
            raise AdapterRegistrationError(f"adapter already registered: {adapter_id!r}")
        self._adapters[adapter_id] = adapter

    def get(self, adapter_id: str) -> SessionAdapter | None:
        return self._adapters.get(adapter_id)

    def all(self) -> list[SessionAdapter]:
        return [self._adapters[k] for k in sorted(self._adapters)]

    def ids(self) -> list[str]:
        return sorted(self._adapters)

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, adapter_id: object) -> bool:
        return adapter_id in self._adapters
