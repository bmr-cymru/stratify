F34 Stratis rootfs with stratify.py
===================================

  1. Overview & Requirements
  2. Configuring virtual machines
  3. Enable sshd (optional)
  4. Download stratify.py
  5. Installation using Live media
  6. Installation using host system
  7. If something goes wrong
      7.1 Rescuing a stratis system with stratify
  8. stratify.py options
  9. Hacking stratify.py


# 1. Overview & Requirements
----------------------------

tl;dr: run `stratify --text --target vda --kickstart /root/ks.cfg` in a root
terminal on a live VM to install a system with Stratis as the root file
system.

To create virtual machines with a Stratis root file system using stratify.py
you will need:
 
* The URL for the stratify.py script
* An `x86_64` virtual machine using BIOS and running Fedora 34,
  either:
   * A VM running the F34 Workstation Live media (recommended)
   * A VM installed with any F34 media with additional storage for Stratis
* (Optional) a kickstart file to automate installation settings

The script can be run in either a live environment using the Fedora
Workstation Live ISO image, or in a "host" virtual machine previously
installed with Fedora 34 and configured with additional storage for
a stratis root file system to be installed.

The quickest method is to use the Live media, since this does not
require an instllation to be carried out before starting.

Using the Workstation live media does not affect the installed system:
the installation uses whatever Fedora variant is specified in the `--repo`
argument to stratify.py (or the repo command in the kickstart file if
used).

A kickstart file can be given on the command line to make the installation
fully automatic. An example is available at [1].


# 2. Configuring virtual machines
---------------------------------

# 2.1 Configuring the live environment
--------------------------------------

i) Create a new virtual machine instance using the Fedora Workstation 34 Live
     image.

ii) Allocate at least 10GiB of storage as a single VirtIO disk (e.g. vda)
and allow at least 2048MiB of guest memory.

ii) Boot the Live image and wait for the Live desktop to load.

iii) Open a terminal and run "sudo su -" to gain root privileges.


# 2.2. Configuring a host virtual machine
-----------------------------------------

The host VM's role is to provide a Fedora 34 environment where stratify can
run that provides the ability to install software packages with dnf and to
call the command line anaconda installer program. A minimal install using any
F34 media is acceptable - the host environment is only needed for the duration
of the installation.

i) Boot the host VM with the installation media and any kickstart or other
options. The guest should have sufficient storage for the host install and
will require one additional disk of at least 10GiB for the Stratis root
install. The additional storage can either be ignored during the initial host
installation (using manual partitioning) or it can be added to the guest after
the initial host installation has been carried out.

ii) Set a root password and allow the installation to complete normally.

iii) Boot the VM and log in to the root account.


# 3. Enable sshd (optional)
---------------------------

Optionally enable the sshd daemon for root logins with a password:

```
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl start sshd
```

 If using the live environment it is necessary to set a root password (or enable
 ssh keys):

```
passwd
```

# 4. Download stratify.py
-------------------------

Download the script using wget or curl:

```
# wget --no-check-certificate -O stratify.py https://gitlab.cee.redhat.com/breeves/stratify/-/raw/main/stratify.py
```

or:

```
# curl --insecure -o stratify.py https://gitlab.cee.redhat.com/breeves/stratify/-/raw/main/stratify.py
```

Optionally download the example kickstart:

```
# wget --no-check-certificate -O ks.cfg https://gitlab.cee.redhat.com/breeves/stratify/-/raw/main/ks.cfg
```

or

```
curl --insecure -o ks.cfg https://gitlab.cee.redhat.com/breeves/stratify/-/raw/main/ks.cfg
```

The kickstart file contains two hashed passwords: to replace them use the
openssl passwd command:

```
$ openssl passwd -6 "password"
$6$VvxJNYbsqtX66EjI$24HCGhwKOn8lkNMxglZZb90utAc66Jgy3oM6T5DhIdErbpElbviCyikPpRpmERG69O/SyVpZ9YPRuaM22A52G.
```
# 5. Installation using Live media
----------------------------------

Assuming that the storage to be used for Stratis is using VirtIO device vda,
either in a terminal running in the Live desktop or an ssh terminal run the
following command:

```
# python stratify.py --text --target vda
```

This will download required packages, partition vda and create a boot file
system on vda1. A stratis pool named p1 and a file system named fs1 will be
created and mounted at /mnt/stratisroot.

Stratify will then run the anaconda installer. A kickstart file may be given
by passing "--kickstart /root/ks.cfg" (the path must be absolute).

