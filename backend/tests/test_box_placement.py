"""Box placement method on synthetic buildings (UTM metres). Box types here are TEST values, not real ones."""

import pytest
from shapely.geometry import box as rect

from app.design import box_placement as bp

SMALL = bp.BoxType("small (test)", 8)
LARGE = bp.BoxType("large (test)", 16)


def building(key: str, x: float, y: float, users: int) -> bp.Demand:
    return bp.Demand(key, rect(x, y, x + 10, y + 10), users)


def served_by(boxes: list[bp.PlacedBox]) -> dict[str, list[bp.PlacedBox]]:
    out: dict[str, list[bp.PlacedBox]] = {}
    for b in boxes:
        for s in b.served:
            out.setdefault(s.key, []).append(b)
    return out


def test_every_user_is_served_and_no_box_is_over_capacity() -> None:
    row = [building(str(i), i * 15, 0, users) for i, users in enumerate([3, 4, 5, 2, 6, 1, 7, 3])]
    boxes = bp.place(row, [SMALL, LARGE])
    assert sum(b.users for b in boxes) == 31
    assert all(b.users <= b.usable for b in boxes)
    assert set(served_by(boxes)) == {d.key for d in row}
    assert all(len(v) == 1 for v in served_by(boxes).values())  # each small building: one box


def test_smallest_box_type_that_holds_the_group() -> None:
    boxes = bp.place([building("a", 0, 0, 5)], [LARGE, SMALL])
    assert [b.box_type for b in boxes] == [SMALL]
    boxes = bp.place([building("a", 0, 0, 12)], [LARGE, SMALL])
    assert [b.box_type for b in boxes] == [LARGE]


def test_large_building_gets_several_boxes_on_it() -> None:
    boxes = bp.place([building("tower", 0, 0, 40)], [SMALL, LARGE])
    assert sum(b.users for b in boxes) == 40
    assert [b.dedicated for b in boxes].count(True) == 2  # 2 × 16 full, the last 8 in a normal box
    assert all(b.host == "tower" for b in boxes)
    assert sorted(b.users for b in boxes) == [8, 16, 16]


def test_exact_multiple_keeps_one_box_for_neighbours() -> None:
    boxes = bp.place([building("t", 0, 0, 32), building("n", 12, 0, 0)], [LARGE])
    assert sorted(b.users for b in boxes) == [16, 16]


def test_drop_limit_splits_far_buildings() -> None:
    near = [building("a", 0, 0, 2), building("b", 15, 0, 2)]
    far = [building("c", 500, 0, 2)]
    boxes = bp.place(near + far, [LARGE], max_drop_m=30)
    by = served_by(boxes)
    assert by["a"][0] is by["b"][0] and by["c"][0] is not by["a"][0]
    assert all(s.distance_m <= 30 for b in boxes for s in b.served)
    # without a limit, the three fit in one box
    assert len(bp.place(near + far, [LARGE])) == 1


def test_box_is_on_the_building_closest_to_the_users() -> None:
    row = [building("west", 0, 0, 1), building("middle", 20, 0, 6), building("east", 40, 0, 1)]
    [box] = bp.place(row, [LARGE])
    assert box.host == "middle"
    assert {s.key: s.distance_m for s in box.served} == {"west": 15.0, "middle": 0.0, "east": 15.0}


def test_spare_share_reduces_capacity() -> None:
    boxes = bp.place([building("a", 0, 0, 8)], [SMALL, LARGE], spare_percent=25)
    assert [(b.box_type, b.usable) for b in boxes] == [(LARGE, 12)]  # small holds only 6 after spare


def test_buildings_without_users_get_nothing() -> None:
    assert bp.place([building("empty", 0, 0, 0)], [SMALL]) == []


def test_needs_types_and_usable_capacity() -> None:
    with pytest.raises(bp.PlacementError):
        bp.place([building("a", 0, 0, 1)], [])
    with pytest.raises(bp.PlacementError):
        bp.place([building("a", 0, 0, 1)], [bp.BoxType("one", 1)], spare_percent=50)
