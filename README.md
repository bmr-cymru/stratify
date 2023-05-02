F38 Stratis rootfs with stratify.py
===================================

  0. [Versions & Changes](https://github.com/bmr-cymru/stratify#0-versions--changes)
  1. [Overview & Requirements](https://github.com/bmr-cymru/stratify#1-overview--requirements)
  2. [Configuring virtual machines](https://github.com/bmr-cymru/stratify#2-configuring-virtual-machines)
      1. [Configuring the Live environment](https://github.com/bmr-cymru/stratify#21-configuring-the-live-environment)
      2. [Configuring a host virtual machine](https://github.com/bmr-cymru/stratify#22-configuring-a-host-virtual-machine)
  3. [Enable sshd (optional)](https://github.com/bmr-cymru/stratify#3-enable-sshd-optional)
  4. [Download stratify.py](https://github.com/bmr-cymru/stratify#4-download-stratifypy)
      1. [Automatic download with bootstrap.sh](https://github.com/bmr-cymru/stratify#41-automatic-download-with-bootstrapsh)
      2. [Manual download with wget or curl](https://github.com/bmr-cymru/stratify#42-manual-download-with-wget-or-curl)
  5. [Installation using Live media](https://github.com/bmr-cymru/stratify#5-installation-using-live-media)
  6. [Installation using host system](https://github.com/bmr-cymru/stratify#6-installation-using-host-system)
  7. [If something goes wrong](https://github.com/bmr-cymru/stratify#7-if-something-goes-wrong)
  8. [stratify.py options](https://github.com/bmr-cymru/stratify#8-stratifypy-options)
  9. [Hacking stratify.py](https://github.com/bmr-cymru/stratify#9-hacking-stratifypy)
 10. [References & Links](https://github.com/bmr-cymru/stratify#10-references--links)

# 0. Versions & Changes

This script allows users to easily deploy systems with [Stratis][4] as the root
file system.

The script is tested with the current released Fedora media (currently Fedora
38). The script may work with older releases but these are not routinely
tested. In particular releases that ship with Stratis versions prior to 2.4.0
do not include packaged support for stratis as the root file system: it is
necessary to use the `--git` option on these releases to build Stratis from
source.

Due to the overheads of running both the graphical Live media environment and
the Anaconda installer the minimum recommended guest memory for Live media
installations is now 3GiB.


# 1. Overview & Requirements
----------------------------

tl;dr: run `python stratify.py --target vda --kickstart /root/ks.cfg` in a root
terminal on a live VM to install a system with Stratis as the root file system.

To create virtual machines with a Stratis root file system using `stratify.py`
you will need:
 
* The `stratify.py` script or the URL of the `bootstrap.sh` script
* An `x86_64` virtual machine using BIOS or EFI firmware and running Fedora 38,
  either:
   * A VM running the F38 Workstation Live media (recommended)
   * A VM installed with any F38 media with additional storage for Stratis
* Sufficient storage available to the VM to contain the Stratis installation
* A kickstart file to set installation options

The script can be run in either a live environment using the Fedora Workstation
Live ISO image, or in a "host" virtual machine previously installed with Fedora
and configured with an additional storage device for a stratis root file system
to be installed to.

The quickest method is to use the Live media since this does not require an
installation to be carried out before starting.

By default `stratify.py` will install from the current Fedora Server package
repository. This can be overridden by provising a repo URL with `--repo`.

A kickstart file must be given on the command line to configure the
installation, including the root password. An [example][1] is available in the
Stratify repository.


# 2. Configuring virtual machines
---------------------------------

# 2.1. Configuring the live environment
--------------------------------------

* Create a new virtual machine instance using the Fedora Workstation 38 Live
  image.

* Allocate at least 10GiB of storage as a single VirtIO disk (e.g. vda) and
  allow at least 3GiB of guest memory.

* Boot the Live image and wait for the Live desktop to load.

* Open a terminal and run `su -` to gain root privileges.


# 2.2. Configuring a host virtual machine
-----------------------------------------

The host VM's role is to provide a Fedora environment where `stratify.py` can
run that has the ability to install necessary software packages from the Fedora
repos with dnf and to call the command line anaconda installer program. A
minimal install using any F38 media is acceptable - the host environment is only
needed for the duration of the installation. This option is suitable for running
`stratify.py` in "headless" environments using only the console or SSH to
interact with the system.

* Boot the host VM with the installation media and any kickstart or other
  options.

* The guest should have sufficient storage for the host install and will
  require one additional disk of at least 10GiB for the Stratis root install.
  The target device must be separate from the disk containing the host
  installation as it will be re-partitioned during the installation.

* The additional storage can either be ignored during the initial host
  installation (using manual partitioning) or it can be added to the guest
  after the initial host installation has been carried out.

* Set a root password and allow the installation to complete normally.

* Boot the VM and log in to the root account.


# 3. Enable sshd (optional)
---------------------------

Optionally enable the sshd daemon for root logins with a password, either in
the installer/kickstart script, or by executing the following commands:

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

Download the [Stratify script][3] using wget or curl:

```
# wget https://raw.githubusercontent.com/bmr-cymru/stratify/main/stratify.py
```

or:

```
# curl -o stratify.py https://raw.githubusercontent.com/bmr-cymru/stratify/main/stratify.py
```

Download the [example kickstart][1]:

```
# wget https://raw.githubusercontent.com/bmr-cymru/stratify/main/ks.cfg
```

or

```
# curl -o ks.cfg https://raw.githubusercontent.com/bmr-cymru/stratify/main/ks.cfg
```

The [kickstart file][2] contains a hashed password for the root user: to
generate a hash for a new password use the openssl passwd command:

```
$ openssl passwd -6 "password"
$6$VvxJNYbsqtX66EjI$24HCGhwKOn8lkNMxglZZb90utAc66Jgy3oM6T5DhIdErbpElbviCyikPpRpmERG69O/SyVpZ9YPRuaM22A52G.
```
And then edit the kickstart file to set the new password value.


# 5. Installation using Live media
----------------------------------

Assuming that the storage to be used for Stratis is using VirtIO device `vda`,
either in a terminal running in the Live desktop or an ssh terminal run the
following command:

```
# python stratify.py --target vda --kickstart /root/ks.cfg
```

This will download required packages, partition vda and create a boot file
system on `vda1`. A stratis pool named `p1` and a file system named `fs1` will
be created and mounted at `/mnt/stratisroot`.

Stratify will then run the anaconda installer. A kickstart file must be given by
passing `--kickstart /root/ks.cfg` (the path must be absolute).

Once the system has been installed the script will install packages required
for stratis root file system support from the distribution repositories.

If the `--git` option is given then the script will install build dependencies,
clone the stratis git repositories and initiate a build.

Once the build is complete the script configures grub2 and creates a boot entry
for the Stratis system.

Once the script logs "Stratis root fs installation complete." the target system
is fully installed and unmounted and the system can be safely rebooted.  The
only boot entry in the grub menu corresponds to the Stratis installation.


# 6. Installation using host system
-----------------------------------

Assuming that the system has been installed to VirtIO device `vda`, and that
the storage available for Stratis to use is on VirtIO device `vdb`, run the
following command:

```
# python stratify.py --target vdb --kickstart /root/ks.cfg
```

This will download required packages, partition `vdb` and create a `/boot` file
system on vdb1. A stratis pool named `p1` and a file system named `fs1` will be
created and mounted at `/mnt/stratisroot`.

Stratify will then run the anaconda installer. A kickstart file must be given by
passing `--kickstart /root/ks.cfg` (the path must be absolute).

Once the system has been installed the script will install packages required
for stratis root file system support from the distribution repositories.

If the `--git` option is given then the script will install build dependencies,
clone the stratis git repositories and initiate a build.

Once the build is complete the script configures grub2 and creates a boot entry
for the Stratis system.

Once the script logs "Stratis root fs installation complete." the target system
is fully installed and unmounted and the system can be safely rebooted.

Before the Stratis system can be booted the VM must be reconfigured to boot
from the device given to `--target` in order to use the correct bootloader.


# 7. If something goes wrong
---------------------------

If the installation fails use `--wipe` to erase the disk contents before
repeating.

The disk partitioning and file system creation can be skipped by using
`--nopartition`. This assumes a partition layout appropriate to the system
firmware exists and that the device contains a pool and file system with the
expected names: pool `p1` and root file system `fs1`.


## 7.1. Rescuing a stratis system with stratify
----------------------------------------------

If a Stratis root file system installation fails to boot the `stratify.py`
script can be used to install dependencies and re-create the chroot layout for
debugging purposes.

As with installation this can be done from either a host system installed with
Fedora 38, or from the Fedora 38 Live Media.

To rescue a system, start the system and download `stratify.py` and then as
root run run:

```
# python stratify.py --target <device> --rescue
```

This will mount the file systems from the target device and set up the chroot
before starting a shell in the stratis rootfs system.

Exiting the shell will tear down the chroot and leave the system ready to
reboot.

To clean up chroot mounts left by a failed installation use `--cleanup`:

```
# python stratify.py --target <device> --cleanup
```

# 8. stratify.py options
------------------------

```
usage: stratify.py [-h] [-d TARGET] [-b] [-c] [-e] [-f FS_NAME] [-g] [-k KICKSTART] [-m] [-n] [-p POOL_NAME] [-r] [--repo REPO] [-s SYS_ROOT] [-w]

Fedora 38 Stratis Root Install Script

options:
  -h, --help            show this help message and exit
  -d TARGET, --target TARGET
                        Specify the device to use
  -b, --bios            Assume thesystem is using BIOS firmware
  -c, --cleanup         Clean up and unmount a rescue chroot
  -e, --efi             Assue the system is using EFI firmware
  -f FS_NAME, --fs-name FS_NAME
                        Set the file system name
  -g, --git             Perform a build from git master branch instead of packages
  -k KICKSTART, --kickstart KICKSTART
                        Path to a local kickstart file
  -m, --mbr             Use MBR disk labels
  -n, --nopartition     Do not partition disks or create Stratis fs
  -p POOL_NAME, --pool-name POOL_NAME
                        Set the pool name
  -r, --rescue          Rescue a Stratis root installation.
  --repo REPO           Set the repository URL to use for the installation
  -s SYS_ROOT, --sys-root SYS_ROOT
                        Set the path to the system root directory
  -w, --wipe            Wipe all devices before initialising
```

# 9. Hacking stratify.py
-----------------------

The script is very simple and should be easy to modify for local requirements:
most of the high level logic is driven directly from the `main()` function
using helper functions to install software, clone git repositories etc.

To add additional software packages to the host or Live environment, modify the
`package_deps` list.

To add additional software packages to the build dependencies, modify the
`build_deps` list.

To clone and install from additional git repositories, extend the `git_deps`
table. Each entry is a 3-tuple (GIT URL, BRANCH, [BUILD, AND INSTALL
COMMANDS]).

If running anaconda manually, consider using the unshare program with the
arguments "--mount --propagate private" to prevent anaconda mount operations
affecting the root namespace (this may prevent unmounting and erasing the
Stratis pool when carrying out repeated installations, see comments in
`_dir_install()`).

# 10. References & Links

* [Stratis project][4]
* [stratify.py script][3]
* [bootstrap script][2]
* [example kickstart][1]

[1]: https://raw.githubusercontent.com/bmr-cymru/stratify/main/ks.cfg
[2]: https://raw.githubusercontent.com/bmr-cymru/stratify/main/bootstrap.sh
[3]: https://raw.githubusercontent.com/bmr-cymru/stratify/main/stratify.py
[4]: https://stratis-storage.github.io/
