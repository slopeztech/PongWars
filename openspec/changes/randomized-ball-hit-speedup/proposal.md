# Proposal

## Why

As a rally continues, the ball can become too fast for players to track and return, ending rounds earlier than intended. A smaller, variable speed increase on ordinary paddle hits should keep rallies playable for longer without removing their gradual acceleration.

## What Changes

- Replace the fixed acceleration on ordinary paddle hits with a random increase between 1% and 4% per hit.
- Preserve deterministic simulation by deriving each increase from the match's seeded random source.
- Leave the existing speed cap and the special speed boosts for spin and headbutt hits unchanged.

## Capabilities

### New Capabilities

- `ball-physics`: Define how ordinary paddle hits increase ball speed while preserving deterministic simulation and the maximum speed limit.

### Modified Capabilities

None.

## Impact

- Affects ball bounce behavior in the domain simulation and its unit tests.
- No configuration, network protocol, dependency, or user-interface changes.

## Out of Scope

- Changing the maximum ball speed, paddle speed, or spin and headbutt boosts.
- Adding a gameplay setting or changing acceleration from other sources.
