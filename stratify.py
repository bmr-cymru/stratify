#!/usr/bin/python

from subprocess import run as run
from sys import exit, argv
from argparse import ArgumentParser
from os.path import basename, join, exists, isabs
from os import mkdir, chmod, chroot, chdir, listdir, unlink, symlink, fdatasync
import traceback
import logging

_version = "0.7"
_date = "2023-03-03"

_debug = False

# Default Stratis object names
pool_name = "p1"
fs_name = "fs1"

# Default Fedora repository URL
repo = "https://mirrors.mit.edu/fedora/linux/releases/37/Server/x86_64/os/"

# Default location of the target system root directory
sys_root = "/mnt/stratisroot"

# Path to the fstab
etc_fstab = "etc/fstab"

# Default size of the /boot/efi partition
EFI_PART_SIZE = 600

# Default size of the /boot partition
BOOT_PART_SIZE = 1000

# Packages needed in the live host
package_deps = [
    "git",
    "anaconda",
    "stratisd",
    "stratis-cli",
    "vim-enhanced"
]

# Packages needed to build from git
# Package list taken from dkeefe's script
build_deps = [
    "asciidoc",
    "cargo",
    "clang",
    "cryptsetup-devel",
    "cryptsetup-libs",
    "dbus-devel",
    "dbus-devel.i686",
    "dbus-devel.x86_64",
    "dbus-glib-devel",
    "dbus-python-devel",
    "device-mapper-devel",
    "device-mapper-persistent-data",
    "gcc",
    "git",
    "glibc-devel.i686",
    "glibc-devel.x86_64",
    "keyutils",
    "libblkid-devel",
    "llvm",
    "llvm-devel",
    "make",
    "openssl-devel",
    "python3-coverage",
    "python3-dateutil",
    "python3-dbus-client-gen",
    "python3-dbus-python-client-gen",
    "python3-devel",
    "python3-justbytes",
    "python3-psutil",
    "python3-pyparsing",
    "python3-pytest.noarch",
    "python3-pyudev",
    "python3-semantic_version",
    "python3-setuptools",
    "python3-wcwidth",
    "rpm-build",
    "rpmdevtools",
    "rust",
    # "rust-toolset",
    "systemd-devel",
    "systemd-devel.x86_64",
    "xfsprogs",
    "python3-dbus",
    "clevis-luks"
]

boot_deps = [
    "boom-boot"
]

boot_deps_pc = [
    "grub2-pc",
    "grub2-pc-modules",
]

boot_deps_efi = [
    "shim-x64",
    "grub2-efi-x64",
    "grub2-efi-x64-modules",
    "shim-ia32",
    "grub2-efi-ia32",
    "grub2-efi-ia32-modules",
    "grub2-tools-efi"
]

# Packages that must be built from a git repository. Each entry is a 3-tuple:
# (CLONE_URL, BRANCH, INSTALL_CMD).
git_deps = [
    ("https://github.com/stratis-storage/stratisd",
     "master", "make install"),
    ("https://github.com/stratis-storage/stratis-cli",
     "master", "python setup.py install")
]

chroot_bind_mounts = [
    "dev",
    "proc",
    "run",
    "sys"
]

enable_units = [
    "stratisd.service"
]

# Module logging configuration
_log = logging.getLogger(__name__)

_log_debug = _log.debug
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error


def fail(rc):
    if _debug:
        traceback.print_stack()
    exit(rc)


def whole_disk(name):
    """Return ``True`` if the string ``dev`` corresponds to a whole disk
    device, or ``False`` otherwise.
    """
    if name.startswith("vd") or name.startswith("sd"):
        return not name[-1].isdigit()
    if name.startswith("mpath"):
        return not name[name.rindex('p') + 1].isdigit()


def filter_device(name):
    """Return ``True`` if ``name`` matches the list of allowed device
    name prefixes, or ``False`` otherwise.
    """
    # Allowed device name prefixes
    dev_filter = ["sd", "vd", "mpath"]
    for df in dev_filter:
        if name.startswith(df):
            return True
    return False


def get_devices():
    """Return a list of block devices obtained from lsblk, filtered
    for allowed device name prefixes.
    """
    dev_cmd = ["lsblk", "--list", "--noheadings", "--output", "name"]
    dev_output = run(dev_cmd, capture_output=True).stdout.decode('utf8')
    dev_list = dev_output.strip().splitlines()
    return [d for d in dev_list if filter_device(d)]


