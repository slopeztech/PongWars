## ADDED Requirements

### Requirement: Pseudo-3D perspective view
The system SHALL render the table with a perspective camera (tilted plane, vanishing point), giving height to paddles, ball, walls and obstacles, with drop shadows, using software projection on pygame surfaces.

#### Scenario: Depth ordering
- **WHEN** two objects overlap on screen
- **THEN** the one nearer to the camera is drawn in front

### Requirement: 8-bit look
The system SHALL render to a low-resolution internal surface (default 320x180), restrict colors to a defined palette (<= 32 colors) and upscale with nearest-neighbor, using a bitmap font.

#### Scenario: Palette limit
- **WHEN** a frame is rendered
- **THEN** every pixel color belongs to the palette

### Requirement: Render is read-only
Rendering SHALL only read world state and events; it MUST NOT mutate the simulation.

#### Scenario: Headless render
- **WHEN** the renderer runs with the SDL dummy video driver
- **THEN** it produces a frame without errors, enabling tests in CI

### Requirement: Performance
The game SHALL sustain 60 FPS at the default resolution on a mid-range laptop without a dedicated GPU.

#### Scenario: Benchmark
- **WHEN** the render benchmark runs 600 frames of a busy scene
- **THEN** the average frame time is below 16 ms

### Requirement: Visual feedback
The system SHALL provide screen shake, hit flashes, ball trail and particles for hits, goals and extras, each toggleable in settings.

#### Scenario: Disable effects
- **WHEN** the user disables screen shake
- **THEN** goals do not shake the camera

## ADDED Requirements

### Requirement: Multi-seat support
The rendering layer SHALL support 2 to 4 seats, including horizontal paddles for the top and bottom seats.

#### Scenario: Four seats
- **WHEN** a 4-player arena is active
- **THEN** all four seats are drawn or polled independently

### Requirement: Shared or split camera
The renderer SHALL support a shared camera and a split-screen mode (one viewport per seat, each oriented so the seat's own goal is at the bottom), selectable per match.

#### Scenario: Split view
- **WHEN** the view is "split" in a 3 or 4 player match
- **THEN** each seat gets its own viewport with a rotated camera

### Requirement: Translated HUD
All HUD text SHALL be resolved through the translator.

#### Scenario: Locale keys
- **WHEN** the HUD is drawn
- **THEN** every label is obtained from a `hud.*` locale key

### Requirement: Player-specific HUD extras
Pickups, active effects and weapons SHALL use their complete localized names without clipping. Active effects and weapons SHALL be displayed below the score of the player they affect in shared and split views.

#### Scenario: Shared view extras
- **WHEN** a player has an active effect or weapon in shared view
- **THEN** that extra is drawn below that player's score, not in a global list

#### Scenario: Complete localized extra names
- **WHEN** an extra pickup, effect or weapon is displayed
- **THEN** its complete translated name is visible, along with remaining duration or ammunition where applicable

### Requirement: Countdown placement
The match countdown SHALL be displayed below the projected arena.

#### Scenario: Countdown outside the arena
- **WHEN** a countdown number is shown
- **THEN** it is positioned below the arena boundary and remains visible in the viewport
