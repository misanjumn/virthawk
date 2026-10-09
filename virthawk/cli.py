"""🦅 VirtHawk CLI — entry point."""

import argparse
import json
import re
import time

from rich.console import Console

from virthawk import __version__
from virthawk.collectors import hypervisor, guest as guest_collector

console = Console()

# ── label helpers (same style as syshawk) ────────────────────────────────────
_LW   = 10
_CONT = " " * (2 + _LW + 3)   # 15 chars — continuation indent


def _label(name: str) -> str:
    return f"  [bold cyan]{name:<{_LW}}[/] : "


def _sublabel(name: str) -> str:
    return f"{_CONT}{name:<8} "


def _pct_color(p: float) -> str:
    if p >= 80:
        return "bold red"
    elif p >= 50:
        return "bold yellow"
    return "bold green"


def _pct(p: float) -> str:
    return f"[{_pct_color(p)}]{p}%[/]"


def _mb(byt: int | None) -> str:
    if byt is None:
        return "—"
    return f"{byt / (1024 ** 2):.2f} MB/s"


# ── section renderers ─────────────────────────────────────────────────────────

def _render_hypervisor(h: dict) -> None:
    hv   = h.get("type", "")
    ver  = h.get("version", "")
    arch = h.get("arch", "")
    console.print(f"{_label('Hypervisor')}{hv} {ver}  ·  {arch}")
    if h.get("libvirt_version"):
        console.print(f"{_label('Libvirt')}{h['libvirt_version']}")
    console.print(f"{_label('Host')}{h.get('hostname', '')}")
    active   = h.get("active", 0)
    inactive = h.get("inactive", 0)
    total    = h.get("total", 0)
    console.print(f"{_label('Domains')}{active} running  ·  {inactive} inactive  ·  {total} total")


def _render_guest(g: dict) -> None:
    state = g["state"]
    state_color = "bold green" if state == "running" else (
        "bold yellow" if state in ("paused", "blocked") else "bold red"
    )
    console.print(f"{_label('Guest')}[bold]{g['name']}[/]")
    console.print(f"{_label('State')}[{state_color}]{state}[/]")
    if g.get("virt_type"):
        console.print(f"{_label('Virt')}{g['virt_type']}")

    # hostname — dim suffix if fallback
    hn = g.get("hostname") or g["name"]
    agent_note = "" if hn != g["name"] else "  [dim](domain name, agent unavailable)[/]"
    console.print(f"{_label('Hostname')}{hn}{agent_note}")

    # OS + kernel from guest agent
    gos = g.get("guest_os") or {}
    if gos.get("os_name"):
        console.print(f"{_label('OS')}{gos['os_name']}")
    if gos.get("kernel"):
        console.print(f"{_label('Kernel')}{gos['kernel']}")

    console.print(f"{_label('UUID')}[dim]{g['uuid']}[/]")
    console.print(f"{_label('Autostart')}{'yes' if g['autostart'] else 'no'}")

    # vCPUs + CPU model
    cpu_time = f"  ·  CPU time: {g['cpu_time_s']}s" if g.get("cpu_time_s") is not None else ""
    console.print(f"{_label('vCPUs')}{g['vcpus']}{cpu_time}")
    if g.get("cpu_model"):
        console.print(f"{_label('CPU Model')}{g['cpu_model']}")

    if g.get("topology"):
        console.print(f"{_label('Topology')}{g['topology']}")

    # memory
    mem = g["memory"]
    if mem["max_gb"] > 0 and state == "running":
        console.print(f"{_label('Memory')}{mem['used_gb']} GB / {mem['max_gb']} GB  {_pct(mem['percent'])}")
    else:
        console.print(f"{_label('Memory')}0.0 GB / {mem['max_gb']} GB  —")

    # disks
    disks = g.get("disks") or []
    for i, d in enumerate(disks):
        lbl = _label("Disk") if i == 0 else _CONT
        cap = f"{d['capacity_gb']} GB" if d.get("capacity_gb") is not None else "—"
        rd  = f"   rd: {d['rd_gb']} GB" if "rd_gb" in d else ""
        wr  = f"   wr: {d['wr_gb']} GB" if "wr_gb" in d else ""
        console.print(f"{lbl}[magenta]{d['dev']:<8}[/]  {cap:<12}{rd}{wr}")
        if d.get("source"):
            console.print(_sublabel("path") + f"[dim]{d['source']}[/]")

    # networks
    nets = g.get("networks") or []
    for i, n in enumerate(nets):
        lbl = _label("Network") if i == 0 else _CONT
        model  = n.get("model") or ""
        mac    = n.get("mac") or ""
        src    = f"  bridge: {n['source']}" if n.get("source") else ""
        # prefer host-side vnet name; fall back to mac for shut-off guests
        target = n.get("target") or ""
        dev_label = target or mac
        console.print(f"{lbl}[bold]{dev_label:<8}[/]  {model:<8}{src}")
        # only show MAC as sub-line when we have a vnet name on the header
        # (for shut-off guests dev_label IS the mac, so no need to repeat it)
        if mac and target:
            console.print(_sublabel("MAC") + mac)
        if n.get("ip"):
            console.print(_sublabel("IP") + n["ip"])
        if "rx_bytes" in n or "tx_bytes" in n:
            console.print(_sublabel("") +
                          f"[green]↑ {_mb(n.get('tx_bytes'))}[/]"
                          f"   [cyan]↓ {_mb(n.get('rx_bytes'))}[/]")

    # snapshots
    snaps = g.get("snapshots", {})
    count = snaps.get("count", 0)
    names = snaps.get("names", [])
    if count > 0:
        name_list = f"  ({', '.join(names)})" if names else ""
        console.print(f"{_label('Snapshots')}{count}{name_list}")
    else:
        console.print(f"{_label('Snapshots')}0")


