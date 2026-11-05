from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.adapters.firefox import FirefoxAdapter
from session_snapshot.adapters.terminal import TerminalAdapter


def register_builtin_adapters(registry: AdapterRegistry) -> None:
    """Register every adapter that ships with the project.

    Each new adapter adds exactly one line here.
    """
    registry.register(TerminalAdapter())
    registry.register(FirefoxAdapter())
