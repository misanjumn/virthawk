"""Tests for guest collector — uses unittest.mock to avoid needing libvirt."""

from unittest.mock import MagicMock, patch
import libvirt
from virthawk.collectors import guest as guest_collector


def _make_dom(name="test-vm", state=libvirt.VIR_DOMAIN_RUNNING,
              max_mem=4 * 1024 * 1024, curr_mem=2 * 1024 * 1024,
              vcpus=4, cpu_time=5_000_000_000):
    dom = MagicMock()
    dom.name.return_value = name
    dom.UUIDString.return_value = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    dom.info.return_value = [state, max_mem, curr_mem, vcpus, cpu_time]
    dom.autostart.return_value = 1
    dom.hostname.return_value = f"{name}.local"
    dom.memoryStats.return_value = {"rss": curr_mem}
    dom.vcpus.return_value = (
        [(0, 1, 5_000_000_000, 0)],   # vcpu info
        [(True, False, False, False)]  # pinmap — pinned to cpu 0
    )
    dom.XMLDesc.return_value = """
        <domain>
          <devices>
            <disk><target dev='vda'/></disk>
            <interface type='bridge'>
              <mac address='52:54:00:ab:cd:ef'/>
              <source bridge='virbr0'/>
              <model type='virtio'/>
              <target dev='vnet0'/>
            </interface>
          </devices>
        </domain>
    """
    dom.blockInfo.return_value = (50 * 1024**3, 40 * 1024**3, 40 * 1024**3)
    dom.blockStats.return_value = (100, 1024 * 1024, 50, 512 * 1024, 0)
    dom.interfaceStats.return_value = (2 * 1024**2, 1000, 0, 0, 1 * 1024**2, 500, 0, 0)
    dom.interfaceAddresses.side_effect = Exception("no agent")
    dom.snapshotListNames.return_value = ["snap1", "snap2"]
    return dom


def test_collect_returns_required_keys():
    dom = _make_dom()
    data = guest_collector.collect(dom)
    for key in ("name", "uuid", "state", "autostart", "hostname",
                "vcpus", "memory", "disks", "networks", "snapshots"):
        assert key in data, f"Missing key: {key}"


def test_state_running():
    dom = _make_dom(state=libvirt.VIR_DOMAIN_RUNNING)
    data = guest_collector.collect(dom)
    assert data["state"] == "running"


def test_state_shutoff():
    dom = _make_dom(state=libvirt.VIR_DOMAIN_SHUTOFF, cpu_time=0)
    data = guest_collector.collect(dom)
    assert data["state"] == "shut off"


def test_memory_keys():
    dom = _make_dom()
    data = guest_collector.collect(dom)
    for key in ("used_gb", "max_gb", "percent"):
        assert key in data["memory"]


def test_memory_percent_in_range():
    dom = _make_dom()
    data = guest_collector.collect(dom)
    assert 0.0 <= data["memory"]["percent"] <= 100.0


def test_disks_have_dev_and_capacity():
    dom = _make_dom()
    data = guest_collector.collect(dom)
    assert len(data["disks"]) >= 1
    assert data["disks"][0]["dev"] == "vda"
    assert data["disks"][0]["capacity_gb"] == 50.0


def test_networks_have_mac():
    dom = _make_dom()
    data = guest_collector.collect(dom)
    assert len(data["networks"]) >= 1
    assert data["networks"][0]["mac"] == "52:54:00:ab:cd:ef"


def test_snapshots_count():
    dom = _make_dom()
    data = guest_collector.collect(dom)
    assert data["snapshots"]["count"] == 2
    assert "snap1" in data["snapshots"]["names"]


def test_topology_pinning():
    dom = _make_dom()
    data = guest_collector.collect(dom)
    assert data["topology"] is not None
    assert "pin 0" in data["topology"]


def test_hostname_fallback_when_agent_unavailable():
    dom = _make_dom(state=libvirt.VIR_DOMAIN_SHUTOFF, name="vm-offline")
    dom.hostname.side_effect = Exception("agent not running")
    data = guest_collector.collect(dom)
    assert data["hostname"] == "vm-offline"
