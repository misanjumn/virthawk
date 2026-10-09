# 🦅 VirtHawk

> A CLI for libvirt guest diagnostics - inspect all running VMs, vCPUs, memory, disks, networks and snapshots in one command.

[![PyPI version](https://badge.fury.io/py/virthawk.svg)](https://pypi.org/project/virthawk/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🦅 VirtHawk - fast, sharp libvirt guest diagnostics. Pairs with [syshawk](https://github.com/misanjumn/syshawk) for full host + guest visibility.

---

## Install

```bash
pip3 install virthawk
```

Requires `libvirt` to be installed on the host (`libvirt-daemon` or equivalent).

---

## Usage

Both **flag style** and **subcommand style** work identically:

```bash
# Full output - hypervisor header + all guests
virthawk

# Hypervisor info only
virthawk host
virthawk --host

# All guests
virthawk guests
virthawk --guests

# Only running guests
virthawk running
virthawk --running

# Single guest by name
virthawk guest <name>
virthawk --guest <name>

# JSON output
virthawk --json
virthawk json

# Live refresh
virthawk --watch
virthawk --watch --interval 3
virthawk watch

# Remote hypervisor
virthawk --uri qemu+ssh://root@remotehost/system

# Version
virthawk --version
```

---

## Example output

```
🦅 VirtHawk v0.1.0 - libvirt guest diagnostics

  Hypervisor : QEMU 10.0.11  ·  ppc64le
  Libvirt    : 11.4.0
  Host       : kvm-host-01.example.com
  Domains    : 2 running  ·  1 inactive  ·  3 total

  Guest      : guest-web-01
  State      : running
  Virt       : kvm
  Hostname   : guest-web-01  (domain name, agent unavailable)
  UUID       : 4b4b918d-0000-1111-2222-000000000001
  Autostart  : no
  vCPUs      : 32  ·  CPU time: 586.4s
  CPU Model  : POWER11
  Topology   : no pinning
  Memory     : 2.6 GB / 32.0 GB  8.2%
  Disk       : vda       50.0 GB        rd: 48.35 GB   wr: 24.33 GB
               path     /var/lib/libvirt/images/guest-web-01.qcow2
  Network    : vnet0     virtio    bridge: default
               MAC      52:54:00:ab:cd:ef
               IP       192.168.122.101/24
                        ↑ 0.15 MB/s   ↓ 0.69 MB/s
  Snapshots  : 0

  · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·

  Guest      : guest-db-01
  State      : running
  Virt       : kvm
  Hostname   : guest-db-01  (domain name, agent unavailable)
  UUID       : b02474ea-0000-1111-2222-000000000002
  Autostart  : no
  vCPUs      : 8  ·  CPU time: 13213.8s
  CPU Model  : POWER11
  Topology   : no pinning
  Memory     : 12.0 GB / 16.0 GB  75.1%
  Disk       : vda       20.0 GB        rd: 0.28 GB   wr: 7.78 GB
               path     /var/lib/libvirt/images/guest-db-01.qcow2
               sda       11.7 GB        rd: 1.73 GB   wr: 0.0 GB
               path     /var/lib/libvirt/images/guest-db-01-data.qcow2
  Network    : vnet1     virtio    bridge: virbr0
               MAC      52:54:00:11:22:33
                        ↑ 6.24 MB/s   ↓ 23.74 MB/s
  Snapshots  : 0

  · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·

  Guest      : guest-old-01
  State      : shut off
  Virt       : kvm
  Hostname   : guest-old-01  (domain name, agent unavailable)
  UUID       : ab500f8b-0000-1111-2222-000000000003
  Autostart  : no
  vCPUs      : 2
  CPU Model  : POWER11
  Memory     : 0.0 GB / 8.0 GB  -
  Disk       : vda       20.0 GB
               path     /var/lib/libvirt/images/guest-old-01.qcow2
  Network    : 52:54:00:aa:bb:cc  virtio    bridge: default
  Snapshots  : 1  (snap-final)
```

---

## Features

| Feature | Command |
|---|---|
| Full snapshot | `virthawk` |
| Hypervisor info | `virthawk host` or `virthawk --host` |
| All guests | `virthawk guests` or `virthawk --guests` |
| Running guests only | `virthawk running` or `virthawk --running` |
| Single guest | `virthawk guest <name>` or `virthawk --guest <name>` |
| JSON output | `virthawk --json` |
| Live watch mode | `virthawk --watch` |
| Remote hypervisor | `virthawk --uri qemu+ssh://host/system` |

---

## Guest info collected

| Field | Source | Requires guest agent |
|---|---|---|
| Name, UUID, state, autostart | libvirt domain API | No |
| Virt type (kvm / qemu / tcg) | Domain XML | No |
| Hostname | `dom.hostname()` | **Yes** (fallback: domain name) |
| OS name + kernel | `dom.guestInfo()` | **Yes** |
| vCPUs, CPU time | `dom.info()`, `dom.vcpus()` | No |
| CPU model | Domain XML | No |
| CPU pinning topology | `dom.vcpus()` pinmap | No |
| Memory used / max | `dom.memoryStats()`, `dom.info()` | Balloon driver |
| Disk capacity, rd/wr totals | `dom.blockInfo()`, `dom.blockStats()` | No |
| Disk image path | Domain XML | No |
| Network MAC, model, bridge | Domain XML | No |
| Guest IP (accurate) | `dom.interfaceAddresses()` agent | **Yes** |
| Guest IP (fallback) | `dom.interfaceAddresses()` lease | No (dnsmasq networks only) |
| rx/tx throughput | `dom.interfaceStats()` | No |
| Snapshots | `dom.snapshotListNames()` | No |

---

## Dependencies

- [`libvirt-python`](https://pypi.org/project/libvirt-python/) - libvirt Python bindings
- [`rich`](https://github.com/Textualize/rich) - pretty terminal output

---

## Platform support

| Distro | Install libvirt-python |
|---|---|
| SLES / openSUSE | `zypper install python3-libvirt` |
| RHEL / CentOS / Rocky | `dnf install python3-libvirt` |
| Ubuntu / Debian | `apt install python3-libvirt` |
| Fedora | `dnf install python3-libvirt` |
| Any (via pip) | `pip3 install libvirt-python` + `libvirt-devel` headers |

> **Permissions:** `qemu:///system` requires root or membership in the `libvirt` group:
> `usermod -aG libvirt $USER`

---

## Pairing with syshawk

```bash
syshawk       # host OS, CPU, memory, disk, network, firmware
virthawk      # hypervisor version, all guests, vCPUs/RAM/disks/nets
```

---

## Development

```bash
git clone https://github.com/misanjumn/virthawk
cd virthawk
pip3 install -e ".[dev]"
pytest
```

---

## Author

**Misbah Anjum N**
- GitHub: [@misanjumn](https://github.com/misanjumn)
- PyPI: [virthawk](https://pypi.org/project/virthawk/)

---

## License

MIT © Misbah Anjum N
