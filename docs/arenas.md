# Arenas

The arena sets the table layout, obstacles, serve position and player count.
Choose an arena in match setup; its required number of player seats is selected
automatically. All arenas use the same 160-by-90 logical table.

There are thirteen built-in arenas. **Trident** is for three players and
**Crossfire** is for four; the other eleven are for two players.

## Two-player arenas

### Classic

An open table with no obstacles. Choose it for the most direct rallies.

### Pillars

Four solid pillars form a mirrored pattern across the middle lanes. They block
shots and divide the court into narrower routes; the ball reflects from them.

### Bumpers

One bumper sits at the center and four more form a mirrored outer pattern.
Bumpers reflect the ball and increase its speed on contact, so a ricochet can
send it back into play with extra force.

### Moving Walls

Two solid walls move up and down on mirrored paths. Their motion repeats every
six seconds, continually changing the gaps available for a shot.

### Fortress

Four destructible wall segments sit in mirrored pairs near the goal areas. Each
segment takes three hits to break. The remaining segments stay out of the way for
the rest of the point; the layout is rebuilt after a goal.

### Monolith

A large solid block stands in the center of the table. Each time the ball hits
it, the block switches between a tall, narrow orientation and a wide, low one,
changing which routes are open.

### Orbital

Two bumpers travel around mirrored oval paths. They complete a cycle every six
seconds and can redirect the ball as they move.

### Pinball

Four bumpers are arranged in a mirrored pinball-style layout. Their rebounds
change the ball's direction and increase its speed.

### Portal

Two portals appear at random clear positions. Entering one moves the ball to the
other while preserving its direction and speed. After each crossing, both
portals relocate, so the next route is unpredictable. Portals do not place the
ball on top of the serve point or an obstacle.

### Arkanoid

A random cluster of 2-16 destructible blocks appears near the center of the
table. Every ball hit breaks a block; lasers and missiles can clear blocks as
well. A new cluster is generated after each goal.

### Gravity

The ball is attracted toward a well in the center of the table. The attraction
gets stronger as the ball approaches, bending its trajectory. The ball serves
near the top edge at a higher-than-usual speed.

## Multiplayer arenas

### Trident (three players)

Three paddles defend three sides of the table. A pair of solid blocks creates
additional interior deflections while leaving a path through the arena.

### Crossfire (four players)

Four paddles defend the left, right, top, and bottom sides. Four solid blocks
form a mirrored pattern across the table, making the ball's routes cross.

In arenas with more than two players, a goal is credited to the last player who
touched the ball, unless that player conceded it. Game modes determine whether
the conceded player loses a life, is eliminated, or how the point affects the
match.

## Obstacle behavior

- **Solid** obstacles reflect the ball without changing its speed.
- **Bumpers** reflect the ball and increase its speed by 25%, up to the
  maximum-speed limit.
- **Destructible** obstacles lose one hit point per ball impact. Weapons such as
  lasers and missiles can also damage or remove them.
- Moving and orbital obstacles follow repeating paths, changing the routes
  available during a point.

Arena files are stored in
[`src/pongwars/data/arenas/`](../src/pongwars/data/arenas/). See
[Development and contribution](development.md) for the documentation convention
that applies when adding or changing an arena.

For scoring rules, see [Game modes](game-modes.md). For powers, weapons, and
penalties, see [Extras](extras.md).
