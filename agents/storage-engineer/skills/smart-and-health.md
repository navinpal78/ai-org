# SMART and disk health

Applies to: a disk that is slow, failing, or suspected of failing.

## SMART is a trend, not a verdict

A single `smartctl -a` reading is a snapshot. Every attribute is a normalised
value that vendors compute differently, and a value that looks alarming on one
disk is normal on another.

**Never conclude "this disk is dying" from one reading.** The useful question is
not "what does 194 temperature look like" but "has this changed, and how fast".

The two things that make a reading meaningful:

```bash
sudo smartctl -a /dev/sdX                  # current values
sudo smartctl -l selftest /dev/sdX         # history of logged self-tests
sudo smartmontools -a /dev/sdX             # history if smartmontools installed
```

`smartctl -l selftest` is the one that matters. It shows that the drive has been
running its own self-tests, and it logs the outcome over time. A drive that
logged a failed short self-test last Tuesday is a different proposition from one
with a clean history.

## Attributes that matter

Vendor-specific, but these families are consistent:

| Attribute | Healthy behaviour | Worry when |
|---|---|---|
| `Reallocated_Sector_Ct` (5) | 0, stays 0 | Any growth. The drive is remapping bad sectors. |
| `Pending_Sector_Ct` (197) | 0 | Non-zero. Sectors have failed and are unreadable. |
| `Uncorrectable_Sector_Ct` (198) | 0 | Non-zero. Unrecoverable data loss has happened. |
| `Reallocated_Event_Count` | 0 | Growing |
| `UDMA_CRC_Error_Count` (199) | 0, stable | **Growing means the cable or link, not the platters.** Replacing the disk fixes nothing. |
| `Power_On_Hours` | informational | Compare against the drive's rated life |
| `Load_Cycle_Count` | informational | Extreme values indicate aggressive power management |

`UDMA_CRC_Error_Count` is the one people misdiagnose most often. It belongs to
the *interface*, not the disk: a bad SATA cable, a marginal power supply, or a
flaky HBA produces it, and the disk is fine. Replacing the drive wastes the
drive and leaves the fault.

`Reallocated_Sector_Ct` is the opposite: it belongs to the disk, and growth
means the platters are degrading. This is the one that predicts failure.

## The dangerous SMART commands

`smartctl -t` is not read-only in the sense that matters:

```bash
sudo smartctl -t short /dev/sdX     # tells the drive to wake and test itself
```

- It **spins up a sleeping drive**. On a drive you are keeping as a cold spare
  in a slot, that wears it, and in a hot-swap backplane it may not return.
- On a drive with read errors, waking it can be the thing that finally kills it.
- On some USB bridges it hangs the whole bus.

Read the attributes with `-a` or `-x`. Do not run `-t` on a drive you are trying
to preserve.

## When a disk is failing

The order is not negotiable:

1. **Stop writing.** Every write risks more loss.
2. **Get the history** - `smartctl -l selftest`, not just `-a`.
3. **Image the device before touching it.** This is the step people skip and
   regret.

```bash
sudo ddrescue -n /dev/sdX /mnt/backup/sdX.img /mnt/backup/sdX.map
# first pass, skip bad blocks, gets the bulk of the data off quickly
# second pass, go back over the bad blocks as many times as it takes
sudo ddrescue -d /dev/sdX /mnt/backup/sdX.img /mnt/backup/sdX.map
```

`ddrescue` is the right tool and `dd` is not: `dd` stops at the first read error,
which is precisely the one that matters. `ddrescue` continues, logs, and can be
resumed.

**Disk is large enough that one copy will not fit?** Then do not destroy
anything. Say so, and let the operator decide. A failed read is not an emergency
that requires improvising.

4. **Work on the image.** Run `fsck` on the image, mount the image loopback,
   copy files off. The original stays untouched, which means every attempt is
   reversible.
5. **Replace the disk.** Then copy back. Not the other way round.

## What a failing disk looks like in practice

- I/O errors in `dmesg` on specific sectors
- Reads that take seconds instead of milliseconds
- `EXT4-fs error`, `XFS metadata corruption` that reappears after a repair
- Files that are corrupt rather than missing - the worst symptom, because it is
  silent and spreads
- A filesystem that goes read-only and stays there

When corruption is already spreading, **every minute of continued use makes it
worse.** Say that in plain words, and make the stop-writing instruction the first
thing in your reply.

## What not to conclude

- Not "the SMART values are fine" - check the history, and check the CRC count.
- Not "it is just a bad sector" - reallocated sectors are the disk coping; a
  rising count is the disk failing.
- Not "let's test it with `badblocks -w`" - that writes to every block and
  destroys whatever filesystem is there. `badblocks -s` is read-only.
- Not "reformat it and see if the problem goes away" - if the disk is failing,
  the new filesystem will fail too, and you have destroyed the recoverable
  data to learn nothing.
