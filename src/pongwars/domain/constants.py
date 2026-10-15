"""@package pongwars.domain.constants
@brief Simulation constants (world units; 1 unit = 1 logical pixel).
"""

TICK_RATE = 60
DT = 1.0 / TICK_RATE

FIELD_WIDTH = 160.0
FIELD_HEIGHT = 90.0

PADDLE_HALF_WIDTH = 1.5
PADDLE_HALF_HEIGHT = 8.0
PADDLE_MARGIN = 6.0
PADDLE_SPEED = 90.0

BALL_RADIUS = 2.0
BALL_START_SPEED = 80.0
BALL_MAX_SPEED = 200.0
BALL_MIN_SPEED = 40.0
BALL_HIT_SPEEDUP = 1.04
MAX_BOUNCE_ANGLE = 1.0  # radians, at the paddle edge
MAX_SERVE_ANGLE = 0.5  # radians

SERVE_DELAY_TICKS = 60
DEFAULT_SCORE_LIMIT = 7
MAX_COLLISIONS_PER_STEP = 4
EPSILON = 1e-9

BUMPER_FACTOR = 1.25
ARENA_SIDE_MARGIN = 16.0  # obstacles must stay this far from both goal lines
KING_ZONE_HALF_WIDTH = 12.0
KING_POINT_INTERVAL_TICKS = 30
ARENA_END_MARGIN = 16.0  # keep-out distance from the top/bottom lines in 3-4 player arenas

PICKUP_RADIUS = 3.0
PICKUP_LIFETIME_TICKS = 900
PICKUP_MAX_ON_TABLE = 3
PICKUP_AREA_X = (0.25, 0.75)  # fraction of the field width where pickups may appear
PICKUP_AREA_Y = (15.0, FIELD_HEIGHT - 15.0)
PICKUP_PLACEMENT_TRIES = 12
MAX_BALLS = 4
MULTIBALL_SPREAD = 0.4  # radians between the original ball and each clone
MAGNET_HOLD_TICKS = 45
BOMB_RADIUS = 40.0
BOMB_IMPULSE = 1.3
SHIELD_BALL_CLEARANCE = 1.0
CAT_LIFETIME_TICKS = 300  # 5 seconds
CAT_SPEED = 130.0
CAT_RADIUS = 3.0
CAT_COOLDOWN_TICKS = 40  # pause between two pounces of the same cat
CAT_MIN_SPEED_FACTOR = 0.7  # random ball speed, as a fraction of BALL_START_SPEED ...
CAT_MAX_SPEED_FACTOR = 1.6  # ... up to this fraction
SLOW_BALL_FACTOR = 0.7
TURBO_BALL_FACTOR = 1.25
DRUNK_AMPLITUDE = 0.9
DRUNK_FREQUENCY = 0.12  # radians per tick
WARP_MARGIN = 20.0  # keep warped balls away from the goal lines
EXTRAS_DATA_FILE = "extras.toml"
DEFAULT_EXTRAS_INTERVAL = 10.0
DEFAULT_EXTRAS_MAX_ACTIVE = 3
MAX_EXTRAS_INTERVAL = 120.0