def get_partitions(name):
    """Return a list of partition device names.
    """
    all_devs = get_devices()
    parts = [d for d in all_devs if d.startswith(name) and d != name]
    return parts


def get_partition_device(name, partnum):
    """Format a device name with a partition number according to the
    convention for the corresponding device type.
    """
    if name.startswith("mpath"):
        return "%sp%d" % (name, partnum)
    else:
        return "%s%d" % (name, partnum)


def _next_device(name, parts):
    """Return the next partition available from the list ``parts``.
    """
    return get_partition_device(name, parts.pop())


def get_efi_device(name, parts):
    """Allocate a partition name to use for the /boot/efi file system.
    """
    return _next_device(name, parts)


def get_boot_device(name, parts):
    """Allocate a partition name to use for the /boot file system.
    """
    return _next_device(name, parts)


def get_stratis_device(name, parts):
    """Allocate a partition name to use for the Stratis pool.
    """
    return _next_device(name, parts)


def check_target(target):
    """Check that the given --target device exists and is a whole-disk
    device.
    """
    all_devs = get_devices()
    if target not in all_devs:
        _log_error("Target device not found: %s" % target)
        fail(1)
    if not whole_disk(target):
        _log_error("Expected whole disk device for --target: %s" % target)
        fail(1)
    return True


def install_deps(deps, deptype, chroot=None):
    """Install the list of package dependencies given in ``deps`` in either
    the host system or the chroot using dnf.
    """
    _log_info("Installing %s dependencies%s" %
              (deptype, " in chroot" if chroot else ""))
    _log_debug("Package list: %s", ", ".join(deps))
    pkg_cmd = ["dnf", "-y", "install"]
    pkg_cmd.extend(deps)
    if not chroot:
        pkg_run = run(pkg_cmd)
    else:
        pkg_run = runat(pkg_cmd, chroot, "/")
    if pkg_run.returncode != 0:
        _log_error("Failed to install packages")
        fail(1)


def mount(what, where, options=None, bind=False, fstype=None):
    """Mount ``what`` onto ``where``, optionally passing ``options`` to
    the mount program, and creating a bind mount if ``bind`` is ``True``.
    """
    mount_cmd = ["mount"]
    if bind:
        mount_cmd.extend(["--bind"])
    if fstype:
        mount_cmd.extend(["-t", fstype])
    if options:
        mount_cmd.extend(["-o", options])
    mount_cmd.extend([what, where])
    _log_debug("Invoking mount command: %s" % " ".join(mount_cmd))
    mount_run = run(mount_cmd)
    if mount_run.returncode != 0:
        _log_error("Failed to mount '%s' on '%s'" % (what, where))
        fail(1)


def umount(where, check=True):
    """Unmount a device or file system mount point. If ``check`` is not
    ``True`` ignore errors returned by the mount program.
    """
    umount_cmd = ["umount", where]
    _log_debug("Invoking umount command: %s" % " ".join(umount_cmd))
    umount_run = run(umount_cmd)
    if check and umount_run.returncode != 0:
        _log_error("Failed to umount '%s'" % where)
        fail(1)


def wipe_device(name):
    """Overwrite disk label (MBR or GPT) on device ``name``.
    """
    wipefs_cmd = ["wipefs", "-a", "/dev/%s" % name]
    wipefs_run = run(wipefs_cmd)
    if wipefs_run.returncode != 0:
        _log_error("Failed to wipe disk labels from '%s'" % name)


def mk_parttable(name, mbr=False):
    """Create a partition table on device ``name``. A GPT partition table is
    created unless the ``mbr`` argument is ``True``.
    """
    part_cmd = ["fdisk", "/dev/%s" % name]
    part_input = ("%s\nw\n" % 'o' if mbr else 'g').encode('utf8')
    part_run = run(part_cmd, input=part_input)
    if part_run.returncode != 0:
        _log_error("Could not create %s disk label on '%s'" %
                   ("GPT" if gpt else "MBR", name))
        fail(1)


