# Design

## Context

See [proposal.md](./proposal.md) for motivation and [specs/ball-physics/spec.md](./specs/ball-physics/spec.md) for the behavior contract. `World` owns a seeded `RandomSource`, and `_paddle_bounce` currently selects a fixed multiplier for ordinary hits while spin and headbutt select separate special multipliers. Paddle-hit speed is already capped at `BALL_MAX_SPEED`.

## Goals / Non-Goals

**Goals:**
- Make ordinary paddle-hit acceleration vary uniformly from 1% through 4%.
- Keep identical seeded simulations reproducible.
- Preserve the existing speed cap and special-hit multipliers.

**Non-Goals:**
- Change acceleration from bumpers, gravity, extras, or any other source.
- Add match settings or alter existing speed constants unrelated to ordinary paddle hits.

## Decisions

- Use the existing `World.rng.uniform` source for the ordinary-hit multiplier. This follows the simulation's single seeded randomness pattern and avoids introducing another random stream or configuration. A dedicated stream was considered but rejected because isolating this one draw would add machinery without improving reproducibility for a given seed and input sequence.
- Represent the 1% and 4% bounds as named domain constants, then draw a multiplier in that range only for ordinary hits. Keep the existing special-hit selection and final `BALL_MAX_SPEED` clamp unchanged.
- Test the bounds and special-hit behavior directly, and compare identical seeded worlds receiving the same inputs to verify deterministic outcomes.

## Risks / Trade-offs

- **Ordinary hits consume draws from the shared random sequence, shifting later random outcomes relative to older versions** → This is an intentional consequence of introducing seeded per-hit variation; repeated simulations on the same version, seed, and input sequence remain deterministic.

## Migration Plan

No data migration or rollout step is required. The change applies to new and ongoing matches when the updated simulation runs.
