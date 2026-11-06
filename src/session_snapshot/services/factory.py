from pathlib import Path

from session_snapshot.adapters.builtin import register_builtin_adapters
from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.discovery import PsutilProcessSource
from session_snapshot.core.events import EventBus
from session_snapshot.services.session_service import SessionService
from session_snapshot.store.manifests import ManifestStore
from session_snapshot.windows.x11 import X11Backend


def create_default_service(
    store_root: Path | None = None, bus: EventBus | None = None
) -> SessionService:
    registry = AdapterRegistry()
    register_builtin_adapters(registry)
    return SessionService(
        registry,
        ManifestStore(store_root),
        PsutilProcessSource(),
        bus=bus,
        window_backend=X11Backend(),
    )