One the system has been installed hit "enter" and the script will install
build dependencies, clone the stratis git repositories and initiate a build.
Once the build is complete the script configures grub2 and creates a boot
entry for the Stratis system.

Once the script logs "Stratis root fs installation complete." the target
system is fully installed and unmounted and the system can be safely rebooted.
The only boot entry in the grub menu corresponds to the Stratis installation.

# 6. Installation using host system
-----------------------------------

Assuming that the system has been installed to VirtIO device vda, and that the
storage available for Stratis to use is on VirtIO device vdb, run the
following command:

```
# python stratify.py --text --target vdb
```

This will download required packages, partition vda and create a boot file
system on vda1. A stratis pool named p1 and a file system named fs1 will be
created and mounted at /mnt/stratisroot.

Stratify will then run the anaconda installer. A kickstart file may be given
by passing "--kickstart /root/ks.cfg" (the path must be absolute).

One the system has been installed hit "enter" and the script will install
build dependencies, clone the stratis git repositories and initiate a build.
Once the build is complete the script configures grub2 and creates a boot
entry for the Stratis system.

Once the script logs "Stratis root fs installation complete." the target
system is fully installed and unmounted and the system can be safely rebooted.

Before the Stratis system can be booted the VM must be reconfigured to boot
from the device given to `--target` in order to use the correct bootloader.

The first boot entry will correspond to the Stratis installation but the grub
menu will also include entries to allow booting the original host installation
(the Stratis entry should be the default).

# 7 If something goes wrong
---------------------------

If the installation fails (e.g. to to a kickstart error) use `--wipe` to
erase the disk contents before repeating.

The disk partitioning and file system creation can be skipped by using
`--nopartition`. This assumes a /boot file system exists at the first
partition of the target device and that the second partition contains
a pool and file system with the correct names.

## 7.1 Rescuing a stratis system with stratify
----------------------------------------------

If a Startis root file system installation fails to boot the stratify script
can be used to install dependencies and re-create the chroot layout for
debugging purposes.

As with installation this can be done from either a host system installed
with Fedora 34, or from the Fedora 34 Live Media.

To rescue a system, start the system and download stratify.py and then as
root run run:

```
# python stratify --target <device> --rescue
```

This will mount the file systems from the target device and set up the
chroot before starting a shell in the stratis rootfs system.

Exiting the shell will tear down the chroot and leave the system ready
to reboot.

To clean up chroot mounts left by a failed installation use `--cleanup`:

```
# python stratify --target <device> --cleanup
```

# 8. stratify.py options
------------------------

```
usage: stratify.py [-h] [-d TARGET] [-b] [-c] [-e] [-f FS_NAME] [-k KICKSTART] [-m] [-n] [-p POOL_NAME] [-r] [-s SYS_ROOT] [-t] [-w]

Fedora 34 Stratis Root Install Script

optional arguments:
  -h, --help            show this help message and exit
  -d TARGET, --target TARGET
                        Specify the device to use
  -b, --bios            Assume thesystem is using BIOS firmware
  -c, --cleanup         Clean up and unmount a rescue chroot
  -e, --efi             Assue thesystem is using EFI firmware
  -f FS_NAME, --fs-name FS_NAME
                        Set the file system name
  -k KICKSTART, --kickstart KICKSTART
                        Path to a local kickstart file
  -m, --mbr             Use MBR disk labels
  -n, --nopartition     Do not partition disks or create Stratis fs
  -p POOL_NAME, --pool-name POOL_NAME
                        Set the pool name
  -r, --rescue          Rescue a Stratis root installation.
  -s SYS_ROOT, --sys-root SYS_ROOT
                        Set the path to the system root directory
  -t, --text            Use text mode for Anaconda
  -w, --wipe            Wipe all devices before initialising
```

# 9. Hacking stratify.py
-----------------------

The script is very simple and should be easy to modify for local requirements:
most of the high-level logic is driven directly from the main() function using
helper functions to install software, clone git repositories etc.

To add additional software packages to the host or Live environment, modify
the `package_deps` list.

To add additional software packages to the build dependencies, modify the
`build_deps` list.

To clone and install from additional git repositories, extend the `git_deps`
table. Each entry is a 3-tuple (GIT URL, BRANCH, INSTALL COMMAND).

If running anaconda manually, consider using the unshare program with the
arguments "--mount --propagate private" to prevent anaconda mount operations
affecting the root namespace (may prevent unmounting and erasing the Stratis
pool when carrying out repeated installations, see comments in
`_dir_install()`).

