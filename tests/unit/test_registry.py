import pytest

from session_snapshot.adapters.registry import AdapterRegistrationError, AdapterRegistry
from tests.fakes.fake_adapter import FakeAdapter


def test_register_and_get():
    reg = AdapterRegistry()
    a = FakeAdapter()
    reg.register(a)
    assert reg.get("fake") is a
    assert "fake" in reg
    assert len(reg) == 1


def test_duplicate_id_rejected():
    reg = AdapterRegistry()
    reg.register(FakeAdapter())
    with pytest.raises(AdapterRegistrationError):
        reg.register(FakeAdapter())


def test_invalid_adapter_id_rejected():
    reg = AdapterRegistry()
    with pytest.raises(AdapterRegistrationError):
        reg.register(FakeAdapter(adapter_id="Bad ID!"))


def test_invalid_version_rejected():
    reg = AdapterRegistry()
    a = FakeAdapter()
    a.version = 0
    with pytest.raises(AdapterRegistrationError):
        reg.register(a)


def test_invalid_compatibility_class_rejected():
    reg = AdapterRegistry()
    a = FakeAdapter()
    a.compatibility_class = 3
    with pytest.raises(AdapterRegistrationError):
        reg.register(a)


def test_unknown_adapter_returns_none():
    assert AdapterRegistry().get("nope") is None


def test_all_is_sorted_by_id():
    reg = AdapterRegistry()
    reg.register(FakeAdapter(adapter_id="zeta"))
    reg.register(FakeAdapter(adapter_id="alpha"))
    assert reg.ids() == ["alpha", "zeta"]
    assert [a.adapter_id for a in reg.all()] == ["alpha", "zeta"]