def mk_partitions(name, sizes):
    """Create up to four primary partitions on the device named ``name``.
    This function assumes the device is unpartitioned. Partition sizes
    are specified in order of increasing partition number in the
    ``sizes`` list. A size value of 0 may be specified indicating that
    the corresponding partition should occupy all remaining space (no
    further entries will be processed).
    """
    part_cmd = ["fdisk", "/dev/%s" % name]
    if len(sizes) > 4:
        _log_warn("mk_partitions() supports at most 4 partitions per disk.")
        sizes = sizes[0:3]
    for size in sizes:
        psize = ("+%dm" % size) if size > 0 else ""
        part_input = ("n\np\n\n\n%s\nw\n" % psize).encode('utf8')
        part_run = run(part_cmd, input=part_input)
        if part_run.returncode != 0:
            _log_error("Failed to create partition on '%s' (size=%s)" %
                       (name, size))
            fail(1)
        if size == 0:
            break


def mkfs_xfs(device):
    """Create an XFS file system on ``device`` with the default options.
    """
    mkfs_cmd = ["mkfs.xfs", "/dev/%s" % device]
    mkfs_run = run(mkfs_cmd)
    if mkfs_run.returncode != 0:
        _log_error("Failed to create XFS file system on '%s'" % device)


def mkfs_vfat(device):
    """Create a VFAT file system on ``device`` with the default options.
    """
    mkfs_cmd = ["mkfs.vfat", "/dev/%s" % device]
    mkfs_run = run(mkfs_cmd)
    if mkfs_run.returncode != 0:
        _log_error("Failed to create VFAT file system on '%s'" % device)


def create_pool(name, devices):
    """Create a stratis pool named ``name`` on the list of devices
    given in ``devices``.
    """
    pool_cmd = ["stratis", "pool", "create", name]
    pool_cmd.extend(["/dev/%s" % d for d in devices])
    pool_run = run(pool_cmd)
    if pool_run.returncode != 0:
        _log_error("Failed to create pool '%s' on %s" %
                   (name, ",".join(devices)))
        fail(1)


def create_fs(pool, name):
    """Create a stratis file system named ``name`` in ``pool``.
    """
    fs_cmd = ["stratis", "fs", "create", pool, name]
    fs_run = run(fs_cmd)
    if fs_run.returncode != 0:
        _log_error("Failed to create fs '%s' on pool '%s'" % (name, pool))
        fail(1)


def dir_install(dest_dir, repo_url, text=False, kickstart=None):
    """Run an anaconda --dirinstall to the partition layout configured
    in ``dest_dir`` from the repository at ``repo_url`` and optionally
    using the local kickstart file at the absolute path ``kickstart``.

    Force Anaconda to start in text mode if ``text`` is ``True``.
    """

    # Run anaconda in its own namespace, see lorax:src/pylorax/installer.py
    # Use --propagation private to avoid anaconda's mount of /mnt/sysroot
    # propagating to our namespace.
    #
    # If anaconda is run without unsharing the namespace the mount operations
    # performed in pyanaconda.core.utils.set_system_root() at the end of the
    # installation may leave inaccessible mounts behind that are difficult to
    # clean up (and that prevent erasing the stratis pools to re-use the
    # devices).
    unshare_cmd = [
            "unshare", "--pid", "--kill-child", "--mount",
            "--propagation", "private"
    ]
    install_cmd = ["anaconda", "--dirinstall", dest_dir, "--repo", repo_url]
    if text:
        install_cmd.append("--text")
    if kickstart:
        install_cmd.extend(["--kickstart", kickstart])
        cmd_input = "\n".encode('utf8')
    else:
        cmd_input = None

    _log_info("Running anaconda: %s" % " ".join(install_cmd))
    install_run = run(unshare_cmd + install_cmd, input=cmd_input)
    if install_run.returncode != 0:
        _log_error("Anaconda installation failed: %s" % install_run.returncode)
        fail(1)
    if cmd_input:
        print()


def stratisd_running():
    """Test whether the stratis daemon is running.
    """
    systemctl_cmd = ["systemctl", "status", "stratisd"]
    systemctl_run = run(systemctl_cmd, capture_output=True)
    if systemctl_run.returncode == 0:
        return True
    return False


