# Proposal

## Why

The main menu currently separates local and AI matches even though both use the same match setup, and match choices are not restored for the next round. LAN discovery also lacks meaningful room names and a shared pre-match lobby for players to confirm their appearance before the host starts.

## What Changes

- Replace separate local and AI entries with one **VS** entry; group LAN hosting/joining and help pages in their own submenus.
- Persist the last match setup and restore it when configuring the next match.
- Let a LAN host name the room and show that name in clients' discovery results.
- Add a shared LAN lobby roster where each player can select a paddle color and style; synchronize choices to all peers.
- Keep the match start under host control and disable it until all configured remote seats have joined.
- Update English and Spanish UI text, the user guide, and focused automated tests.

### Non-goals

- Changing match rules, arenas, extras, AI behavior, or paddle rendering beyond using the selected cosmetics.
- Adding player-ready votes, automatic match start, internet matchmaking, relay, or NAT traversal.
- Allowing the host to choose or override a remote player's cosmetics.

## Capabilities

### New Capabilities

- `ui-menus`: Group the VS, LAN, and help entry points and persist the previous match setup.
- `lan-multiplayer`: Name discoverable rooms and provide a shared lobby with synchronized player cosmetics and host-controlled start gating.

### Modified Capabilities

None. The repository has no archived base specs yet; these new capability specs capture the additional behavior without editing the in-progress bootstrap change.

## Impact

- UI flow and persisted settings in `src/pongwars/ui/screens.py` and `src/pongwars/core/settings.py`.
- LAN lobby, discovery, and protocol behavior in `src/pongwars/ui/lan.py` and `src/pongwars/net/`.
- English/Spanish locale catalogs, LAN user documentation, and focused UI/network tests.
- The LAN protocol version changes to represent the room and lobby cosmetic fields; peers with older protocol versions remain incompatible and are rejected.
