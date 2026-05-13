"""System-wide metrics: CPU, RAM, disks, network, uptime."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import psutil


@dataclass
class SystemSnapshot:
    ts: float
    cpu_percent: float
    cpu_per_core: list[float]
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float
    swap_percent: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    net_sent_mb: float
    net_recv_mb: float
    uptime_s: float
    boot_time: float


_last_net = psutil.net_io_counters()
_last_net_ts = time.time()


def snapshot() -> dict:
    global _last_net, _last_net_ts

    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    du = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    now = time.time()
    dt = max(now - _last_net_ts, 0.001)
    sent_rate = (net.bytes_sent - _last_net.bytes_sent) / dt / 1024 / 1024
    recv_rate = (net.bytes_recv - _last_net.bytes_recv) / dt / 1024 / 1024
    _last_net, _last_net_ts = net, now

    snap = SystemSnapshot(
        ts=now,
        cpu_percent=psutil.cpu_percent(interval=None),
        cpu_per_core=psutil.cpu_percent(interval=None, percpu=True),
        ram_percent=vm.percent,
        ram_used_mb=round(vm.used / 1024 / 1024, 1),
        ram_total_mb=round(vm.total / 1024 / 1024, 1),
        swap_percent=sw.percent,
        disk_percent=du.percent,
        disk_used_gb=round(du.used / 1024 / 1024 / 1024, 1),
        disk_total_gb=round(du.total / 1024 / 1024 / 1024, 1),
        net_sent_mb=round(sent_rate, 3),
        net_recv_mb=round(recv_rate, 3),
        uptime_s=round(now - psutil.boot_time(), 0),
        boot_time=psutil.boot_time(),
    )
    return asdict(snap)
