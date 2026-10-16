# Tasks

## 1. Main menu and remembered setup

- [ ] 1.1 Group the main menu into VS, LAN, and Help routes while keeping Appearance, Settings, and Quit; add navigation tests in `tests/unit/test_phase6.py` and `tests/unit/test_lan_ui.py`.
- [ ] 1.2 Persist and restore the last started match setup, validate saved values against current choices, and cover normal and invalid settings in `tests/unit/test_phase6.py`; update `docs/user-guide.md` with the new menu and persistence behavior.

## 2. Named LAN discovery

- [ ] 2.1 Add bounded room-name input and persistence to LAN setup; extend the versioned discovery protocol and `HostInfo` so search results show room name, host name, and occupancy; verify with `tests/unit/test_net.py` and document room naming in `docs/user-guide.md`.

## 3. Shared LAN lobby

- [ ] 3.1 Add the client lobby roster and per-seat color/style controls; validate and broadcast client-owned choices from the host and apply authoritative cosmetics on both renderers; verify with `tests/unit/test_net.py` and `tests/unit/test_lan_ui.py`.
- [ ] 3.2 Disable and guard host start until every configured remote seat has joined; test empty-seat blocking and full-lobby start in `tests/unit/test_lan_ui.py`; update English/Spanish lobby strings and the LAN section of `docs/user-guide.md`.

## 4. Integration verification

- [ ] 4.1 Run the full `pytest` suite, `ruff check`, `mypy`, Doxygen generation, and strict OpenSpec validation; resolve any regressions introduced by this change.

## Workflow follow-up

- Archive the change after implementation, review, and validation are complete.
