"""Live host + container resource snapshot for the Server panel.

Host numbers come from psutil (always available). Per-container CPU/RAM
comes from the Docker socket when it is mounted
(/var/run/docker.sock:/var/run/docker.sock:ro on the backend service) —
otherwise ``containers`` is empty and ``docker`` is False, and the panel
says so instead of failing.
"""
import logging
import os
import time

log = logging.getLogger("igfunnel.hoststats")


def host_snapshot() -> dict:
    import psutil

    per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    total = round(sum(per_core) / len(per_core), 1) if per_core else 0.0
    try:
        load1, load5, load15 = os.getloadavg()  # type: ignore[attr-defined] — unix only
    except (OSError, AttributeError):
        load1 = load5 = load15 = 0.0
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disks = []
    seen = set()
    for mount in ("/",):
        try:
            du = psutil.disk_usage(mount)
        except OSError:
            continue
        disks.append({"mount": mount, "total": du.total, "used": du.used, "percent": du.percent})
        seen.add(mount)
    # Media volume matters most (uploads + DB live here); skip if same fs.
    try:
        from app.config import settings

        media = settings.MEDIA_ROOT
        if media not in seen:
            du = psutil.disk_usage(media)
            disks.append({"mount": media, "total": du.total, "used": du.used, "percent": du.percent})
    except Exception as exc:
        log.warning("media disk probe failed: %s", exc)
    net = psutil.net_io_counters()
    return {
        "ts": time.time(),
        "cpu": {
            "total": total,
            "per_core": [round(c, 1) for c in per_core],
            "count": psutil.cpu_count() or len(per_core),
            "load1": round(load1, 2),
            "load5": round(load5, 2),
            "load15": round(load15, 2),
        },
        "mem": {
            "total": vm.total, "used": vm.used, "percent": vm.percent,
            "swap_total": swap.total, "swap_used": swap.used, "swap_percent": swap.percent,
        },
        "disk": disks,
        "net": {
            "sent": net.bytes_sent, "recv": net.bytes_recv,
            "packets_sent": net.packets_sent, "packets_recv": net.packets_recv,
            "errin": net.errin, "errout": net.errout,
        },
        "uptime_s": int(time.time() - psutil.boot_time()),
    }


def _container_cpu_percent(stats: dict) -> float:
    try:
        cpu = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        online = stats["cpu_stats"].get("online_cpus") or len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage") or []) or 1
        if system <= 0 or cpu < 0:
            return 0.0
        return round(cpu / system * online * 100, 1)
    except (KeyError, TypeError, ZeroDivisionError):
        return 0.0


def container_snapshot() -> "list[dict] | None":
    """Per-container stats, or None when the Docker socket is unavailable."""
    try:
        import docker

        client = docker.from_env(timeout=5)
        out = []
        for c in client.containers.list(all=True):
            try:
                raw = c.stats(stream=False)
                s: dict = raw  # type: ignore[assignment] — stubs say Iterator, runtime is dict
            except Exception as exc:
                log.warning("stats failed for %s: %s", c.name, exc)
                continue
            mem_stats = s.get("memory_stats") or {}
            limit = mem_stats.get("limit") or 0
            usage = mem_stats.get("usage") or 0
            out.append({
                "name": c.name,
                "state": (s.get("name") and c.status) or c.status,
                "cpu": _container_cpu_percent(s),
                "mem_used": usage,
                "mem_limit": limit,
                "mem_percent": round(usage / limit * 100, 1) if limit else 0.0,
            })
        try:
            client.close()
        except Exception:
            pass
        return sorted(out, key=lambda r: r["name"])
    except Exception as exc:
        log.warning("docker socket unavailable: %s", exc)
        return None


def full_snapshot() -> dict:
    snap = host_snapshot()
    containers = container_snapshot()
    snap["docker"] = containers is not None
    snap["containers"] = containers or []
    return snap
