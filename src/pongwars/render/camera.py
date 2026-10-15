"""@package pongwars.render.camera
@brief Pure-math perspective camera projecting table coordinates to the low-res screen.
"""

import math
from dataclasses import dataclass

from pongwars.domain import constants as c

DEFAULT_BACK = 85.0
DEFAULT_HEIGHT = 95.0
DEFAULT_FOCAL = 170.0
QUARTER_TURNS = 4


@dataclass(frozen=True)
class Projection:
    """@brief Result of projecting a point: screen position and apparent scale."""

    sx: float
    sy: float
    scale: float


class Camera:
    """@brief Pitched pinhole camera looking at the table centre.

    Table coordinates are `x` (0..FIELD_WIDTH), `y` (0..FIELD_HEIGHT, far to near) and `z`
    (height above the table). The camera sits in front of the near edge, above the table.
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        back: float = DEFAULT_BACK,
        height: float = DEFAULT_HEIGHT,
        focal: float = DEFAULT_FOCAL,
        quarter_turns: int = 0,
    ) -> None:
        """@brief Create a camera.
        @param screen_w Target surface width in pixels.
        @param screen_h Target surface height in pixels.
        @param back Distance of the camera behind the table centre along the depth axis.
        @param height Camera height above the table.
        @param focal Focal length in pixels.
        @param quarter_turns Rotation of the table about its centre, in 90-degree steps.
        """
        self.cx = screen_w / 2
        self.cy = screen_h / 2
        self.focal = focal
        self._pitch = math.atan2(height, back)
        self._cam = (0.0, back, height)
        self._turns = quarter_turns % QUARTER_TURNS

    def project(self, x: float, y: float, z: float = 0.0) -> Projection:
        """@brief Project a table-space point.
        @param x Table x.
        @param y Table y.
        @param z Height above the table.
        @return Screen position and perspective scale (pixels per table unit).
        """
        px, py = self.rotate(x - c.FIELD_WIDTH / 2, y - c.FIELD_HEIGHT / 2)
        px -= self._cam[0]
        py -= self._cam[1]
        pz = z - self._cam[2]
        sin_p, cos_p = math.sin(self._pitch), math.cos(self._pitch)
        depth = -py * cos_p - pz * sin_p
        up = -py * sin_p + pz * cos_p
        scale = self.focal / depth
        return Projection(self.cx + px * scale, self.cy - up * scale, scale)

    def rotate(self, dx: float, dy: float) -> tuple[float, float]:
        """@brief Apply the camera's table rotation to a centre-relative offset.
        @param dx Offset from the table centre along x.
        @param dy Offset from the table centre along y.
        @return The rotated offset.
        """
        for _ in range(self._turns):
            dx, dy = -dy, dx
        return dx, dy

    def depth(self, y: float) -> float:
        """@brief Sort key for painter's algorithm: smaller y is farther away.
        @param y Table y.
        @return Value that grows towards the camera.
        """
        return y