def destroy_pools():
    """Attempt to destroy all stratis file systems and pools.
    """
    if not stratisd_running():
        start_stratisd()

    # First destroy each file system
    fs_cmd = ["stratis", "fs"]
    fs_list_cmd = fs_cmd + ["list"]
    fs_list_out = run(fs_list_cmd, capture_output=True).stdout.decode('utf8')
    for line in fs_list_out.splitlines():
        if line.startswith("Pool"):
            continue
        (pool, name, rest) = line.split(maxsplit=2)
        _log_warn("Destroying file system %s in pool %s" % (name, pool))
        umount("/dev/stratis/%s/%s" % (pool, name), check=False)
        fs_dest_cmd = fs_cmd + ["destroy", pool, name]
        fs_dest_run = run(fs_dest_cmd)
        if fs_dest_run.returncode != 0:
            _log_error("Failed to destroy file system %s in pool %s" %
                       (name, pool))
            fail(1)

    pool_cmd = ["stratis", "pool"]
    list_cmd = pool_cmd + ["list"]
    list_out = run(list_cmd, capture_output=True).stdout.decode('utf8')
    for line in list_out.splitlines():
        if line.startswith("Name"):
            continue
        (name, rest) = line.split(maxsplit=1)
        _log_warn("Destroying pool %s" % name)
        dest_cmd = pool_cmd + ["destroy", name]
        dest_run = run(dest_cmd)
        if dest_run.returncode != 0:
            _log_error("Failed to destroy pool %s" % name)
            fail(1)


def start_stratisd():
    """Attempt to start stratisd using systemctl.
    """
    systemctl_cmd = ["systemctl", "start", "stratisd"]
    systemctl_run = run(systemctl_cmd)
    if systemctl_run.returncode != 0:
        _log_error("Failed to start stratisd")
        fail(1)


def stop_stratisd():
    """Attempt to stop stratisd using systemctl.
    """
    # The daemon may or may not be running, depending on system state,
    # but systemctl stop always returns 0 in any case.
    systemctl_cmd = ["systemctl", "stop", "stratisd"]
    systemctl_run = run(systemctl_cmd)


def udevadm_settle():
    """Call the ``udevadm settle`` command and wait for it to return.
    """
    udev_cmd = ["udevadm", "settle"]
    udev_run = run(udev_cmd)
    if udev_run.returncode != 0:
        _log_error("Failed to wait for udev events to complete")
        fail(1)


def wipe_partitions(target):
    """Wipe all partitions and the whole disk device ``target``.
    """
    parts = get_partitions(target)
    if parts:
        _log_warn("Wiping partitions on device %s" % target)
        for part in parts:
            _log_warn("Wiping partition %s" % part)
            wipe_device(part)

    _log_warn("Wiping device %s" % target)
    wipe_device(target)


def create_partitions(target, mbr=False, efi=False):
    """Create a default partition layout on ``target``.
    """
    _log_info("Creating partition table on %s" % target)
    mk_parttable(target, mbr=mbr)

    part_sizes = [EFI_PART_SIZE] if efi else []
    part_sizes.extend([BOOT_PART_SIZE, 0])
    _log_info("Partitioning target device %s %s" % (target, part_sizes))
    mk_partitions(target, part_sizes)


def mount_stratis_root(pool, fs, root):
    """Mount the stratis root file system ``pool`/``fs`` at ``root``.
    """
    if not exists(root):
        mkdir(root)
    _log_info("Mounting %s/%s on %s" % (pool, fs, root))
    mount("/dev/stratis/%s/%s" % (pool, fs), root)


def mount_boot(boot_dev, root):
    """Mount the /boot file system on ``boot_dev`` at ``root``/boot.
    """
    boot_path = join(root, "boot")
    try:
        mkdir(boot_path)
    except OSError:
        pass

    _log_info("Mounting %s on %s" % (boot_dev, boot_path))
    mount("/dev/%s" % boot_dev, boot_path)
    chmod(boot_path, 0o555)


def mount_boot_efi(efi_dev, root):
    """Mount the /boot/efi file system on ``efi_dev`` at ``root``/boot/efi.
    """
    efi_path = join(root, "boot", "efi")
    try:
        mkdir(efi_path)
    except OSError:
        pass

    _log_info("Mounting %s on %s" % (efi_dev, efi_path))
    mount("/dev/%s" % efi_dev, efi_path)
    chmod(efi_path, 0o700)


