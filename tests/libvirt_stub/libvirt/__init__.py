"""
Minimal libvirt stub for running tests on machines without libvirt-python installed
(e.g. macOS CI / dev machines). Only exposes the constants and types used by virthawk.
"""

# Domain state constants
VIR_DOMAIN_NOSTATE     = 0
VIR_DOMAIN_RUNNING     = 1
VIR_DOMAIN_BLOCKED     = 2
VIR_DOMAIN_PAUSED      = 3
VIR_DOMAIN_SHUTDOWN    = 4
VIR_DOMAIN_SHUTOFF     = 5
VIR_DOMAIN_CRASHED     = 6
VIR_DOMAIN_PMSUSPENDED = 7

# IP address type constants
VIR_IP_ADDR_TYPE_IPV4 = 0
VIR_IP_ADDR_TYPE_IPV6 = 1

# Guest agent interface address source
VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT = 1
VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE = 2

# guestInfo flags
VIR_DOMAIN_GUEST_INFO_OS = 4


class virConnect:
    pass


class virDomain:
    pass


def openReadOnly(uri: str):
    raise NotImplementedError("stub: real libvirt not available")
