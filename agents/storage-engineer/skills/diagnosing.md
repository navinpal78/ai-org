# Diagnosing

Applies to: any storage fault.

The order below is not a preference. Skipping to a fix before establishing the
shape of the storage is how a filesystem repair is run against the wrong device.

---

## Step 1 - The shape of the storage

Read-only. Ask for this before anything else, and never propose a change until
you have it.

```bash
lsblk -o NAME,SIZE,FSTYPE,FSAVAIL,FSUSE%,MOUNTPOINT,MODEL,SERIAL
findmnt -D                      # what is mounted where, all of it
df -hT                          # capacity by filesystem, with type
df -i                           # inodes
```

What you are establishing:

- **Which physical device** is the one in question, by model and serial, not by
  assumed ordering. `/dev/sda` is not a fixed thing; device order changes
  between boots, and assuming otherwise has destroyed the wrong disk.
- **Which filesystem** is on it, and what it is mounted at.
- **How full** it is, in both bytes and inodes.
- **Whether it is a whole disk or a partition**, and whether anything else is
  mounted from the same device.

A device with no filesystem and no partitions is one thing. A device with a
mounted filesystem is a completely different proposition, and you cannot tell
them apart without this output.

## Step 2 - What the kernel said

Read-only, and the single most informative command in storage diagnostics:

```bash
dmesg -T | grep -iE 'error|fail|ata|scsi|nvme|ext4|xfs|btrfs|zfs|i/o|remount'
journalctl -k -p err -b
```

The kernel reports the device and the error with a timestamp, and it says
things like:

| Kernel message | Means |
|---|---|
| `remounting filesystem read-only` | The FS hit an unrecoverable error and protected itself. **The cause is above this line in the log.** |
| `I/O error, blkdev` | The device failed to read or write. This is the device, not the filesystem. |
| `ata... failed command` / `resetting link` | The device or the link to it. |
| `checksum errors` | Silent corruption, and it may already be spread. |
| `EXT4-fs error` / `XFS metadata corruption` | Metadata damage. Repair is possible but destructive. |

Get the *first* error, not the last. The first one is the cause; everything
after it is consequence.

## Step 3 - The three common non-faults

Before assuming failure, rule out the boring causes. They are extremely common
and look like disasters.

### Inode exhaustion

```bash
df -i
```

"No space left on device" with `df -h` showing 40% used is inode exhaustion -
typically millions of small files. The fix is deleting files or raising inode
count, and nothing at all to do with the disk.

### The read-only remount

A filesystem that has gone read-only is *working as designed*. The kernel found
an error and made it read-only to stop further damage. Do not remount it
read-write "to fix it" - that is how a recoverable filesystem becomes
corruption. Find the error that caused the remount, fix the hardware if
necessary, then repair.

### Full, or reserved blocks

On ext4, 5% is reserved for root, so a filesystem can be "full" for a normal
user with space still showing. `tune2fs -l /dev/sdXN | grep -i reserved` shows
the setting. Also check the quota for the user or group, which can be hit while
the filesystem has room.

## Step 4 - The filesystem check, read-only first

```bash
sudo fsck -n /dev/sdXN          # -n means answer only, change nothing
```

Run it with `-n` **every time**, first, and read what it says. It tells you
whether the filesystem is damaged without touching anything. Only after you
know that, and after the data is backed up or imaged, do you run a repair.

If `fsck -n` reports errors, do not run a bare `fsck` on the only copy.

## Step 5 - The device health

```bash
sudo smartctl -a /dev/sdX        # or -x on NVMe
```

Read `skills/smart-and-health.md` before you interpret it, and do not conclude
from a single reading.

## Step 6 - RAID, ZFS, Btrfs

```bash
mdadm --detail /dev/mdX          # or: cat /proc/mdstat
zpool status -v
zpool list
btrfs device stats /
btrfs scrub status /
```

Degraded arrays need a particular care: a rebuild reads every block of every
surviving disk. If another disk fails mid-rebuild and there is no redundancy
left, the array is gone. Know the rebuild progress and the state of every
member before recommending anything else.

## The report

When you hand back, state:

1. **The device**, by model and serial, as the output showed it.
2. **The finding**, and the evidence.
3. **What it is not** - the boring causes you ruled out.
4. **The single next read-only check**, and what each possible result would mean.
5. **Whether any data is at risk right now.** If yes, that comes first, in
   plain words: "stop writing to this disk."
