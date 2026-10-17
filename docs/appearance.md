# Appearance guide

PongWars lets you customize paddle colors and patterns, the ball, its trail, the
arena floor, and the background. Open **Appearance** from the main menu. Choices
are previewed immediately and saved automatically to
`%APPDATA%\PongWars\settings.json` on Windows or `~/.config/PongWars/settings.json`
on Linux.

The **HUD style** row selects the match overlay. The existing **Arcade**,
**Minimal**, and **Neon** styles remain available; **Arcade cabinet** adds
cabinet-like frames, **Scoreboard** uses a classic illuminated display, and
**Pixel arcade** adds pixel-trimmed panels. All styles work in shared and
split-screen matches. Each player panel shows the score and the icon and name
of active extras (with remaining time or weapon count where applicable). The
active-extra names are fitted to their player panels and use separate rows so
one or two effects remain legible in shared and split-screen views. Names of
pickups on the board appear in cards anchored to the bottom edge with a small
margin; their muted text is smaller than the active-extra labels, and cards
move to separate rows when needed to avoid overlapping.

The preview focuses on the selected option: paddle patterns, the ball, and its
trail are enlarged so their details are visible. The selected player's paddle
uses the same standard angle and scale for all four player slots. Field styles
use an individual icon for each of the 20 designs, so the pattern is clear even
in the small preview panel and does not depend on the arena camera. All four
player slots have a paddle in the sample scene, even when a regular match uses
fewer players.

Animated backgrounds include a subtle full-screen color gradient beneath their
distinctive effects. The `None` and `Grid` choices remain plain.

In the four player rows, **Left/Right** changes that player's paddle color and
**Enter** advances their paddle pattern. Use **Left/Right** to cycle the other
appearance choices. Paddle cosmetics are also sent to other players in a LAN
lobby.

## Paddle colors (24)

The original colors remain first in the list, so existing saved settings keep
their appearance:

Blue, Red, Lime, Yellow, Orange, Pink, White, Lavender, Cyan, Teal, Mint, Forest,
Sky, Royal blue, Indigo, Violet, Magenta, Coral, Crimson, Burgundy, Gold, Sand,
Silver, Charcoal.

## Paddle patterns (20)

Classic, Striped, Glow, Capped, Studded, Checker, Chevron, Twin bars, Hatch,
Diamond, Triangle, Wave, Crossbar, Split, Slash, Zigzag, Ringed, Dashes, Lattice,
Pulse.

## Ball designs (20)

Classic, Pixel, Energy, Ring, Star, Crystal, Sun, Target, Moon, Flower, Dice, Eye,
Atom, Gear, Prism, Comet, Bubble, Spiral, Cross, Heart.

## Ball trails (19)

Classic, Pixel, Neon, Comet, Dotted, Rainbow, Flame, Frost, Sparks, Squares,
Rings, Double, Dash, Ripple, Stardust, Ribbon, Glitch, Orbit, Fade.

The **Trail** setting in Gameplay must be enabled for a ball trail to appear.

## Arena fields (20)

Grid, Checkerboard, Neon, Solid, Dots, Diagonal, Crosshatch, Rings, Target,
Stripes, Waves, Diamonds, Circuit, Boxes, Radial, Stars, Lanes, Scanlines, Maze,
Sparkle.

## Backgrounds (22 choices)

None, Grid, Stars, Rain, Waves, Aurora, Nebula, Comets, Bubbles, Snowfall,
Fireflies, Matrix, Circuit, Embers, Meteor shower, Spiral, Confetti, Starscape,
Plasma, Rainbow, Gears, Pulse.

Background effects are decorative and do not change gameplay. **None** and
**Grid** use the plain background; the other choices animate behind the arena.