def prepare_chroot(root, bind_mounts):
    """Create bind mounts for the chroot environment for the mount
    points specified in ``bind_mounts``, and mount selinuxfs at
    sys/fs/selinux.
    """
    _log_info("Creating bind mounts in chroot %s (%s)" % (root, bind_mounts))
    for mnt in bind_mounts:
        mount(join("/", mnt), join(root, mnt), bind=True)

    selinux_path = join(root, "sys/fs/selinux")
    _log_info("Mounting selinuxfs at %s" % selinux_path)
    mount("none", selinux_path, fstype="selinuxfs")


def teardown_chroot(root, bind_mounts):
    """Unmount selinuxfs and remove bind mounts specified in ``bind_mounts``
    from the chroot environment at ``root``.
    """
    selinux_path = join(root, "sys/fs/selinux")
    _log_info("Unmounting selinuxfs at %s" % selinux_path)
    umount(selinux_path)

    _log_info("Removing bind mounts from chroot %s (%s)" % (root, bind_mounts))
    for mount in bind_mounts:
        umount(join(root, mount))


def git_clone(into, url, branch):
    """Clone the git ``url`` and ``branch`` specified into the file system
    path ``into``.
    """
    git_cmd = ["git", "clone", "-b", branch, url]
    git_run = run(git_cmd, cwd=into)
    if git_run.returncode != 0:
        _log_error("Failed to clone git repository %s" % url)
        fail(1)
    # return the repository directory name
    return url.rsplit('/')[-1]


def runat(cmd, root_dir, cwd="/", shell=False):
    """Change root to ``root_dir`` and run ``cmd`` in directory ``cwd``.
    """
    def _chroot_fn():
        chroot(root_dir)
        chdir(cwd)
    return run(cmd, preexec_fn=_chroot_fn, shell=shell)


def install_from_git(root):
    """For each (GIT_URL, BRANCH, INSTALL COMMAND) tuple in ``git_deps``
    clone the repository into ``root``/git/<repository> and execute the
    install command in the chroot.
    """
    git_basedir = join(root, "root", "git")
    git_chrootdir = join("/", "root", "git")
    _log_info("Creating git directory %s" % git_basedir)
    mkdir(git_basedir)
    for git_dep in git_deps:
        _log_info("Cloning git repository %s into %s" %
                  (git_dep[0], git_basedir))
        git_dir = git_clone(git_basedir, git_dep[0], git_dep[1])
        _log_info("Installing from %s (%s)" % (git_dep[1], git_dep[2]))
        build_cmd = git_dep[2].split()
        runat(build_cmd, root, join(git_chrootdir, git_dir))


def enable_service(root, unit):
    """Enable the systemd service ``unit`` in the chroot layout specified
    by ``root``. The given ``unit`` must be present in the systemd path
    `/usr/lib/systemd/system`.
    """
    _log_info("Enabling unit=%s for sysinit.target.wants in %s" %
              (unit, root))
    etc_path = "/etc/systemd/system/sysinit.target.wants"
    usr_path = "/usr/lib/systemd/system"
    if not exists(join(root, usr_path[1:])):
        _log_warn("systemd unit path %s not found in %s" % (usr_path, root))
    if not exists(join(root, etc_path[1:])):
        _log_error("systemd target directory %s not found in %s" %
                   (etc_path, root))
        fail(1)
    etc_path = join(etc_path, unit)
    usr_path = join(usr_path, unit)
    symlink(usr_path, join(root, etc_path[1:]))


def write_fstab(root, pool, fs, boot_dev, swap_dev=None):
    """Write an fstab for stratis root to the root file system at ``root``,
    using the stratis ``pool`` and ``fs``, ``boot_dev`` and optionally
    ``swap_dev``.
    """
    root_entry = "/dev/stratis/%s/%s / xfs defaults 0 1" % (pool, fs)
    boot_entry = "/dev/%s /boot xfs defaults 0 2" % boot_dev
    if swap_dev:
        swap_entry = "/dev/%s none swap defaults 0 0"
    else:
        swap_entry = ""
    fstab_path = join(root, etc_fstab)
    with open(fstab_path, "w") as fstab:
        fstab.write(root_entry + "\n")
        fstab.write(boot_entry + "\n")
        if swap_entry:
            fstab.write(swap_entry)
        fstab.flush()
        fdatasync(fstab.fileno())


