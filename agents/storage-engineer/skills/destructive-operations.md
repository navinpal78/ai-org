# Destructive operations

Applies to: before you write a single command that alters storage.

You do not run these. You hand them over. Handing one over is a briefing, and
this is the format.

---

## The pre-flight checklist

Before proposing anything that writes to a device, all five of these must be
true, and you must be able to show your work for each:

1. **The device is identified.** Not "the second disk" - the output of
   `lsblk -o NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT`. A name, a size, a model
   and a serial, all agreeing.
2. **You know what is on it.** `blkid` and `findmnt` show the filesystem and
   every mount point. An unmounted device with a filesystem is a device someone
   used. "Not mounted" does not mean "empty".
3. **You know it is the device you think it is.** Device names are not stable
   across reboots. Prefer addressing by serial or by UUID where the tool allows
   it, and say so.
4. **There is a second copy of anything that matters.** Not "the data is
   reproducible" - proven, with a restore tested. If there is no backup, the
   correct answer is to make one first, and that is a `ddrescue` operation
   rather than a destructive one.
5. **You have a recovery path for the operation itself.** A console if it is the
   boot device. An image if it is a data device. Saying "if this goes wrong,
   restore from backup" is not a recovery path - the backup may be the thing
   that is missing.

## The command briefing

Every destructive proposal has all seven parts. Anything less is a command
copy-pasted into an outage.

> **1. Device** - `/dev/sdb2`, confirmed by serial `WD-WX41A99KJ0G1` in `lsblk`.
> **2. Command** - `sudo mkfs.ext4 -L data /dev/sdb2`
> **3. What it destroys** - the existing filesystem and everything on it,
>   irreversibly. It does not touch the disk's hardware or the partition table.
> **4. When it is the right answer** - the filesystem is damaged beyond repair
>   *and* the data is backed up or already recovered. Not before.
> **5. What it does NOT fix** - if the disk is failing, a fresh filesystem will
>   corrupt too. Check health first.
> **6. Undo** - none. There is no undo. This is the point of the briefing.
> **7. Confirm afterwards** - `sudo blkid /dev/sdb2` shows the new label and
>   type; `sudo tune2fs -l /dev/sdb2 | head` shows the geometry.

Point 4 is the one people skip, and it is the one that decides whether the
operation is justified at all.

## Operations that are always the wrong first move

| Operation | Why it is never a first move |
|---|---|
| `mkfs.*` | Destroys the filesystem. If the data is merely unreachable, the mount is wrong. |
| `dd if=... of=/dev/sdX` | Overwrites the device. One character changes a rescue into a catastrophe. |
| `fdisk` / `parted` (write) | Moves partition boundaries. A table can be miswritten and the data with it. |
| `fsck` (write mode) | Rewrites metadata. On a failing disk it can finish the job the hardware started. |
| `badblocks -w` | Writes over the whole device. Destroys the filesystem by design. |
| `shred` | Slow, and on SSDs and CoW filesystems it is not even reliable. `wipefs` is enough. |
| `mdadm --zero-superblock` | Removes a disk from an array without telling the array. Breaks the set. |
| `pvcreate` / `vgcreate` | Overwrites existing structures. If the device already has a signature, the tool should refuse - if it does not, you are on the wrong device. |
| `zpool destroy` | Destroys the pool and all its datasets. No confirmation prompt worth trusting. |
| `rm -rf` on a path | Follows symlinks, resolves trailing slashes, and expands variables. The path that deletes `/` is always a plausible typo. |

## `rm -rf` deserves its own warning

The dangerous command is rarely the one an attacker types. It is the one a
tired person types at 2am, where a variable is empty and a trailing slash is
missing.

- **Never expand a variable in an `rm` without showing what it expands to.**
  `echo "$TARGET"` first, always, and make that a separate command the operator
  runs deliberately.
- **A path is not what you think it is** if it is a symlink, a bind mount, or
  an autofs mount. `findmnt -T /path/to/target` tells you what is really there.
- **Prefer moving to a quarantine directory** over deleting. Recovery is then
  a `mv`, and you find out in a week that you needed the file.
- **Never `rm -rf` a mount point's contents to "clear" it.** That unmounts
  nothing and destroys the mounted filesystem's data.

## What to do instead, usually

Most of the time there is a read-only way to find out, and it takes one command:

- Cannot mount? `blkid`, `file -s`, `dmesg`. All read-only.
- Suspect a failing disk? `smartctl -a`, then `ddrescue` to an image, then work
  on the image.
- Suspect duplicate files filling inodes? `find /path -xdev -type f -printf '%h\n' | sort | uniq -c` - read-only.
- Need to clear a filesystem before reusing a device? `wipefs -a` is far less
  destructive than `mkfs` and is enough to remove stale signatures.
- Suspect a filesystem problem? `fsck -n` first. Always. It is the whole answer
  half the time and it changes nothing.

## When the operator insists

Sometimes they need to destroy something, and they may be right - the disk is
dead, the filesystem is shot, the data is already gone. That is legitimate.

Your job then is not to refuse but to make the consequence explicit and get it
confirmed out loud: which device, what is lost, and that there is no undo. If
they confirm, hand it over. Record in your reply that you flagged it and they
confirmed. That is what makes the handover safe rather than merely cautious.
