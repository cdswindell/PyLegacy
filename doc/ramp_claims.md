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

- A new local ramp publishes its claim and waits for that announcement through the
  normal server/broadcast path before emitting speed or component commands. There
  is no discovery interval or peer round trip. The wait runs on the ramp thread,
  not the GUI thread.
- The first accepted live claim wins. Concurrent later requests fail without
  emitting ramp steps. Requests for an already known remote owner fail immediately.
- The owning process can retarget its own ramp without acquiring another claim.
- Other GUI throttles are disabled while the remote claim is active. Reported
  speed continues to update, but held or pending throttle input is discarded,
  not queued for execution after the claim releases. Safety controls stay usable.
- Completion or cancellation publishes a matching release. A stale or rejected
  claim cannot replace the incumbent, and its release cannot clear a different
  owner. Active claims are included in ordinary new-client state synchronization.

The IP address remains in the announcement for identification. The former port
field is retained as a nonzero 16-bit process nonce alongside the 16-bit claim ID;
it does **not** name a listening socket. There are no cancellation listeners,
peer connections, transfer acknowledgments, or inherited command histories.

## Timing and safety

`ramp_peer.py` retains `CLAIM_REFRESH = 5.0` and `CLAIM_TTL = 15.0` to refresh active
claims and recover stale ownership after a disconnected/crashed process. These
announcements occur only for local ramps, not on every ordinary command.
`CLAIM_TIMEOUT = 0.75` bounds waiting for broadcast confirmation after the existing
state-publication call returns. Missing confirmation fails closed without sending
ramp steps. The underlying transport retains its existing network retry behavior.

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

Update both server and clients; old handoff implementations are not compatible
with exclusive ownership. No ramp TCP port or firewall rule is needed.
`PYTRAIN_RAMP_PORT` is no longer used. `PYTRAIN_RAMP_HOST` can still override the
advertised IP; otherwise client registration or a UDP route-only probe supplies
it. The probe sends no packet and does not bind a cancellation listener.

This cooperative protocol assumes the normal ordered server broadcasts and a
trusted layout LAN. Expired claims allow recovery, not a guarantee of mutual
exclusion across network partitions. Already queued train commands cannot be
recalled. Optional tower/engineer dialogs retain their existing scheduling, so a
simultaneously rejected request can announce dialog before its rejection, but
cannot emit speed/RPM/labor steps. Physical Base 3 and train-room Wi-Fi behavior
still needs a layout test.
