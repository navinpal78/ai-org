# WiFi

Applies to: any wireless fault, and any intermittent fault that stops when
someone uses a cable.

Wireless gets blamed for wired problems constantly, because "it works when I
plug in" feels conclusive. It is not: plugging in changes the entire path,
including which DNS resolver and which address assignment are used. Establish
that the difference is *wireless* before diagnosing wireless.

## Establish that it is wireless at all

```bash
ip -br link                       # which interface, and is it up
nmcli -f IN-USE,SSID,BSSID,CHAN,RATE,SIGNAL,SECURITY dev wifi list
iw dev wlan0 link                 # the negotiated details
```

- **SSID visible, not associated** - authentication or the AP is down.
- **Associated, no DHCP address** - the AP is up, the network side is not
  handing out addresses. That is not a radio problem.
- **Associated, address, but no connectivity** - now you are into DNS and
  routing, and the radio is fine.

Say which of those you are in. It stops the user hunting for radio problems
that are not there.

## Signal

`SIGNAL` in `nmcli` is dBm, and it is negative. The thresholds that matter:

| dBm | Quality | Usable for |
|---|---|---|
| -30 | Excellent | Everything, right next to the AP |
| -50 to -60 | Good | Everything, normal rooms |
| -60 to -70 | Workable | VoIP and browsing, video may stutter |
| -70 to -80 | Marginal | Drops, reconnects, stalls. Often the actual fault. |
| below -80 | Unusable | Association will fail or flap |

The number to watch is the **difference between the RSSI you have and the best
RSSI available in that area**, not the absolute value. -70 is fine next to the
access point and useless at the far end of the house. Scan and compare:

```bash
nmcli -f BSSID,SSID,CHAN,SIGNAL dev wifi list
```

If a much stronger BSSID for the same SSID exists, the client has roamed to a
weak repeater or a distant AP. That is a placement or band problem, not a
driver problem.

## Bands and channels

The 2.4GHz band has only three non-overlapping channels: 1, 6, 11. Anything else
overlaps, and in a dense area the band is unusable rather than slow.

```bash
iw dev wlan0 scan | grep -E 'SSID:|freq:|signal:'
```

- 2.4GHz: fix the channel to 1, 6, or 11. Width 20MHz. Never auto.
- 5GHz: much more spectrum, but shorter range and more walls in the way.
- 6GHz: fast and short-range. Devices that support it will happily hop onto it
  in the wrong room.

An AP left on "auto" picks a channel that may collide with a neighbour - and in
a terraced house or an apartment block, that is a real and common fault. A fixed
channel on 1, 6, or 11 fixes a surprising share of "the wifi is unreliable"
reports.

## The 2.4/5GHz preference problem

A dual-band client that prefers 2.4GHz for range will use the slower band even
next to the AP. If throughput is the complaint rather than coverage, check which
band it actually chose - `iw dev wlan0 link` shows the current frequency, and a
5GHz-capable client on 2.4GHz is a common and fixable finding.

## Interference

Non-WiFi 2.4GHz emitters: Bluetooth headsets, wireless mice, some monitors,
microwaves, poorly shielded baby monitors, and some Zigbee devices.

The test that identifies interference rather than a fault: does throughput
collapse when the suspected device is off? That is a specific, cheap, decisive
test. "Unplug the mouse and try" is a good diagnostic step precisely because the
answer is unambiguous either way.

## Flapping

Association dropping repeatedly is nearly always one of: signal at the edge of
coverage, channel contention, or a power-save setting in the driver. It is
almost never the router needing a reboot.

```bash
journalctl -u NetworkManager -f | grep -i deauth
```

A flood of `deauthenticated by peer` points at the AP side or the channel. A
lone host flapping while others are stable points at that host's driver or
power settings.

## What to hand back

The operator cannot see any of this without running something. Give one command,
say which of the three states above it will distinguish, and say what you expect
to see. A wireless diagnosis made from the description alone is a guess, and you
should label it as one.
