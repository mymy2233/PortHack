#!/bin/bash
echo "root:YourKnownPasswordHere" | chpasswd
passwd -u root
