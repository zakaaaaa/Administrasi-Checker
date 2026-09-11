"""Metrik real-time VPS untuk menu Monitoring Server di admin panel.

Backend berjalan di VPS yang sama dengan aplikasi, jadi semua angka dibaca
langsung dari kernel via psutil (/proc) dan dari systemd (status service).
"""
from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone

import psutil

# Service systemd yang ditampilkan di panel.
MONITORED_SERVICES = [
    ("administrasi-checker-backend", "Backend (FastAPI)"),
    ("administrasi-checker-frontend", "Frontend (Next.js)"),
    ("nginx", "Nginx"),
]

# Filesystem virtual / snap tidak relevan untuk kapasitas disk.
_IGNORED_FSTYPES = {"squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs"}

# Snapshot counter I/O terakhir, untuk menghitung laju (byte/detik) antar-poll.
_io_lock = threading.Lock()
_last_io: dict | None = None


# Info statis — tidak berubah selama proses hidup.
_STATIC_INFO = {
    "hostname": socket.gethostname(),
    "cpu_cores_logical": psutil.cpu_count(logical=True) or 1,
}


def _io_rates() -> dict:
    """Laju network & disk I/O sejak poll sebelumnya (None pada poll pertama)."""
    global _last_io

    net = psutil.net_io_counters(pernic=True)
    net_sent = sum(c.bytes_sent for nic, c in net.items() if nic != "lo")
    net_recv = sum(c.bytes_recv for nic, c in net.items() if nic != "lo")
    disk = psutil.disk_io_counters()
    disk_read = disk.read_bytes if disk else 0
    disk_write = disk.write_bytes if disk else 0

    now = {
        "t": time.monotonic(),
        "net_sent": net_sent,
        "net_recv": net_recv,
        "disk_read": disk_read,
        "disk_write": disk_write,
    }
    with _io_lock:
        prev, _last_io = _last_io, now

    def rate(key: str) -> float | None:
        if prev is None:
            return None
        elapsed = now["t"] - prev["t"]
        if elapsed <= 0:
            return None
        # Counter bisa reset (mis. interface restart) — jangan tampilkan negatif.
        return max(0.0, (now[key] - prev[key]) / elapsed)

    return {
        "network": {
            "sent_total": net_sent,
            "recv_total": net_recv,
            "sent_per_sec": rate("net_sent"),
            "recv_per_sec": rate("net_recv"),
        },
        "disk_io": {
            "read_total": disk_read,
            "write_total": disk_write,
            "read_per_sec": rate("disk_read"),
            "write_per_sec": rate("disk_write"),
        },
    }


def _disks() -> list[dict]:
    disks = []
    seen_devices = set()
    for part in psutil.disk_partitions(all=False):
        if part.fstype in _IGNORED_FSTYPES or part.device in seen_devices:
            continue
        if part.mountpoint.startswith("/snap"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        seen_devices.add(part.device)
        disks.append({
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        })
    return disks


def _services() -> list[dict]:
    names = [name for name, _ in MONITORED_SERVICES]
    parsed: dict[str, dict] = {}
    try:
        out = subprocess.run(
            ["systemctl", "show", *names,
             "-p", "Id", "-p", "ActiveState", "-p", "SubState",
             "-p", "ActiveEnterTimestampMonotonic", "-p", "MainPID", "-p", "MemoryCurrent"],
            capture_output=True, text=True, timeout=3, check=False,
        ).stdout
        # Output: satu blok key=value per unit, dipisah baris kosong.
        for block in out.strip().split("\n\n"):
            props = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
            unit_id = props.get("Id", "").removesuffix(".service")
            if unit_id:
                parsed[unit_id] = props
    except (OSError, subprocess.SubprocessError):
        pass

    now_mono = time.monotonic()
    services = []
    for name, label in MONITORED_SERVICES:
        props = parsed.get(name, {})
        active_state = props.get("ActiveState") or "unknown"
        uptime_seconds = None
        entered = props.get("ActiveEnterTimestampMonotonic", "0")
        if active_state == "active" and entered.isdigit() and int(entered) > 0:
            # systemd & time.monotonic() sama-sama memakai CLOCK_MONOTONIC.
            uptime_seconds = max(0, round(now_mono - int(entered) / 1_000_000))
        memory = props.get("MemoryCurrent", "")
        services.append({
            "name": name,
            "label": label,
            "active_state": active_state,
            "sub_state": props.get("SubState") or "unknown",
            "main_pid": int(props["MainPID"]) if props.get("MainPID", "0").isdigit() and props["MainPID"] != "0" else None,
            "memory_bytes": int(memory) if memory.isdigit() else None,
            "uptime_seconds": uptime_seconds,
        })
    return services


def collect_server_stats() -> dict:
    # Sampling 0.5 dtk agar CPU% akurat di tiap poll (endpoint sync → threadpool).
    per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    load1, load5, load15 = os.getloadavg()
    vm = psutil.virtual_memory()

    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "system": _STATIC_INFO,
        "cpu": {
            "percent": round(sum(per_core) / len(per_core), 1) if per_core else 0.0,
            "per_core": [round(v, 1) for v in per_core],
            "load_avg": [round(load1, 2), round(load5, 2), round(load15, 2)],
        },
        "memory": {
            "total": vm.total,
            "available": vm.available,
            # "used" versi htop: total - available (buff/cache tidak dihitung terpakai).
            "used": vm.total - vm.available,
            "percent": vm.percent,
        },
        "disks": _disks(),
        **_io_rates(),
        "services": _services(),
    }
