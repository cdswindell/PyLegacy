# Exclusive local ramp claims

Ramp destinations stay on the requesting process. That process owns the ramp
until completion or an overriding command; another ramp request fails rather than
canceling or replacing it. Ordinary speed, RPM, and labor commands still use the
existing transport unchanged. No command/PDI buffer, dispatcher, or listener has
ramp ownership hooks.

`TMCC2EngineCommandEnumEx.RAMP_CLAIM` and `RAMP_RELEASE` use the existing state-only
`CommBuffer.update_state()` path. They never go to the Base 3 or SER2 and have no
Lionel database mapping. `TARGET_SPEED` remains defined but is not transmitted.
The variable-command framing and logical engine/train address header are unchanged.

## Ownership

- With no known owner in local engine/train state, a new ramp records its claim
  locally, publishes it, and starts emitting steps without waiting for its echo.
  Publication runs on the ramp thread, not the GUI thread. There is no discovery
  interval, confirmation timeout, or peer round trip.
- Requests for an already known remote owner fail immediately. If two devices
  start before seeing each other's claims, the earlier millisecond timestamp wins,
  regardless of arrival order. Equal timestamps are ordered by packed IPv4 address,
  process nonce, then claim ID, with the lowest tuple winning on every device.
  The loser cancels silently when the earlier claim arrives; it does not queue an
  automatic restart. Its already-submitted commands cannot be recalled.
- The owning process can retarget its own ramp without acquiring another claim.
- Other GUI throttles are disabled while the remote claim is active. Reported
  speed continues to update, but held or pending throttle input is discarded,
  not queued for execution after the claim releases. Safety controls stay usable.
- Completion or cancellation publishes a matching release. A stale or rejected
  claim cannot replace the incumbent, and its release cannot clear a different
  owner. Active claims are included in ordinary new-client state synchronization.

The IP address remains in the announcement for identification. The former port
field is retained as a nonzero 16-bit process nonce alongside the 16-bit claim ID;
it does **not** name a listening socket. A six-byte unsigned Unix timestamp in
milliseconds is assigned once when the claim is created and retained on refresh
and release. It also distinguishes a reused endpoint/ID from an older claim.
The wire payload is 16 bytes (logical address 2, IPv4 4, nonce 2, ID 2, timestamp 6),
encoded in the existing three-byte variable words for a 63-byte packet. No GUIDs,
destinations, or ramp sequences are transmitted. There are no cancellation
listeners, peer connections, transfer acknowledgments, or inherited histories.

## Timing and safety

`ramp_peer.py` retains `CLAIM_REFRESH = 5.0` and `CLAIM_TTL = 15.0` to refresh active
claims and recover stale ownership after a disconnected/crashed process. These
announcements occur only for local ramps, not on every ordinary command.
Local refresh and release do not depend on receiving an echo either. Publication
errors still abort startup; a missing return broadcast does not. The underlying
transport retains its existing network retry behavior.

Halt, reset, direction changes, immediate stop, and shutdown (including supported
numeric aliases) override active and acquiring ramps. Repeated safety commands and
direction toggles still override; redundant forward/reverse commands do not. They
travel as ordinary commands; the owning device recognizes them and aborts locally.
No other process contacts the ramp to stop it. Ordinary cancellation is silent;
only hard-stop protection may reassert zero speed and neutral effort.

The existing `ECHO_TTL = 2.0` and independent local/Base-RX send-order ledgers remain
for ordinary speed echoes. Unexplained Lionel speed commands can still abort a
ramp; an identical eligible echo is inherently indistinguishable from that remote.

## Deployment and limits

Update both server and clients together: the timestamped packet format is not
compatible with older ramp claims. No ramp TCP port or firewall rule is needed.
`PYTRAIN_RAMP_PORT` is no longer used. `PYTRAIN_RAMP_HOST` can still override the
advertised IP; otherwise client registration or a UDP route-only probe supplies
it. The probe sends no packet and does not bind a cancellation listener.

Keep device clocks synchronized through normal network time synchronization:
timestamp ordering is deterministic, but clock skew can favor the device whose
clock runs behind rather than the operator who actually moved first. This
cooperative protocol assumes a trusted layout LAN; it does not guarantee mutual
exclusion across network partitions or missing announcements. Expired claims
allow recovery. In a simultaneous-start race, both ramps may briefly emit speed,
RPM, labor, or dialog commands before the conflict is resolved. Existing ordinary
speed-echo arbitration and safety overrides still apply to in-flight commands.
Physical Base 3 and train-room Wi-Fi behavior still needs a layout test.
