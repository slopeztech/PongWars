# Extras

Extras add temporary powers, usable weapons, and penalties to a match. In match
setup, choose **Off**, **All**, **Powers**, **Weapons**, or **Penalties**. Pickups
spawn on the court and are collected by a ball. The player credited with that
ball's most recent paddle hit receives the pickup.

By default, a pickup appears about every ten seconds, stays on the table for up
to fifteen seconds, and no more than two pickups are present at once. Pickup
selection is weighted, so an effect's configured weight controls how often it
appears relative to other enabled effects. By default, each player can have up
to three timed effects active at once; when a new effect exceeds that limit, the
oldest timed effect expires.

## Powers

Powers help the player who collects them, unless noted otherwise.

| Power | Duration | What it does |
|-------|----------|--------------|
| **Big paddle** | 10 seconds | Makes your paddle 1.5 times its normal length. |
| **Speed boost** | 8 seconds | Makes your paddle move 1.5 times faster. |
| **Magnet** | 12 seconds | Lets your paddle catch the ball on contact. Press your fire key (D by default) to release it, or it releases automatically after three seconds. |
| **Shield** | 20 seconds | Absorbs the next goal that would be scored against you and bounces the ball back into play. |
| **Multiball** | Instant | Randomly sets the match to between two and four balls with diverging trajectories, subject to the four-ball limit. |
| **Slow motion** | 6 seconds | Slows opponents' paddles to 60% of their normal movement speed. |
| **Aim assist** | 10 seconds | Aims your paddle returns toward the next opponent while the power lasts. |
| **Cleanse** | Instant | Removes your active penalties and status effects. It does not remove powers or weapons. |
| **Slow ball** | Instant | Slows every free ball to 70% speed, subject to the game's minimum-speed limit. |
| **Companion** | 8 seconds | Adds a small temporary AI paddle near your goal to help defend it. |
| **Hungry orb** | Instant | Appears immediately and roams the table for two to three seconds, then pursues a ball. When it catches one, it slows it by 10%, swallows it briefly, and releases it at a random clear position on an angled path toward the nearest wall or obstacle, never toward a goal. |

## Weapons

Collect a weapon to store its ammunition, then press your **Use weapon** key to
fire. A weapon pickup adds the listed number of shots; collecting the same
weapon again adds its ammunition to your current supply.

| Weapon | Shots | What it does |
|--------|-------|--------------|
| **Laser** | 3 | Fires along a straight line through the court. The first obstacle blocks it; a destructible block takes damage, or the first opponent in the path is stunned. |
| **Freeze** | 2 | Stops the next living opponent's paddle from moving for two seconds. |
| **Bomb** | 2 | Blasts nearby balls away from your paddle. Caught balls are released by the blast. |
| **Cat** | 2 | Releases a cat that chases the nearest ball for five seconds. On contact it changes the ball's direction and speed; it can pounce again after a short cooldown. |
| **Hex** | 1 | Gives the next living opponent a random lasting penalty. |
| **Warp** | 2 | Moves every free ball to a random position away from the outer goal lines without changing its velocity. |
| **Headbutt** | 1 | Lunges your paddle forward for 0.3 seconds, extending its reach. A hit during the lunge sends the ball back with a powerful special boost. |
| **Build** | 2 | Builds up to two defensive blocks in front of your paddle. Each block breaks on the first ball or weapon contact. |
| **Missile** | 2 | Fires one guided missile toward the nearest living opponent per shot. A hit stuns that paddle; a destructible obstacle can be destroyed. |

If you have no ammunition, or a weapon-jam penalty is active, firing has no
effect.

## Penalties

Penalties make play harder for the affected player. By default, a collected
penalty affects its collector.

| Penalty | Duration | What it does |
|---------|----------|--------------|
| **Small paddle** | 8 seconds | Shrinks your paddle to 60% of its normal length. |
| **Inverted controls** | 6 seconds | Reverses your up/down or left/right movement input. |
| **Slow paddle** | 6 seconds | Reduces your paddle's movement speed to 60%. |
| **Blind** | 6 seconds | Obscures your view of the court; the simulation continues normally. |
| **Ramp** | 8 seconds | Tilts the court so gravity accelerates the ball downhill and slows it uphill. This penalty only appears in two-player arenas. |
| **Invader** | 8 seconds | Sends a slow-moving invader across the court. It launches up to five slow bombs toward the affected player's paddle. |
| **Turbo ball** | Instant | Speeds every free ball up by 25%, subject to the maximum-speed limit. |
| **Dizzy controls** | 7 seconds | Adds a wobble to your paddle movement, even while you are not pressing a direction. |
| **Weapon jam** | 8 seconds | Prevents you from firing your weapon while the penalty lasts. |
| **Stalker** | 7 seconds | Sends a slow pixel creature from the other half of the court after your paddle. It explodes on contact and stuns you. |
| **Abyssal leviathan** | 5 seconds | A giant tentacled creature rises behind the arena, lifts the table, and briefly turns the camera underneath it. |

The **Cleanse** power can remove active penalties and status effects.

These three extras use original characters, pixel art, and synthesized sound
effects.

## Comeback pickups

When extras are enabled and the score gap is at least two points, a special
pickup may appear every fifteen seconds if the table is clear. The pickup is
placed along a paddle's path and must be collected by moving that paddle over
it, rather than by hitting it with the ball. Comeback pickups alternate between
a reduced power or weapon for the trailing player and a reduced penalty for the
leading player.

## Status effects

**Stun** and **Frozen** are not collectible extras. They are short status
effects applied when a weapon hits a paddle: lasers and missiles cause a
1.5-second stun, while Freeze stops a paddle for two seconds. The **Cleanse**
power also removes these effects.

For arena layouts and collisions, see [Arenas](arenas.md). For scoring, see
[Game modes](game-modes.md).
