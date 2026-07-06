#!/bin/bash
# Mount the ICFO NOE group network share.
# Run as yzamir. Will prompt for ICFO domain password.
# This is normally handled by pam_mount on interactive login.
# Use this script after a reboot if the mount is missing.

MOUNT_POINT=/ICFO/groups/NOE

if mountpoint -q "$MOUNT_POINT"; then
    echo "Already mounted: $MOUNT_POINT"
    ls "$MOUNT_POINT" | head -5
    exit 0
fi

echo "Mounting $MOUNT_POINT ..."
sudo mount -t cifs //files.icfo.es/groups/NOE "$MOUNT_POINT" \
    -o username=yzamir,uid=13180,gid=35001,domain=icfonet,vers=2.1

echo "Done. Contents:"
ls "$MOUNT_POINT" | head -10
