"""@package pongwars
@brief PongWars: 8-bit pseudo-3D Pong with configurable matches, extras, AI and LAN play.

Layering (imports only flow in this direction):
`app -> ui / render / input / audio / net -> domain <- ai`.
"""

from pongwars.version import __version__ as __version__
