## ADDED Requirements

### Requirement: Extras as composable effects
Weapons, powers and penalties SHALL be implemented as `Effect` classes with hooks (`on_apply`, `on_tick`, `on_expire`) registered in a `Registry`, with data (duration, magnitude, rarity) loaded from config.

#### Scenario: Add new effect
- **WHEN** a new `Effect` is registered and listed in the extras data file
- **THEN** it can spawn in matches without core changes

### Requirement: Pickups
The system SHALL spawn pickups on the table at a configurable frequency, collected when the ball or a projectile of a player touches them, with the owner determined by the last paddle that hit the ball.

#### Scenario: Collect by last hitter
- **WHEN** the ball touches a pickup after being hit by P1
- **THEN** P1 receives the extra

### Requirement: Powers
The system SHALL include beneficial powers for the owner, at least: bigger paddle, speed boost, magnetic paddle (catch and release ball), shield (blocks one goal), multiball, slow-motion for the opponent.

#### Scenario: Shield
- **WHEN** a player with an active shield would concede a goal
- **THEN** the ball bounces back and the shield is consumed

### Requirement: Weapons
The system SHALL include weapons fired by a player action button with limited ammo, at least: laser (damages destructible obstacles and briefly stuns an enemy paddle), freeze shot, and bomb (area push on the ball).

#### Scenario: Ammo
- **WHEN** a weapon has no ammo left
- **THEN** pressing fire has no effect and an "empty" event is emitted

### Requirement: Penalties
The system SHALL include penalties applied to the player who triggers them (or the one losing a point, configurable), at least: shrunken paddle, inverted controls, slowed paddle, blinded view (screen noise).

#### Scenario: Inverted controls
- **WHEN** the inverted-controls penalty is active on a player
- **THEN** their move axis is negated until it expires

### Requirement: Balance and limits
The match configuration SHALL allow enabling/disabling each extra category and individual extras, setting the spawn rate, and capping simultaneous active effects per player.

#### Scenario: Extras off
- **WHEN** extras are disabled in the config
- **THEN** no pickups spawn during the match

### Requirement: Visibility to players
Active effects SHALL be visible in the HUD with remaining duration and in the 3D view (icons, colors).

#### Scenario: HUD
- **WHEN** an effect is active
- **THEN** the HUD shows its icon and a countdown

### Requirement: Score-gap assistance
When extras are enabled and the score gap reaches three points, the system SHALL offer one reduced targeted pickup at most every 15 seconds, alternating between the losing and leading players. It SHALL only spawn when no pickup is on the table.

#### Scenario: Losing player collects assistance
- **WHEN** a player's paddle passes over a targeted catch-up pickup
- **THEN** only that player receives the reduced beneficial effect without the ball touching it

#### Scenario: Catch-up pickups are spaced
- **WHEN** a score-gap pickup is due while another pickup is already present
- **THEN** no extra catch-up pickup appears alongside it

### Requirement: Pickup spacing and reduced effects
The table SHALL hold at most two pickups, spaced at least 24 world units apart. Targeted pickups SHALL expire sooner than ordinary pickups and apply half-duration, reduced-strength effects or one weapon charge.

#### Scenario: Pickup spacing
- **WHEN** a pickup spawns near an existing pickup
- **THEN** it is placed at least 24 world units away or its spawn is skipped

### Requirement: Companion defender
The system SHALL provide a temporary, small AI-controlled companion paddle that resembles its owner's paddle and can collide with the ball to protect the owner's goal.

#### Scenario: Companion intercepts ball
- **WHEN** a ball reaches the companion paddle
- **THEN** it rebounds as if hit by the owner and the companion expires after its configured duration

### Requirement: Headbutt and missile weapons
The system SHALL provide a headbutt weapon that temporarily lunges the paddle toward the table and a two-charge missile weapon that stuns opponents or damages destructible arena obstacles.

#### Scenario: Missile hits obstacle
- **WHEN** a missile touches a destructible obstacle
- **THEN** the obstacle loses one hit point and is destroyed when its hit points reach zero

#### Scenario: Missile hits opponent
- **WHEN** a missile touches an opponent's paddle
- **THEN** that opponent is briefly stunned and the missile is consumed
