# Backups

Applies to: any question about whether data is safe, and any destructive
proposal that depends on a backup existing.

## A backup you have not restored is a hypothesis

This is the single most important sentence in this skill. A backup's existence
proves nothing; a restore proves everything.

The cheap test that needs no second machine: restore one file to a scratch
location and read it.

```bash
tar -tf /backups/backup-$(date +%F).tar.zst | head     # does it list?
mkdir -p /tmp/restore-test && cd /tmp/restore-test
tar -xf /backups/backup-$(date +%F).tar.zst ./path/to/one/file
diff ./path/to/one/file ~/path/to/one/file && echo "restore verified"
```

Listing the archive is necessary and not sufficient. A tar that lists
correctly and cannot extract is common - usually a truncated file or a
decompression problem. And a full restore into a scratch location, on a
schedule, is the only way to know before you need it.

## 3-2-1

- **3** copies of the data
- **2** different media or systems (not two tarballs on the same disk)
- **1** off-site, or at least physically separate and not on the same power

In a home lab, the cheap version that still meets the spirit: local backup plus
one copy on a machine somewhere else. An external drive in the same room is not
a second copy against theft, flood, fire, or a power surge taking the whole
circuit.

## Snapshots are not backups

A ZFS snapshot, a Btrfs snapshot, an LVM snapshot, and a Time Machine local
snapshot are all excellent and none of them is a backup.

They share the fate of what they snapshot. If the array fails, the disk fills,
or someone runs `zpool destroy`, the snapshots go with it. They protect against
"someone deleted a file", which is the easy mistake. They protect against
nothing else.

A snapshot is a **rollback mechanism**. A backup is a **second copy**. You need
both and they are not substitutes.

## Verify on a schedule, not on the day

```bash
# -t lists the archive without writing anything
tar -tf "$ARCHIVE" > /dev/null && echo "archive readable"
# confirm the newest archive is the one you think it is
ls -lt /backups/ | head
# confirm the restore actually happened, at the recorded time
test -f /var/log/restore-test.log && tail /var/log/restore-test.log
```

An automated monthly restore test is worth more than a daily backup, because it
is the one that has actually been observed. If you cannot test a restore, say
so, and say what the risk is.

## Backups do not replace imaging

Backups preserve the files. Imaging preserves the *device* - its partition
table, its filesystem metadata, everything needed to reconstruct the disk
exactly.

- **Backup** - use when you want the files.
- **Image** (`ddrescue`) - use when the device is failing, before touching it.
- **Snapshot** - use when someone deleted something and you want it back.

Using the wrong one is a common and expensive error. Someone needing an image
takes a nightly file backup, the disk dies the next month, and the partition
table went with it.

## What belongs in a home lab

- Nightly incremental backup of the data, kept 7 days
- Weekly full, kept 4
- Monthly full, kept 6, **off-site**
- The off-site copy rotated with a check that it was not blank
- A monthly restore test, logged
- Documentation of what is backed up, where it lives, and how to restore it

That last item is the one that is always missing and the one that matters when
the person who set it up is unavailable. A backup nobody can restore is
decoration.

## The questions to ask

When someone says "I have backups", before believing any of it:

1. What is actually included, and what is quietly excluded?
2. Where does the second copy physically live? Same room, same building?
3. When did anyone last restore from it, successfully?
4. Is it encrypted, and who holds the key? An encrypted backup nobody can
   decrypt is not a backup.
5. What is the restore command, exactly, for each thing that matters?
6. Does it cover the boot partition and the configuration, or only the data?

If the answer to 3 is "never", say plainly that the backup is untested and
unknown-good, and that this should be fixed before the next hardware failure -
not after it.