def mk_dracut_initramfs(root):
    """Create a dracut initramfs for the kernel installed in the chroot.
    """
    dracut_cmd = ["dracut", "--force", "--verbose"]
    _log_info("Creating dracut initramfs")
    dracut_run = runat(dracut_cmd, root, "/")
    if dracut_run.returncode != 0:
        _log_error("Failed to generate initramfs")
        fail(1)


def install_bootloader(root, target):
    """Install and configure the grub2 boot loader in the chroot.
    """
    grub2_install_cmd = ["grub2-install", "/dev/%s" % target]

    grub2_install_run = runat(grub2_install_cmd, root, "/")
    _log_info("Installing grub2 bootloader")
    if grub2_install_run.returncode != 0:
        _log_error("Failed to install boot loader")
        fail(1)


def configure_bootloader(root):
    """Configure the grub2 boot loader in the chroot.
    """
    grub2_mkconfig_cmd = ["grub2-mkconfig > /boot/grub2/grub.cfg"]

    _log_info("Generating grub2 bootloader configuration")
    grub2_mkconfig_run = runat(grub2_mkconfig_cmd, root, "/", shell=True)
    if grub2_mkconfig_run.returncode != 0:
        _log_error("Failed to generate bootloader configuration")
        fail(1)


def get_fs_uuid(device):
    """Return the file system UUID for ``device``, as reported by ``blkid``.
    """
    lsblk_cmd = ["lsblk", "--noheadings", "--fs", "--output", "uuid"]
    lsblk_cmd.extend(["/dev/%s" % device])
    lsblk_run = run(lsblk_cmd, capture_output=True)
    if lsblk_run.returncode != 0:
        _log_error("Failed to get file system UUID for %s" % device)
        fail(1)
    lsblk_out = lsblk_run.stdout.decode('utf8')
    return lsblk_out.strip()


def configure_bootloader_stub(root, boot_dev):
    """Configure the EFI grub.cfg stub to redirect to the configuration
    in /boot/grub2/grub.cfg.
    """
    grub_stub = (
        "search --no-floppy --fs-uuid --set=dev %s\n"
        "set prefix=($dev)/grub2\n"
        "export $prefix\n"
        "configfile $prefix/grub.cfg\n"
    )
    boot_uuid = get_fs_uuid(boot_dev)
    stub_path = join(root, "boot/efi/EFI/fedora/grub.cfg")
    _log_info("Generating grub.cfg EFI stub at %s" % stub_path)
    with open(stub_path, "w") as stub:
        stub.write(grub_stub % boot_uuid)
        stub.flush()
        fdatasync(stub.fileno())


def unlink_bootentries(root):
    """Clean up Anaconda generated boot entries.
    """
    bls_dir = "boot/loader/entries"
    bls_path = join(root, bls_dir)
    for fname in listdir(bls_path):
        if fname.endswith(".conf"):
            unlink(join(bls_path, fname))


def get_stratis_pool_uuid(pool):
    """Return the stratis root fs pool uuid.
    """
    pool_cmd = ["stratis", "pool", "list"]
    pool_out = run(pool_cmd, capture_output=True).stdout.decode('utf8')
    for line in pool_out.splitlines():
        if line.startswith("Name"):
            continue
        fields = line.split()
        if fields[0] == pool:
            return fields[-1]
    _log_error("Failed to get stratis pool uuid")
    fail(1)


def configure_boom(root, pool_uuid):
    """Create a boom OsProfile with the necessary kernel arguments to
    mount the stratis root file system.
    """
    _log_info("Creating boom OsProfile for Stratis boot")
    os_options = "root=%{root_device} ro %{root_opts}"
    os_options += " stratis.rootfs.pool_uuid=%s" % pool_uuid
    boom_cmd = ["boom", "profile", "create", "--from-host"]
    boom_cmd.extend(["--os-options", os_options])
    boom_run = runat(boom_cmd, root, "/")
    if boom_run.returncode != 0:
        _log_error("Failed to create OsProfile")


