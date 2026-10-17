"""Frame model for ARC-AGI-3.

Pure-stdlib representation of the official FrameData shape (see arcprize/ARC-AGI-3-Agents
agents/agent.py: FrameData has game_id, frame (list-of-lists grid), state,
levels_completed, win_levels, guid, full_reset, available_actions).

Working on plain dicts keeps the agent core testable offline (no arcengine import);
a thin adapter converts to/from the real SDK on Kaggle (see agent.py docstring).
"""

from __future__ import annotations


def make_frame(grid, state="PLAYING", levels_completed=0, win_levels=None,
               available_actions=None, game_id="synthetic", guid="", full_reset=False):
    """Build a frame dict in the official FrameData shape."""
    return {
        "game_id": game_id,
        "frame": [list(row) for row in grid],
        "state": state,
        "levels_completed": levels_completed,
        "win_levels": win_levels or [],
        "guid": guid,
        "full_reset": full_reset,
        "available_actions": available_actions if available_actions is not None else [0, 1, 2, 3, 4, 5, 6],
    }


def frame_signature(frame):
    """Stable hash of a frame's grid + state, for loop detection."""
    grid = frame.get("frame") or []
    rows = []
    for row in grid:
        rows.append("".join(str(int(v)) for v in row))
    state = str(frame.get("state", ""))
    levels = int(frame.get("levels_completed", 0) or 0)
    return hash((tuple(rows), state, levels))


def grid_cells(frame):
    """Yield (r, c, value) for every cell."""
    grid = frame.get("frame") or []
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            yield r, c, v


def non_background_cells(frame, background=0):
    return [(r, c, v) for r, c, v in grid_cells(frame) if v != background]


def grid_shape(frame):
    grid = frame.get("frame") or []
    if not grid:
        return (0, 0)
    return (len(grid), len(grid[0]))


def grids_equal(a, b):
    ga, gb = a.get("frame") or [], b.get("frame") or []
    if len(ga) != len(gb):
        return False
    for ra, rb in zip(ga, gb):
        if list(ra) != list(rb):
            return False
    return True


def grid_diff(a, b):
    """Cells that changed between frame a and b: list of (r, c, old, new)."""
    ga, gb = a.get("frame") or [], b.get("frame") or []
    out = []
    if not ga or not gb or len(ga) != len(gb):
        return out
    for r, (ra, rb) in enumerate(zip(ga, gb)):
        if len(ra) != len(rb):
            continue
        for c, (va, vb) in enumerate(zip(ra, rb)):
            if va != vb:
                out.append((r, c, va, vb))
    return out


def summarize_diff(diff):
    """Compact signature of a diff: (n_changed, sorted value pairs, centroid delta)."""
    if not diff:
        return (0, (), None)
    pairs = tuple(sorted(set((old, new) for _, _, old, new in diff)))
    rs = [r for r, _, _, _ in diff]
    cs = [c for _, c, _, _ in diff]
    centroid = (sum(rs) / len(rs), sum(cs) / len(cs))
    return (len(diff), pairs, centroid)
