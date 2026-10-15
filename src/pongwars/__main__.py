"""@package pongwars.__main__
@brief Command line entry point (`python -m pongwars` / `pongwars`).
"""


def main() -> int:
    """@brief Launch the game.

    @return Process exit code.
    """
    from pongwars.app import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