def create_boot_entry(root, root_dev, title=None):
    """Create a boom boot entry for the stratis root fs.
    """
    _log_info("Creating boom boot entry")
    boom_cmd = ["boom", "create", "--root-device", root_dev]
    if title:
        boom_cmd.extend(["--title", title])
    boom_run = runat(boom_cmd, root, "/")


def restorecon(root, path, recursive=False):
    """Call the ``restorecon`` command to restore SELinux contexts to
    ``path``. If ``root`` is not ``None`` the command is executed using
    this value as the root directory. If ``recursive`` is ``True``
    contexts will be restored recursively beginning at ``path``.
    """
    restorecon_cmd = ["restorecon"]
    if recursive:
        restorecon_cmd.extend(["-R"])
    restorecon_cmd.extend([path])
    restorecon_run = runat(restorecon_cmd, root)
    if restorecon_run.returncode != 0:
        _log_error("Failed to run '%s' in %s" %
                   (" ".join(restorecon_cmd), root))
        fail(1)


def cleanup(root, efi, bind_mounts):
    _log_info("Unmounting %s %s chroot layout" % ("EFI" if efi else "BIOS", root))
    teardown_chroot(root, bind_mounts)
    boot = join(root, "boot")
    if efi:
        boot_efi = join(boot, "efi")
        _log_info("Unmounting %s from %s" % (boot_efi, root))
        umount(boot_efi)
    _log_info("Unmounting %s from %s" % (boot, root))
    umount(boot)
    _log_info("Unmounting %s" % root)
    umount(root)


def is_bios():
    """Return ``True`` if this system is using BIOS firmware or ``False``
    if EFI is present. Assumes x86_64 platform.
    """
    return not exists("/sys/firmware/efi")


