"""@package pongwars.net.snapshot
@brief Capture, apply and interpolate world state; (de)serialise simulation events.
"""

import math
from dataclasses import fields
from typing import Any

from pongwars.domain import events as ev
from pongwars.domain.entities import Ball, Cat
from pongwars.domain.extras import EFFECTS, Pickup
from pongwars.domain.vec import Vec2
from pongwars.domain.world import Phase, World
from pongwars.net.protocol import ProtocolError

DECIMALS = 3
TELEPORT_DISTANCE = 30.0
EVENT_TYPES: dict[str, type[ev.Event]] = {
    name: cls
    for name, cls in vars(ev).items()
    if isinstance(cls, type) and issubclass(cls, ev.Event) and cls is not ev.Event
}


def _r(value: float) -> float:
    return round(float(value), DECIMALS)


def capture(world: World) -> dict[str, Any]:
    """@brief Serialise everything a client needs to draw the world.
    @param world Authoritative world.
    @return A JSON-friendly dict.
    """
    return {
        "tick": world.tick,
        "phase": world.phase.value,
        "winner": world.winner,
        "scores": list(world.scores),
        "alive": [bool(a) for a in world.alive],
        "balls": [
            [_r(b.pos.x), _r(b.pos.y), _r(b.vel.x), _r(b.vel.y), b.toucher, b.held_by]
            for b in world.balls
        ],
        "paddles": [
            [_r(p.rect.cx), _r(p.rect.cy), _r(p.rect.half_w), _r(p.rect.half_h)]
            for p in world.paddles
        ],
        "obs": [[_r(o.rect.cx), _r(o.rect.cy), o.hp, int(o.active)] for o in world.obstacles],
        "pick": [[_r(p.pos.x), _r(p.pos.y), p.name, p.ttl] for p in world.extras.pickups],
        "cats": [[_r(k.pos.x), _r(k.pos.y), k.owner, k.ttl, k.cooldown] for k in world.extras.cats],
        "fx": [[[e.name, e.remaining] for e in seat] for seat in world.extras.active],
        "wpn": [list(w) if w else None for w in world.extras.weapons],
    }


def apply(world: World, state: dict[str, Any]) -> None:
    """@brief Overwrite a mirror world with a captured state.
    @param world Mirror world built from the same configuration.
    @param state Output of capture().
    @throws ProtocolError If the state is malformed or does not fit the world.
    """
    try:
        _apply(world, state)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ProtocolError("bad snapshot") from exc


def _apply(world: World, state: dict[str, Any]) -> None:
    n = world.players
    paddles, obstacles = state["paddles"], state["obs"]
    if len(paddles) != n or len(obstacles) != len(world.obstacles):
        raise ValueError("snapshot does not match the world")
    if not (len(state["scores"]) == len(state["alive"]) == len(state["fx"]) == n):
        raise ValueError("snapshot does not match the world")
    balls = state["balls"]
    if not balls:
        raise ValueError("no ball")
    world.tick = int(state["tick"])
    world.phase = Phase(state["phase"])
    world.winner = state["winner"]
    world.scores = [int(s) for s in state["scores"]]
    world.alive = [bool(a) for a in state["alive"]]
    made = [_ball(row, world.ball.radius) for row in balls]
    world.ball = made[0]
    world.extra_balls = made[1:]
    for paddle, row in zip(world.paddles, paddles, strict=True):
        paddle.rect.cx, paddle.rect.cy, paddle.rect.half_w, paddle.rect.half_h = map(float, row)
    for obstacle, row in zip(world.obstacles, obstacles, strict=True):
        obstacle.rect.cx, obstacle.rect.cy = float(row[0]), float(row[1])
        obstacle.hp, obstacle.active = int(row[2]), bool(row[3])
    manager = world.extras
    manager.pickups = [
        Pickup(Vec2(float(x), float(y)), str(name), int(ttl)) for x, y, name, ttl in state["pick"]
    ]
    manager.cats = [
        Cat(Vec2(float(x), float(y)), int(owner), int(ttl), int(cd))
        for x, y, owner, ttl, cd in state["cats"]
    ]
    for pickup in manager.pickups:
        if pickup.name not in manager.specs:
            raise ValueError("unknown pickup")
    manager.active = [[_effect(world, name, left) for name, left in seat] for seat in state["fx"]]
    weapons = state["wpn"]
    if len(weapons) != n:
        raise ValueError("snapshot does not match the world")
    manager.weapons = [(str(w[0]), int(w[1])) if w else None for w in weapons]


def _ball(row: list[Any], radius: float) -> Ball:
    x, y, vx, vy, toucher, held = row
    return Ball(
        Vec2(float(x), float(y)),
        Vec2(float(vx), float(vy)),
        radius,
        toucher=None if toucher is None else int(toucher),
        held_by=None if held is None else int(held),
    )


def _effect(world: World, name: str, remaining: int) -> Any:
    spec = world.extras.specs[str(name)]
    effect = EFFECTS.get(str(name))(spec)
    effect.remaining = int(remaining)
    return effect


def _lerp(a: float, b: float, alpha: float) -> float:
    return a + (b - a) * alpha


def blend(a: dict[str, Any], b: dict[str, Any], alpha: float) -> dict[str, Any]:
    """@brief Interpolate positions between two snapshots; everything else comes from `b`.
    @param a Older state.
    @param b Newer state.
    @param alpha 0 gives `a`, 1 gives `b` (clamped).
    @return A new state; `b` itself when the two are not comparable.
    """
    alpha = max(0.0, min(1.0, alpha))
    out = dict(b)
    try:
        if len(a["balls"]) == len(b["balls"]):
            out["balls"] = [
                _blend_ball(p, q, alpha) for p, q in zip(a["balls"], b["balls"], strict=False)
            ]
        if len(a["paddles"]) == len(b["paddles"]):
            out["paddles"] = [
                [_lerp(p[0], q[0], alpha), _lerp(p[1], q[1], alpha), q[2], q[3]]
                for p, q in zip(a["paddles"], b["paddles"], strict=False)
            ]
        if len(a["cats"]) == len(b["cats"]):
            out["cats"] = [
                [_lerp(p[0], q[0], alpha), _lerp(p[1], q[1], alpha), *q[2:]]
                for p, q in zip(a["cats"], b["cats"], strict=False)
            ]
        if len(a["obs"]) == len(b["obs"]):
            out["obs"] = [
                [_lerp(p[0], q[0], alpha), _lerp(p[1], q[1], alpha), *q[2:]]
                for p, q in zip(a["obs"], b["obs"], strict=False)
            ]
    except (KeyError, IndexError, TypeError):
        return b
    return out


def _blend_ball(p: list[Any], q: list[Any], alpha: float) -> list[Any]:
    if math.hypot(q[0] - p[0], q[1] - p[1]) > TELEPORT_DISTANCE:
        return list(q)
    return [_lerp(p[0], q[0], alpha), _lerp(p[1], q[1], alpha), *q[2:]]


def events_to_list(events: list[ev.Event]) -> list[Any]:
    """@brief Serialise events.
    @param events Simulation events.
    @return A list of [type name, field values...] entries.
    """
    return [[type(e).__name__, *(getattr(e, f.name) for f in fields(e))] for e in events]


def events_from_list(data: list[Any]) -> list[ev.Event]:
    """@brief Rebuild events; unknown or malformed entries are skipped.
    @param data Output of events_to_list().
    @return The events.
    """
    result: list[ev.Event] = []
    for entry in data:
        try:
            cls = EVENT_TYPES[entry[0]]
            result.append(cls(*entry[1:]))
        except (KeyError, IndexError, TypeError):
            continue
    return result
