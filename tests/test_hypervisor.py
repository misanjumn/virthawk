"""Tests for hypervisor collector — uses unittest.mock."""

from unittest.mock import MagicMock
from virthawk.collectors import hypervisor


def _make_conn():
    conn = MagicMock()
    conn.getType.return_value = "QEMU"
    conn.getVersion.return_value = 8_002_000
    conn.getLibVersion.return_value = 10_000_000
    conn.getHostname.return_value = "kvm-host.local"
    conn.getURI.return_value = "qemu:///system"
    conn.getCapabilities.return_value = "<capabilities><host><arch>x86_64</arch><kvm/></host></capabilities>"
    conn.numOfDomains.return_value = 2
    conn.numOfDefinedDomains.return_value = 1
    # nodeInfo: (model, memory_MB, cpus, mhz, nodes, sockets, cores, threads)
    conn.getNodeInfo.return_value = ("x86_64", 16384, 8, 3600, 1, 1, 4, 2)
    return conn


def test_collect_returns_required_keys():
    conn = _make_conn()
    data = hypervisor.collect(conn)
    for key in ("type", "version", "hostname", "active", "inactive", "total"):
        assert key in data, f"Missing key: {key}"


def test_version_format():
    conn = _make_conn()
    data = hypervisor.collect(conn)
    assert data["version"] == "8.2.0"


def test_domain_counts():
    conn = _make_conn()
    data = hypervisor.collect(conn)
    assert data["active"] == 2
    assert data["inactive"] == 1
    assert data["total"] == 3


def test_kvm_detected():
    conn = _make_conn()
    data = hypervisor.collect(conn)
    assert data["kvm"] is True


def test_kvm_not_present():
    conn = _make_conn()
    conn.getCapabilities.return_value = "<capabilities><host><arch>x86_64</arch></host></capabilities>"
    data = hypervisor.collect(conn)
    assert data["kvm"] is False


def test_arch_parsed():
    conn = _make_conn()
    data = hypervisor.collect(conn)
    assert data["arch"] == "x86_64"