def main(argv):
    parser = ArgumentParser(prog=basename(argv[0]), description="Fedora 34 "
                            "Stratis Root Install Script")
    parser.add_argument("-d", "--target", type=str, help="Specify the device "
                        "to use", default="vda")
    parser.add_argument("-b", "--bios", action="store_true", help="Assume the"
                        "system is using BIOS firmware")
    parser.add_argument("-c", "--cleanup", action="store_true", help="Clean "
                        "up and unmount a rescue chroot")
    parser.add_argument("-e", "--efi", action="store_true", help="Assue the"
                        "system is using EFI firmware")
    parser.add_argument("-f", "--fs-name", type=str, help="Set the file "
                        "system name", default=fs_name)
    parser.add_argument("-k", "--kickstart", type=str, help="Path to a local "
                        "kickstart file")
    parser.add_argument("-m", "--mbr", action="store_true", help="Use MBR "
                        "disk labels")
    parser.add_argument("-n", "--nopartition", action="store_true",
                        help="Do not partition disks or create Stratis fs")
    parser.add_argument("-p", "--pool-name", type=str, help="Set the pool "
                        "name", default=pool_name)
    parser.add_argument("-r", "--rescue", action="store_true", help="Rescue "
                        "a Stratis root installation.")
    parser.add_argument("-s", "--sys-root", type=str, help="Set the path to"
                        " the system root directory", default=sys_root)
    parser.add_argument("-t", "--text", action="store_true", help="Use text "
                        "mode for Anaconda")
    parser.add_argument("-w", "--wipe", action="store_true", help="Wipe all "
                        "devices before initialising")
    args = parser.parse_args(argv[1:])

    logging.basicConfig(filename="stratify.log", level=logging.DEBUG,
                        filemode="w", format='%(asctime)s %(message)s')

    default_log_level = logging.INFO
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(default_log_level)
    console_handler.setFormatter(formatter)
    _log.addHandler(console_handler)

    _log_info("stratify.py %s - %s" % (_version, _date))

    if args.rescue or args.cleanup:
        args.nopartition = True

    if args.rescue:
        if args.cleanup:
            _log_error("Cannot use --rescue and --cleanup")
            fail(1)

    if args.wipe:
        if args.rescue or args.cleanup:
            _log_error("Cannot use --wipe with --rescue or --cleanup")
            fail(1)

    if args.wipe and args.nopartition:
        _log_error("Cannot use --wipe with --nopartition")
        fail(1)

    if args.kickstart and not isabs(args.kickstart):
        _log_error("--kickstart argument must be an absolute path")
        fail(1)

    if args.mbr and args.efi:
        _log_error("Cannot use MBR partitions with --efi")
        fail(1)

    if args.bios and args.efi:
        _log_error("Cannot use --bios with --efi")
        fail(1)

    # Install dependencies in the live host
    install_deps(package_deps, "host")

    if not check_target(args.target):
        _log_error("No target device given!")
        fail(1)

    if args.wipe:
        # Remove pre-existing stratis pools
        destroy_pools()

    # Stop the Stratis daemon if it is running so that we can wipe any
    # stale data from the target device.
    stop_stratisd()

    target = args.target
    pool = args.pool_name
    fs = args.fs_name
    root = args.sys_root
    rescue = args.rescue

    if args.bios:
        efi = False
    elif args.efi:
        efi = True
    else:
        efi = not is_bios()

    if args.cleanup:
        cleanup(root, efi, chroot_bind_mounts)
        exit(0)
    else:
        # Clean up any stray boot file system
        umount(join(args.sys_root, "boot"), check=False)

    _log_info("%s for %s" %
              ("Installing" if not rescue else "Rescuing",
               ("EFI" if efi else "BIOS")))

    # Available partition numbers
    parts = list(range(4, 0, -1))

    if efi:
        efi_dev = get_efi_device(target, parts)
        _log_info("Using %s as EFI device" % efi_dev)

    boot_dev = get_boot_device(target, parts)
    _log_info("Using %s as boot device" % boot_dev)

    stratis_dev = get_stratis_device(target, parts)
    _log_info("Using %s as Stratis pool device" % stratis_dev)

    if not args.nopartition:
        if args.wipe:
            wipe_partitions(target)

        create_partitions(target, efi=efi)

        if efi:
            mkfs_vfat(efi_dev)

        mkfs_xfs(boot_dev)

        _log_info("Starting Stratis daemon")
        start_stratisd()

        udevadm_settle()

        _log_info("Creating pool %s with %s" % (pool, stratis_dev))
        create_pool(pool, [stratis_dev])
        _log_info("Creating file system %s in pool %s" % (fs, pool))
        create_fs(pool, fs)
    else:
        _log_info("Starting Stratis daemon")
        start_stratisd()
    udevadm_settle()

    mount_stratis_root(pool, fs, root)
    mount_boot(boot_dev, root)
    if efi:
        mount_boot_efi(efi_dev, root)

    if not rescue:
        # Call Anaconda to create an installation
        dir_install(root, repo, text=args.text, kickstart=args.kickstart)

    prepare_chroot(root, chroot_bind_mounts)

    if rescue:
        _log_info("System chroot is mounted at %s" % root)
        _log_info("Exit the shell to clean up chroot")
        runat(["/bin/bash"], root, cwd="/root", shell=True)
        cleanup(root, efi, chroot_bind_mounts)
        exit(0)

    install_deps(build_deps, "build", chroot=root)

    install_from_git(root)

    for unit in enable_units:
        enable_service(root, unit)

    write_fstab(root, pool, fs, boot_dev)
    mk_dracut_initramfs(root)

    if efi:
        # Install grub2 dependencies for EFI
        install_deps(boot_deps + boot_deps_efi, "boot", chroot=root)
        configure_bootloader_stub(root, boot_dev)
    else:
        # Install grub2 dependencies for PC/BIOS
        install_deps(boot_deps + boot_deps_pc, "boot", chroot=root)
        install_bootloader(root, target)

    configure_bootloader(root)

    _log_info("Removing non-stratis boot entries from %s/boot" % root)
    unlink_bootentries(root)

    stratis_pool_uuid = get_stratis_pool_uuid(pool)
    _log_info("Configuring boom OsProfile for pool_uuid=%s" %
              stratis_pool_uuid)
    configure_boom(root, stratis_pool_uuid)

    _log_info("Creating stratis root fs boot entry")
    create_boot_entry(root, "/dev/stratis/%s/%s" % (pool, fs), title=None)

    _log_info("Restoring SELinux contexts to %s" % join(root, "etc"))
    restorecon(root, "/etc", recursive=True)

    cleanup(root, efi, chroot_bind_mounts)

    _log_info("Stratis root fs installation complete.")

if __name__ == '__main__':
    main(argv)
