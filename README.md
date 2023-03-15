F37 Stratis rootfs with stratify.py
===================================

  0. Versions & Changes
  1. Overview & Requirements
  2. Configuring virtual machines
  3. Enable sshd (optional)
  4. Download stratify.py
  5. Installation using Live media
  6. Installation using host system
  7. If something goes wrong
  8. stratify.py options
  9. Hacking stratify.py

# 0. Versions & Changes

The script is tested with the current released Fedora media (currently Fedora
37). The script may work with older releases but these are not routinely
tested. In particular releases that ship with Stratis versions prior to 2.4.0
do not include packaged support for stratis as the root file system: it is
necessary to use the `--git` option on these releases to build Stratis from
source.

Due to the overheads of running both the graphical Live media environment and
the Anaconda installer the minimum recommended guest memory for Live media
installations is now 3GiB.


# 1. Overview & Requirements
----------------------------

tl;dr: run `stratify --text --target vda --kickstart /root/ks.cfg` in a root
terminal on a live VM to install a system with Stratis as the root file
system.

To create virtual machines with a Stratis root file system using `stratify.py`
you will need:
 
* The URL for the `stratify.py` script
* An `x86_64` virtual machine using BIOS or EFI firmware and running Fedora 37,
  either:
   * A VM running the F37 Workstation Live media (recommended)
   * A VM installed with any F37 media with additional storage for Stratis
* (Optional) a kickstart file to automate installation settings

The script can be run in either a live environment using the Fedora Workstation
Live ISO image, or in a "host" virtual machine previously installed with Fedora
37 and configured with additional storage for a stratis root file system to be
installed.

The quickest method is to use the Live media, since this does not require an
instllation to be carried out before starting.

Using the Workstation live media does not affect the installed system: the
installation uses whatever Fedora variant is specified in the `--repo` argument
to `stratify.py` (or the repo command in the kickstart file if given).

A kickstart file can be given on the command line to make the installation
fully automatic. An example is available at [1].


# 2. Configuring virtual machines
---------------------------------

# 2.1 Configuring the live environment
--------------------------------------

* Create a new virtual machine instance using the Fedora Workstation 37 Live
  image.

* Allocate at least 10GiB of storage as a single VirtIO disk (e.g. vda) and
  allow at least 3GiB of guest memory.

* Boot the Live image and wait for the Live desktop to load.

* Open a terminal and run "sudo su -" to gain root privileges.


# 2.2. Configuring a host virtual machine
-----------------------------------------

The host VM's role is to provide a Fedora 37 environment where stratify can
run that provides the ability to install software packages with dnf and to
call the command line anaconda installer program. A minimal install using any
F37 media is acceptable - the host environment is only needed for the duration
of the installation.

* Boot the host VM with the installation media and any kickstart or other
options.

* The guest should have sufficient storage for the host install and
will require one additional disk of at least 10GiB for the Stratis root
install.

* The additional storage can either be ignored during the initial host
installation (using manual partitioning) or it can be added to the guest after
the initial host installation has been carried out.

* Set a root password and allow the installation to complete normally.

* Boot the VM and log in to the root account.


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

This step is automated when using the provided bootstrap.sh script (4.1).


# 4. Download stratify.py
-------------------------

The stratify script can be downloaded manually from GitLab or installed
automatically using the bootstrap.sh script.


# 4.1 Automatic download with bootstrap.sh
------------------------------------------

The bootstrap script will configure the environment to allow root login over
ssh using a well-known password ("redhat") and download the python script and
optional kickstart file:

```
# curl --insecure https://gitlab.cee.redhat.com/breeves/stratify/-/raw/main/bootstrap.sh | sh
Enabling ssh root login with password...
Changing password for user root.
passwd: all authentication tokens updated successfully.
Starting ssh daemon...
Downloading stratify.py...
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 32606  100 32606    0     0  60210      0 --:--:-- --:--:-- --:--:-- 60269
Downloading ks.cfg...
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   803  100   803    0     0   1938      0 --:--:-- --:--:-- --:--:--  1934

Host IP addresses:
    inet 192.168.122.19/24 brd 192.168.122.255 scope global dynamic noprefixroute enp1s0
```


# 4.2 Manual download with wget or curl
---------------------------------------

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

Assuming that the storage to be used for Stratis is using VirtIO device `vda`,
either in a terminal running in the Live desktop or an ssh terminal run the
following command:

```
# python stratify.py --text --target vda
```

This will download required packages, partition vda and create a boot file
system on `vda1`. A stratis pool named `p1` and a file system named `fs1` will
be created and mounted at `/mnt/stratisroot`.

Stratify will then run the anaconda installer. A kickstart file may be given by
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
# python stratify.py --text --target vdb
```

This will download required packages, partition `vda` and create a `/boot` file
system on vda1. A stratis pool named `p1` and a file system named `fs1` will be
created and mounted at `/mnt/stratisroot`.

Stratify will then run the anaconda installer. A kickstart file may be given
by passing `--kickstart /root/ks.cfg` (the path must be absolute).

One the system has been installed hit "enter" and the script will install
stratis with root file system support either from the distribution repositories
or by building from the upstream source repositories if `--git` is given.

Once the script logs "Stratis root fs installation complete." the target
system is fully installed and unmounted and the system can be safely rebooted.

Before the Stratis system can be booted the VM must be reconfigured to boot
from the device given to `--target` in order to use the correct bootloader.

The first boot entry will correspond to the Stratis installation but the grub
menu will also include entries to allow booting the original host installation
(the Stratis entry should be the default).

# 7 If something goes wrong
---------------------------

If the installation fails (e.g. due to a kickstart error or anaconda crash) use
`--wipe` to erase the disk contents before repeating.

The disk partitioning and file system creation can be skipped by using
`--nopartition`. This assumes a partition layout appropriate to the system
firmware exists and that the device contains a pool and file system with the
expected names.

## 7.1 Rescuing a stratis system with stratify
----------------------------------------------

If a Stratis root file system installation fails to boot the stratify script
can be used to install dependencies and re-create the chroot layout for
debugging purposes.

As with installation this can be done from either a host system installed
with Fedora 37, or from the Fedora 37 Live Media.

To rescue a system, start the system and download `stratify.py` and then as
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

Fedora 37 Stratis Root Install Script

optional arguments:
  -h, --help            show this help message and exit
  -d TARGET, --target TARGET
                        Specify the device to use
  -b, --bios            Assume thesystem is using BIOS firmware
  -c, --cleanup         Clean up and unmount a rescue chroot
  -e, --efi             Assue the system is using EFI firmware
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
most of the high level logic is driven directly from the `main()` function using
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

