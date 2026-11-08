"""Navigation model for the GUI shell: the five pages and the sidebar state.

Pure Python, no Qt. The label doubles as the tooltip shown in collapsed mode.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    id: str
    label: str
    icon: str


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("dashboard", "Dashboard", "layout-dashboard"),
    NavItem("sessions", "Sessions", "layers"),
    NavItem("applications", "Applications & Adapters", "puzzle"),
    NavItem("activity", "Activity & Reports", "activity"),
    NavItem("settings", "Settings", "settings"),
)

DEFAULT_PAGE = "dashboard"


def page_ids() -> tuple[str, ...]:
    return tuple(item.id for item in NAV_ITEMS)


def nav_item(page_id: object) -> NavItem | None:
    for item in NAV_ITEMS:
        if item.id == page_id:
            return item
    return None


def page_index(page_id: str) -> int:
    """Position of a page in the navigation order; ValueError if unknown."""
    return page_ids().index(page_id)


def normalize_page(value: object) -> str:
    """Return value if it names a page, else the default page."""
    item = nav_item(value)
    return item.id if item is not None else DEFAULT_PAGE


class NavigationState:
    """Which page is active and whether the sidebar is collapsed."""

    def __init__(self, collapsed: bool = False, active: object = DEFAULT_PAGE) -> None:
        self.collapsed: bool = collapsed is True
        self.active: str = normalize_page(active)

    def select(self, page_id: object) -> bool:
        """Make a page active. Returns False and changes nothing if unknown."""
        item = nav_item(page_id)
        if item is None:
            return False
        self.active = item.id
        return True

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = collapsed is True

    def toggle_collapsed(self) -> bool:
        """Flip the sidebar state and return the new value."""
        self.collapsed = not self.collapsed
        return self.collapsed