_RULE = "[dim]  · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·[/]"


def _print_snapshot(hv_data: dict, guests: list[dict]) -> None:
    console.print()
    console.print(f"[bold white]🦅 VirtHawk[/] [dim]v{__version__} — libvirt guest diagnostics[/]")
    console.print()
    _render_hypervisor(hv_data)
    console.print()
    for i, g in enumerate(guests):
        _render_guest(g)
        console.print()
        if i < len(guests) - 1:
            console.print(_RULE)
            console.print()


# ── connect ───────────────────────────────────────────────────────────────────

def _connect(uri: str):
    import libvirt
    conn = libvirt.openReadOnly(uri)
    if conn is None:
        raise RuntimeError(f"Failed to connect to libvirt: {uri}")
    return conn


def _all_guests(conn, running_only: bool = False) -> list:
    import libvirt
    domains = []
    # active (running) domains
    for did in conn.listDomainsID():
        try:
            domains.append(conn.lookupByID(did))
        except Exception:
            pass
    # inactive (defined but not running)
    if not running_only:
        for name in conn.listDefinedDomains():
            try:
                domains.append(conn.lookupByName(name))
            except Exception:
                pass
    return domains


# ── watch ─────────────────────────────────────────────────────────────────────

def _watch(uri: str, interval: int, running_only: bool) -> None:
    console.print(f"[dim]🦅 VirtHawk — live  (Ctrl+C to quit, refreshing every {interval}s)[/]")
    try:
        while True:
            conn = _connect(uri)
            hv_data = hypervisor.collect(conn)
            domains = _all_guests(conn, running_only)
            guests  = [guest_collector.collect(d) for d in domains]
            conn.close()
            console.clear()
            console.print(f"[dim]🦅 VirtHawk — live  (Ctrl+C to quit, refreshing every {interval}s)[/]\n")
            _print_snapshot(hv_data, guests)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/]")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="virthawk",
        description="🦅 VirtHawk — libvirt guest diagnostics CLI",
    )

    parser.add_argument("command", nargs="?", default=None, metavar="COMMAND",
                        help="host | guests | running | guest <name> | json | watch")
    parser.add_argument("name", nargs="?", default=None, metavar="NAME",
                        help="Guest name (used with: virthawk guest <name>)")

    parser.add_argument("--host",    action="store_true", help="Show hypervisor info only")
    parser.add_argument("--guests",  action="store_true", help="Show all guests")
    parser.add_argument("--running", action="store_true", help="Show only running guests")
    parser.add_argument("--guest",   metavar="NAME",      help="Show a single guest by name")

    parser.add_argument("--json",     action="store_true", help="Output as JSON")
    parser.add_argument("--watch",    action="store_true", help="Live refresh mode")
    parser.add_argument("--interval", type=int, default=3, metavar="S",
                        help="Refresh interval for watch (default: 3s)")
    parser.add_argument("--uri",      default="qemu:///system", metavar="URI",
                        help="libvirt connection URI (default: qemu:///system)")
    parser.add_argument("--version",  action="version", version=f"virthawk {__version__}")

    args = parser.parse_args()

    # merge subcommand + flag styles
    do_watch   = args.watch   or args.command == "watch"
    do_json    = args.json    or args.command == "json"
    do_host    = args.host    or args.command == "host"
    do_guests  = args.guests  or args.command == "guests"
    do_running = args.running or args.command == "running"

    # single guest: virthawk guest <name>  OR  virthawk --guest <name>
    single_guest = args.guest
    if args.command == "guest" and args.name:
        single_guest = args.name

    # connect
    try:
        conn = _connect(args.uri)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        return

    hv_data = hypervisor.collect(conn)

    # watch mode
    if do_watch:
        conn.close()
        _watch(args.uri, args.interval, do_running)
        return

    # host only
    if do_host:
        conn.close()
        console.print()
        console.print(f"[bold white]🦅 VirtHawk[/] [dim]v{__version__} — libvirt guest diagnostics[/]")
        console.print()
        _render_hypervisor(hv_data)
        console.print()
        return

    # single guest
    if single_guest:
        try:
            dom = conn.lookupByName(single_guest)
            g = guest_collector.collect(dom)
            conn.close()
            console.print()
            console.print(f"[bold white]🦅 VirtHawk[/] [dim]v{__version__} — libvirt guest diagnostics[/]")
            console.print()
            _render_guest(g)
            console.print()
        except Exception as e:
            conn.close()
            console.print(f"[bold red]Error:[/] guest '{single_guest}' not found — {e}")
        return

    # all / running guests
    running_only = do_running and not do_guests
    domains = _all_guests(conn, running_only)
    guests  = [guest_collector.collect(d) for d in domains]
    conn.close()

    if do_json:
        print(json.dumps({"hypervisor": hv_data, "guests": guests}, indent=2))
        return

    _print_snapshot(hv_data, guests)
