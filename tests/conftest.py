"""
Inject the libvirt stub so tests run on machines without libvirt-python.
The stub directory takes priority over any real libvirt install.
"""
import sys
import os

_stub_dir = os.path.join(os.path.dirname(__file__), "libvirt_stub")
if _stub_dir not in sys.path:
    sys.path.insert(0, _stub_dir)
