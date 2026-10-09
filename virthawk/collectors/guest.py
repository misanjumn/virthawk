"""Collect per-guest information from a libvirt domain."""

from __future__ import annotations
import re
import libvirt

# Suppress libvirt's default stderr error handler
def _silence_libvirt():
    try:
        libvirt.registerErrorHandler(lambda ctx, err: None, None)
    except Exception:
        pass

_silence_libvirt()


# libvirt domain state codes → human label
_STATES = {
    libvirt.VIR_DOMAIN_NOSTATE:     "no state",
    libvirt.VIR_DOMAIN_RUNNING:     "running",
    libvirt.VIR_DOMAIN_BLOCKED:     "blocked",
    libvirt.VIR_DOMAIN_PAUSED:      "paused",
    libvirt.VIR_DOMAIN_SHUTDOWN:    "shutdown",
    libvirt.VIR_DOMAIN_SHUTOFF:     "shut off",
    libvirt.VIR_DOMAIN_CRASHED:     "crashed",
    libvirt.VIR_DOMAIN_PMSUSPENDED: "suspended",
}


def collect(dom: libvirt.virDomain) -> dict:
    info: dict = {}
    dom_info = dom.info()   # [state, maxMem, memory, nrVirtCpu, cpuTime]
    state_code = dom_info[0]
    is_running = state_code == libvirt.VIR_DOMAIN_RUNNING

    info["name"]      = dom.name()
    info["uuid"]      = dom.UUIDString()
    info["state"]     = _STATES.get(state_code, str(state_code))
    info["virt_type"] = _virt_type(dom)
    info["cpu_model"] = _cpu_model(dom)
    info["autostart"] = _autostart(dom)
    info["hostname"]  = _hostname(dom, is_running)
    info["guest_os"]  = _guest_os(dom, is_running)
    info["vcpus"]     = dom_info[3]
    info["cpu_time_s"] = round(dom_info[4] / 1e9, 1) if is_running else None
    info["topology"]  = _topology(dom)
    info["memory"]    = _memory(dom, dom_info)
    info["disks"]     = _disks(dom, is_running)
    info["networks"]  = _networks(dom, is_running)
    info["snapshots"] = _snapshots(dom)
    return info


# ── helpers ───────────────────────────────────────────────────────────────────

def _autostart(dom: libvirt.virDomain) -> bool:
    try:
        return bool(dom.autostart())
    except Exception:
        return False


def _virt_type(dom: libvirt.virDomain) -> str:
    """Return the virtualisation type: kvm, qemu, tcg, xen, etc."""
    try:
        xml = dom.XMLDesc()
        m = re.search(r"<domain\s+type=['\"]([^'\"]+)['\"]", xml)
        return m.group(1).lower() if m else ""
    except Exception:
        return ""


def _cpu_model(dom: libvirt.virDomain) -> str:
    """Return the guest CPU model from domain XML e.g. 'POWER11', 'Skylake-Client'."""
    try:
        xml = dom.XMLDesc()
        # <cpu ...><model ...>VALUE</model></cpu>
        m = re.search(r"<cpu\b.*?<model[^>]*>([^<]+)</model>", xml, re.DOTALL)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


def _hostname(dom: libvirt.virDomain, is_running: bool) -> str:
    if is_running:
        try:
            return dom.hostname()
        except Exception:
            pass
    return dom.name()   # fallback to domain name


def _guest_os(dom: libvirt.virDomain, is_running: bool) -> dict:
    """Return OS name + kernel from qemu-guest-agent via guestInfo(). Empty dict if unavailable."""
    if not is_running:
        return {}
    try:
        flags = (
            libvirt.VIR_DOMAIN_GUEST_INFO_OS
        )
        info = dom.guestInfo(flags, 0)
        result = {}
        # os.pretty-name e.g. "SLES 16.0" — preferred
        # fallback: os.name + os.version
        name = info.get("os.pretty-name") or (
            f"{info.get('os.name', '')} {info.get('os.version', '')}".strip()
        )
        if name:
            result["os_name"] = name
        kernel = info.get("os.kernel-release")
        if kernel:
            result["kernel"] = kernel
        return result
    except Exception:
        return {}


def _topology(dom: libvirt.virDomain) -> str | None:
    """Return vCPU pinning string, or 'no pinning' if not set."""
    try:
        vcpu_info = dom.vcpus()
        if not vcpu_info or not vcpu_info[1]:
            return "no pinning"
        pinmaps = vcpu_info[1]   # list of tuples, one per vCPU
        total_host_cpus = len(pinmaps[0]) if pinmaps else 0
        parts = []
        for i, pinmap in enumerate(pinmaps):
            pinned = [j for j, p in enumerate(pinmap) if p]
            # all CPUs allowed = libvirt default = effectively no pinning
            if pinned and len(pinned) < total_host_cpus:
                parts.append(f"pin {i}→{','.join(str(c) for c in pinned)}")
        return "  ".join(parts) if parts else "no pinning"
    except Exception:
        return None


