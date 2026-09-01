import pytest
import asyncio
from backend.app.services.interaction_version_manager import InteractionVersionManager

@pytest.mark.asyncio
async def test_initial_version():
    manager = InteractionVersionManager(initial_version=10)
    assert manager.active_version == 10
    assert manager.is_active(10) is True
    assert manager.is_active(9) is False
    assert manager.is_active(11) is False

@pytest.mark.asyncio
async def test_monotonic_version_increment():
    manager = InteractionVersionManager(initial_version=10)
    
    v1 = await manager.create_new_version(reason="First interaction")
    assert v1 == 11
    assert manager.active_version == 11
    assert manager.is_active(11) is True
    assert manager.is_active(10) is False

    v2 = await manager.create_new_version(reason="User correction")
    assert v2 == 12
    assert manager.active_version == 12
    assert manager.is_active(12) is True
    assert manager.is_active(11) is False

@pytest.mark.asyncio
async def test_invalidation_listener():
    manager = InteractionVersionManager(initial_version=10)
    invalidated_pairs = []

    def on_invalidate(old_ver, new_ver):
        invalidated_pairs.append((old_ver, new_ver))

    manager.add_invalidation_listener(on_invalidate)

    await manager.create_new_version()
    await manager.create_new_version()

    assert invalidated_pairs == [(10, 11), (11, 12)]
