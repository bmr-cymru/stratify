#!/bin/sh
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

#
# Configure host system to run stratify.py
#

echo "Enabling ssh root login with password..."
echo redhat | passwd --stdin root
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
echo "Starting ssh daemon..."
systemctl start sshd
echo "Downloading stratify.py..."
curl --insecure -o stratify.py https://gitlab.cee.redhat.com/breeves/stratify/-/raw/main/stratify.py
echo "Downloading ks.cfg..."
curl --insecure -o ks.cfg https://gitlab.cee.redhat.com/breeves/stratify/-/raw/main/ks.cfg
echo
echo "Host IP addresses:"
ip addr show | grep 'inet\>' | grep -v '127\.0\.0\.1'
