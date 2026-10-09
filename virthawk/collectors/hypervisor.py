"""Collect hypervisor-level information from libvirt."""

import re
import libvirt

# Suppress libvirt's default stderr error handler
try:
    libvirt.registerErrorHandler(lambda ctx, err: None, None)
except Exception:
    pass


def collect(conn: libvirt.virConnect) -> dict:
    info = {}
    try:
        info["type"]    = conn.getType()                        # e.g. "QEMU"
        info["version"] = _fmt_version(conn.getVersion())       # e.g. "10.0.11"
        info["libvirt_version"] = _fmt_version(conn.getLibVersion())  # e.g. "10.0.0"
        info["hostname"] = conn.getHostname()
        info["uri"] = conn.getURI()

        caps_xml = conn.getCapabilities()
        info["arch"] = _parse_arch(caps_xml)

        # domain counts
        info["active"] = conn.numOfDomains()
        info["inactive"] = conn.numOfDefinedDomains()
        info["total"] = info["active"] + info["inactive"]

        # host memory (KB → GB)
        node_info = conn.getNodeInfo()
        total_kb = node_info[1] * 1024          # nodeInfo[1] is memory in MB
        info["host_memory_gb"] = round(total_kb / (1024 ** 2), 1)
        info["host_cpus"] = node_info[2]

        # KVM acceleration
        info["kvm"] = _has_kvm(caps_xml)
    except Exception:
        pass
    return info


def _fmt_version(v: int) -> str:
    """Convert libvirt packed int (e.g. 8002000) to '8.2.0'."""
    major = v // 1_000_000
    minor = (v % 1_000_000) // 1_000
    micro = v % 1_000
    return f"{major}.{minor}.{micro}"


def _parse_arch(caps_xml: str) -> str:
    try:
        m = re.search(r"<host>.*?<arch>([^<]+)</arch>", caps_xml, re.DOTALL)
        return m.group(1) if m else ""
    except Exception:
        return ""


def _has_kvm(caps_xml: str) -> bool:
    # present as: <baselabel type='kvm'> or <domain type='kvm'>
    return "kvm" in caps_xml.lower()
