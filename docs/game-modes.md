# Game modes

Choose a mode before starting a match. Each mode changes how points are awarded
and when the match ends; the arena and number of players are selected separately.
All modes work with the two-, three-, and four-player arenas.

## Classic

Score by sending the ball through an opponent's goal. The opponent who concedes a
goal gives a point to the scorer. The first player to reach **Points to win**
(default: 7; range: 1-50) wins.

Enable **Win by two** to require a lead of at least two points. Reaching the target
alone is not enough while an opponent is within one point.

## Timed

Play for a fixed duration (default: 120 seconds; range: 10-600). Goals count as
points, and the player with the unique highest score when time expires wins.

If the top score is tied when the clock runs out, the match continues in sudden
death. Scoring resumes normally; play ends once a player has a unique lead.

## Survival

Every goal against a player costs that player one life (default: 3; range: 1-20).
The scorer earns a point, if there is one. When a player's lives reach zero, that
player is eliminated. In arenas with three or four players, their goal becomes a
wall, so the ball bounces back instead of leaving the table. The last player
remaining wins.

## King of the Table

Goals do not award points. Instead, the last player to touch the main ball earns
one point for every quarter-second (15 simulation ticks) the ball remains in the
central zone. Leaving the zone or another player touching the ball resets the
current hold. Reach **Points to win** (default: 10; range: 1-100) to win.

## Match setup options

Mode-specific options appear below the general match setup choices:

| Mode | Option | Default | Range |
|------|--------|---------|-------|
| Classic | Points to win | 7 | 1-50 |
| Classic | Win by two | Off | On / Off |
| Timed | Duration (seconds) | 120 | 10-600 |
| Survival | Lives | 3 | 1-20 |
| King of the Table | Points to win | 10 | 1-100 |

The configured arena determines the number and positions of players. In a
three- or four-player match, a point from a goal is credited to the last player
who touched the ball, unless that player was the one who conceded it.

For arena layouts and player counts, see [Arenas](arenas.md). To add pickups,
weapons, and other match effects, see [Extras](extras.md).
