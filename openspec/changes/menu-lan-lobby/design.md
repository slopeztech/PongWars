# Design

## Context

The UI uses a keyboard-driven screen stack with `MainMenuScreen` and a reusable `SetupScreen`. User preferences are stored in JSON through `Settings`. LAN matches use an authoritative UDP host, a client session, a versioned codec, and UDP discovery. See the proposal and capability specs for the user-visible behavior.

## Goals / Non-Goals

**Goals:**

- Reuse the existing setup screen, settings persistence, and screen-stack navigation.
- Keep match configuration separate from user preferences and safely recover from invalid saved values.
- Keep the host authoritative for LAN roster, cosmetics, and match start.
- Preserve the existing UDP transport abstraction and deterministic simulation.

**Non-Goals:**

- Replace the LAN transport or simulation protocol architecture.
- Persist transient roster data or remote-player choices as part of a match save.
- Add cosmetic asset downloads, ready voting, or automatic match start.

## Decisions

### D1. Route menu categories through small submenus

The main menu will expose VS, LAN, Help, Appearance, Settings, and Quit. VS will open the existing configurable setup without prescribing a controller type; the controller rows continue to distinguish local humans and AI. LAN and Help will each open a small submenu that routes to their existing screens.

This keeps keyboard navigation and setup behavior in the existing `ScreenStack`. Keeping separate local/AI top-level entries was rejected because both flows share the same setup surface and differ only by controller selection.

### D2. Persist the previous setup as validated settings data

Store the last started setup in a JSON-compatible `Settings.last_match` mapping: mode, arena, controller choices, AI difficulty, extras, view, mode options, and LAN room name. Save it when setup starts a match, not while the user is editing or cancels. On the next setup, validate values against current registries and declared ranges one field at a time; invalid or removed values fall back to the normal setup defaults.

The immutable `MatchConfig` remains the runtime and network configuration. Persisting a `MatchConfig` object directly was rejected because it mixes per-match state with user settings and would make malformed or old saved choices harder to recover selectively.

### D3. Carry the bounded room name in LAN discovery

Normalize room names to the protocol's printable character set and a fixed maximum length, with a non-empty fallback. Include the resulting name in discovery replies and display it as the primary discovery entry, with host name and occupancy as supporting details. Room names do not need to be globally unique; the host address distinguishes matches.

No separate matchmaking service or extra discovery round trip is needed. Existing clients that do not speak the new protocol version are rejected by the version handshake.

### D4. Keep lobby cosmetics host-authoritative

Represent each seat's palette index and paddle-style index as bounded integer arrays in lobby roster and match-start messages. A client may submit changes only for its own accepted seat; the host validates those values, updates the roster, and broadcasts the authoritative result. The host's own seat uses the same host-controlled update path. Match renderers consume the synchronized arrays after the host starts the match.

Adding per-seat appearance fields to the existing protocol messages was chosen over a separate asset or customization service: cosmetics are small local indices, and every peer already has the same palette and styles.

### D5. Enforce start eligibility in the host lobby

The host lobby derives eligibility from the configured remote seats and the live host roster. It disables Start while any configured remote seat is open and rechecks eligibility when Start is activated. AI-controlled seats are not treated as missing clients. The host remains the only peer that can initiate the existing match-start handshake; no per-player ready state is introduced.

The UI guard and host-session invariant are both required so a stale menu state or a direct call cannot bypass the lobby rule. Converting unfilled remote seats to AI at start was rejected for this flow because it would silently change the configured player set.

## Risks / Trade-offs

- **Protocol compatibility**: room and cosmetic fields require a protocol version bump → reject incompatible clients clearly and require all LAN peers to use the same release.
- **Old or malformed settings**: persisted values may no longer match current registries → validate each field and keep safe setup defaults.
- **Cosmetic divergence during packet loss**: a client may temporarily display an older roster → the host periodically broadcasts the authoritative roster and includes final values in the start message.
- **Repeated or confusing room names**: room names are not globally unique → show host identity and joined/total player counts in discovery results.

## Migration Plan

No external data migration is required. Older settings files omit `last_match` and continue to load with an empty value. The new protocol version intentionally does not interoperate with older builds; users must update every peer together. Rollback can remove the new setting field and protocol version while leaving existing settings fields intact.
