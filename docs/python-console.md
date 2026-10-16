# Running PongWars from Python

Use this guide if you want to run the game from a terminal or launch it from an
interactive Python console. Players using the Windows installer do not need Python.

## Requirements

- Python 3.11 or newer
- A desktop with a display

## Run from a terminal

Open a terminal in the repository folder, then create and activate a virtual
environment and install the game:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pongwars
```

On macOS or Linux, activate the environment with:

```sh
source .venv/bin/activate
```

Then launch with `python -m pongwars`.

## Run from an interactive Python console

Activate the virtual environment and start Python from the repository folder:

```powershell
.\.venv\Scripts\Activate.ps1
python
```

At the Python prompt, launch the game with:

```python
from pongwars.app import run
run()
```

The call keeps control of the console until the game exits. Close the game window or
choose **Quit** to return to the Python prompt.