def _memory(dom: libvirt.virDomain, dom_info: list) -> dict:
    max_kb  = dom_info[1]
    curr_kb = dom_info[2]
    used_kb = curr_kb

    # Try balloon stats for actual used memory (requires balloon driver in guest)
    try:
        stats = dom.memoryStats()
        if "rss" in stats:
            used_kb = stats["rss"]
        elif "actual" in stats:
            used_kb = stats["actual"]
    except Exception:
        pass

    max_gb  = round(max_kb  / (1024 ** 2), 1)
    used_gb = round(used_kb / (1024 ** 2), 1)
    pct     = round((used_kb / max_kb) * 100, 1) if max_kb > 0 else 0.0
    return {"used_gb": used_gb, "max_gb": max_gb, "percent": pct}


def _disks(dom: libvirt.virDomain, is_running: bool) -> list[dict]:
    disks = []
    try:
        xml = dom.XMLDesc()
        # collect interface target devs so we can exclude them from disk list
        iface_targets = set(re.findall(
            r"<interface\b.*?<target\s+dev=['\"]([^'\"]+)['\"].*?</interface>",
            xml, re.DOTALL
        ))
        # only <target> inside <disk> blocks
        disk_blocks = re.findall(r"<disk\b.*?</disk>", xml, re.DOTALL)
        for block in disk_blocks:
            m = re.search(r"<target\s+dev=['\"]([^'\"]+)['\"]", block)
            if not m:
                continue
            dev = m.group(1)
            if dev in iface_targets:
                continue   # skip network interface targets
            d: dict = {"dev": dev}
            # source path — file-backed or block device
            ms = re.search(r"<source\s+(?:file|dev)=['\"]([^'\"]+)['\"]", block)
            if ms:
                d["source"] = ms.group(1)
            try:
                bi = dom.blockInfo(dev)
                d["capacity_gb"] = round(bi[0] / (1024 ** 3), 1)
            except Exception:
                d["capacity_gb"] = None
            if is_running:
                try:
                    bs = dom.blockStats(dev)
                    # bs: (rd_req, rd_bytes, wr_req, wr_bytes, errs)
                    # these are cumulative totals since domain start — show as GB
                    d["rd_gb"] = round(bs[1] / (1024 ** 3), 2)
                    d["wr_gb"] = round(bs[3] / (1024 ** 3), 2)
                except Exception:
                    pass
            disks.append(d)
    except Exception:
        pass
    return disks


def _networks(dom: libvirt.virDomain, is_running: bool) -> list[dict]:
    nets = []
    try:
        xml = dom.XMLDesc()
        # parse each <interface> block
        iface_blocks = re.findall(
            r"<interface\b.*?</interface>",
            xml, re.DOTALL
        )
        for block in iface_blocks:
            iface: dict = {}
            # type
            m = re.search(r"<interface\s+type=['\"]([^'\"]+)['\"]", block)
            iface["type"] = m.group(1) if m else ""

            # MAC
            m = re.search(r"<mac\s+address=['\"]([^'\"]+)['\"]", block)
            iface["mac"] = m.group(1) if m else ""

            # source (bridge/network name)
            m = re.search(r"<source\s+(?:bridge|network|dev)=['\"]([^'\"]+)['\"]", block)
            iface["source"] = m.group(1) if m else ""

            # model
            m = re.search(r"<model\s+type=['\"]([^'\"]+)['\"]", block)
            iface["model"] = m.group(1) if m else ""

            # target (host-side vnet name)
            m = re.search(r"<target\s+dev=['\"]([^'\"]+)['\"]", block)
            iface["target"] = m.group(1) if m else ""

            # IP via guest agent first, then DHCP lease fallback
            if is_running and iface.get("mac"):
                iface["ip"] = (_guest_ip_agent(dom, iface["mac"])
                               or _guest_ip_lease(dom, iface["mac"]))

            # traffic stats
            if is_running and iface.get("target"):
                try:
                    st = dom.interfaceStats(iface["target"])
                    # st: (rx_bytes, rx_packets, rx_errs, rx_drop,
                    #       tx_bytes, tx_packets, tx_errs, tx_drop)
                    iface["rx_bytes"] = st[0]
                    iface["tx_bytes"] = st[4]
                except Exception:
                    pass

            nets.append(iface)
    except Exception:
        pass
    return nets


def _guest_ip_agent(dom: libvirt.virDomain, mac: str) -> str | None:
    """Get guest IP via qemu-guest-agent (most accurate)."""
    try:
        ifaces = dom.interfaceAddresses(
            libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT
        )
        for iface_data in ifaces.values():
            if iface_data.get("hwaddr", "").lower() == mac.lower():
                for addr in iface_data.get("addrs", []):
                    if addr["type"] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                        return f"{addr['addr']}/{addr['prefix']}"
    except Exception:
        pass
    return None


def _guest_ip_lease(dom: libvirt.virDomain, mac: str) -> str | None:
    """Get guest IP from libvirt DHCP lease table (no agent needed).
    Works only for guests on libvirt-managed networks (dnsmasq)."""
    try:
        ifaces = dom.interfaceAddresses(
            libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE
        )
        for iface_data in ifaces.values():
            if iface_data.get("hwaddr", "").lower() == mac.lower():
                for addr in iface_data.get("addrs", []):
                    if addr["type"] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                        return f"{addr['addr']}/{addr['prefix']}"
    except Exception:
        pass
    return None


def _snapshots(dom: libvirt.virDomain) -> dict:
    try:
        names = dom.snapshotListNames()
        return {"count": len(names), "names": names}
    except Exception:
        return {"count": 0, "names": []}
