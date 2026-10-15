## 1. Phase 0 - Structure and tooling

- [x] 1.1 Initialize OpenSpec (config, context, rules)
- [x] 1.2 Capability specs and architecture design
- [x] 1.3 `pyproject.toml`, dependencies, ruff/mypy/pytest configured
- [x] 1.4 Package skeleton `src/pongwars/**` with Doxygen docstrings
- [x] 1.5 `docs/Doxyfile` and `scripts/docs.ps1` (0 warnings)
- [x] 1.6 `scripts/check.ps1` (lint + types + tests + coverage)
- [x] 1.7 Architecture test: layer dependency rules and pygame-free `domain`
- [x] 1.8 README and OpenSpec + AI workflow guide
- [x] 1.9 Translate all artifacts to English; add `localization` spec

## 2. Phase 1 - Domain core (`game-core`, `match-configuration`, `localization`)

- [x] 2.1 `core.Registry` generic + tests
- [x] 2.2 `core.i18n` Translator + `data/locales/en.json` + consistency test
- [x] 2.3 `domain.rng` (seeded RandomSource) + tests
- [x] 2.4 `domain.vec` 2D vector, `domain.constants` + tests
- [x] 2.5 `MatchConfig`: dataclass, JSON round trip, validation (key-based errors), version + tests
- [x] 2.6 Entities: Paddle, Ball, Wall + tests
- [x] 2.7 Physics: integration, swept collision (anti-tunneling), bounces, contact-point angle + tests
- [x] 2.8 `World.step(FrameInputs)`, scoring, serve, typed events + tests
- [x] 2.9 Determinism test (same seed + inputs => same state)

## 3. Phase 2 - Modes and arenas (`game-modes`, `arenas`)

- [x] 3.1 `Mode` interface + registry + Classic mode
- [x] 3.2 Timed, Survival, King of the Table modes
- [x] 3.3 TOML/JSON arena loader + validation
- [x] 3.4 Obstacles: solid, bumper, moving, destructible
- [x] 3.5 Built-in arenas (Classic, Pillars, Bumpers, Moving Walls, Fortress) + symmetry test
- [x] 3.6 2/3/4-player arenas (seats, walls, elimination, last-toucher scoring, Trident and Crossfire arenas)

## 4. Phase 3 - 8-bit pseudo-3D rendering and local input (`rendering`, `input`)

- [x] 4.1 Main loop with fixed step and accumulator
- [x] 4.2 Perspective camera/projection + math tests
- [x] 4.3 Palette, low-res surface, nearest scaling, bitmap font
- [x] 4.4 Draw table, paddles, ball, obstacles, shadows, depth ordering
- [x] 4.5 Particles, trail, screen shake (configurable)
- [x] 4.6 `PlayerInput`, 2-player keyboard, remapping, gamepad
- [x] 4.7 Render benchmark (< 16 ms/frame)

## 5. Phase 4 - AI (`ai-opponent`)

- [x] 5.1 `Observation` and `AIController`
- [x] 5.2 Trajectory prediction with bounces
- [x] 5.3 Easy/Normal/Hard/Insane difficulties via parameters
- [x] 5.4 Difficulty monotonicity and determinism tests

## 6. Phase 5 - Extras (`extras`)

- [x] 6.1 `Effect` base + registry + data
- [x] 6.2 Pickups and configurable spawner
- [x] 6.3 Powers (big paddle, speed, magnet, shield, multiball, slow-mo)
- [x] 6.4 Weapons (laser, freeze, bomb) and ammo
- [x] 6.5 Penalties (small paddle, inverted controls, slowness, blindness)
- [x] 6.6 Active effects HUD

## 7. Phase 6 - UI, audio and language (`ui-menus`, `audio`, `localization`)

- [x] 7.1 Screen stack and widgets (all text via Translator)
- [x] 7.2 Main menu, auto-generated match setup, pause, results
- [x] 7.3 Persistent settings incl. language selector
- [x] 7.4 Chiptune synthesizer and event-to-sound mapping
- [x] 7.5 Bitmap font charset per language

## 8. Phase 7 - LAN (`lan-multiplayer`)

- [ ] 8.1 `Transport`/`Codec` interfaces and in-memory transport
- [ ] 8.2 Versioned protocol, snapshots and inputs
- [ ] 8.3 Authoritative host and interpolating client
- [ ] 8.4 Real UDP transport and broadcast discovery
- [ ] 8.5 Simulated packet loss, timeouts and disconnection
- [ ] 8.6 Full host<->client integration test

## 9. Phase 8 - Wrap-up

- [x] 9.1 Coverage >= 90% on domain/ai/net
- [x] 9.2 Doxygen with zero warnings
- [x] 9.3 Packaging and user guide
- [ ] 9.4 Archive change (`/opsx-archive`)

