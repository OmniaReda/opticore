"""Place Network Boxes so every building's users are served (prototype method, not a Design Team rule).

Input is in UTM metres (EPSG:32636): one `Demand` per building (its outline and its number of users).
Method — a greedy, capacity-limited grouping of nearby buildings:

1. A building with more users than the largest box gets as many full largest boxes as it needs, on it;
   its remaining users are grouped with its neighbours like any other building.
2. Start a group with the unserved building farthest from the others (edges first, so no building is
   left alone at the end), then add the nearest unserved building while
   - the group's users still fit in the largest box (after the spare share), and
   - every building of the group stays within `max_drop_m` of the box (when a limit is given).
3. The box goes on the group's building that is closest to the group's users (users-weighted), and
   is the smallest box type that holds the group's users.

Distances are straight lines from the box to the building outline, not along streets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

# How many nearest unserved buildings are tried each time a group grows.
_CANDIDATES = 40


@dataclass(frozen=True)
class BoxType:
    name: str
    capacity: int  # users per box


@dataclass(frozen=True)
class Demand:
    key: str  # identifies the building for the caller
    outline: BaseGeometry  # UTM metres
    users: int


@dataclass(frozen=True)
class Served:
    key: str
    users: int
    distance_m: float  # box → building outline (0 for the building the box is on)


@dataclass
class PlacedBox:
    box_type: BoxType
    usable: int  # capacity minus the spare share
    host: str  # key of the building the box is on
    location: Point  # UTM metres
    served: list[Served] = field(default_factory=list)
    dedicated: bool = False  # one of the full boxes of a building larger than the largest box

    @property
    def users(self) -> int:
        return sum(s.users for s in self.served)


class PlacementError(ValueError):
    pass


def usable_capacity(box_type: BoxType, spare_percent: float) -> int:
    return math.floor(box_type.capacity * (1 - spare_percent / 100))


def place(
    demands: list[Demand], box_types: list[BoxType], max_drop_m: float | None = None, spare_percent: float = 0
) -> list[PlacedBox]:
    if not box_types:
        raise PlacementError("Give at least one box type")
    usable = {t: usable_capacity(t, spare_percent) for t in box_types}
    if min(usable.values()) < 1:
        raise PlacementError("The spare share leaves no usable capacity in a box type")
    # Smallest first: the first type that holds a group is the one used.
    types = sorted(box_types, key=lambda t: (usable[t], t.capacity, t.name))
    largest = types[-1]
    limit = usable[largest]

    boxes: list[PlacedBox] = []
    left: dict[int, int] = {}  # index in `demands` → users still to serve
    for i, d in enumerate(demands):
        if d.users <= 0:
            continue
        full, rest = divmod(d.users, limit)
        if rest == 0 and full > 0:  # keep one box for grouping with neighbours if it is not full
            full, rest = full - 1, limit
        point = d.outline.representative_point()
        for _ in range(full):
            boxes.append(PlacedBox(largest, limit, d.key, point, [Served(d.key, limit, 0.0)], dedicated=True))
        left[i] = rest

    points = [d.outline.representative_point() for d in demands]
    xy = np.array([(p.x, p.y) for p in points]) if points else np.zeros((0, 2))
    unserved = set(left)

    def drop(host: int, member: int) -> float:
        return 0.0 if host == member else float(points[host].distance(demands[member].outline))

    def best_host(members: list[int]) -> tuple[int, float]:
        """The member building closest to the group's users, and its longest drop."""
        best: tuple[float, int, float] | None = None
        for h in members:
            drops = [drop(h, m) for m in members]
            cost = sum(left[m] * dist for m, dist in zip(members, drops, strict=True))
            if best is None or cost < best[0]:
                best = (cost, h, max(drops))
        assert best is not None
        return best[1], best[2]

    while unserved:
        idx = np.fromiter(unserved, dtype=int)
        centre = xy[idx].mean(axis=0)
        seed = int(idx[np.argmax(np.hypot(*(xy[idx] - centre).T))])
        members, users, host = [seed], left[seed], seed
        unserved.discard(seed)
        while unserved and users < limit:
            idx = np.fromiter(unserved, dtype=int)
            near = idx[np.argsort(np.hypot(*(xy[idx] - xy[host]).T))[:_CANDIDATES]]
            added = False
            for c in near.tolist():
                if users + left[c] > limit:
                    continue
                new_host, longest = best_host([*members, c])
                if max_drop_m is not None and longest > max_drop_m:
                    continue
                members.append(c)
                users += left[c]
                host = new_host
                unserved.discard(c)
                added = True
                break
            if not added:
                break
        box_type = next(t for t in types if usable[t] >= users)
        served = [Served(demands[m].key, left[m], round(drop(host, m), 1)) for m in members]
        boxes.append(PlacedBox(box_type, usable[box_type], demands[host].key, points[host], served))
    return boxes
