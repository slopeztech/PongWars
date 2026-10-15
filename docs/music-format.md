# `.pws` song format

Songs live in `src/pongwars/data/music/*.pws`, are parsed by `audio/songfile.py`,
synthesized by `audio/sequencer.py` and played by the jukebox (`audio/jukebox.py`).

The jukebox picks songs at random for the current context (never the one that just
played), leaving 2-3 seconds of silence between songs.

## Header

```
title  = Neon Lobby
artist = Pixel Pete
tempo  = 96          # quarter-note BPM, 40-300
meter  = 4/4         # 4/4, 3/4, 6/8, ...
volume = 0.8         # 0-1
use    = menu, match # menu | match | any
```

## Instruments

```
instrument lead = square duty=0.5 volume=0.4 attack=0.01 decay=0.1 sustain=0.7 release=0.1
instrument pad  = triangle
instrument bass = saw
instrument kick = noise
```

Waves: `square`, `triangle`, `saw`, `noise`.

## Sections

```
[section a]
lead: | C4:4 E4:4 G4:4 R:4 | C5:2. R:4 |
bass: | C2:2 G2:2 | C2:1 |
kick: | X:4 R:4 X:4 R:4 | X:4 R:4 X:4 R:4 |
```

- Note: `PITCH[#|b]OCTAVE:DENOM[.]`, e.g. `C#4:8`, `A4:2.` (denominators 1-32, `.` = x1.5).
- `R:n` is a rest, `X:n` a noise hit (noise instruments only).
- Every bar must add up to the meter exactly, otherwise the file is rejected with its line number.
- `#` starts a comment at line start or after whitespace.

## Arrangement

```
[arrangement]
intro a*2 b a b end
```

`name*N` repeats a section N times.

## Adding a song

Drop a valid file in the music folder; it is picked up on the next start. Invalid
files are skipped and logged ("Skipping song ...").
