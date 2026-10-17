"""Create, inspect and delete the Crusoe Cloud VM that hosts the NemoClaw sandbox.

    python scripts/crusoe_vm.py create     # 50 GiB disk + c1a.4x in us-east1-a, Ubuntu 22.04
    python scripts/crusoe_vm.py status     # state and public IP
    python scripts/crusoe_vm.py delete     # VM and disk, so billing stops

Uses the signed client in scripts/crusoe_cloud.py and ~/.ssh/liftoff_crusoe.pub.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crusoe_cloud import request  # noqa: E402

PROJECT = os.environ.get("CRUSOE_PROJECT_ID", "a5cc0e16-9812-45f7-8946-9c3a512c8e2f")
LOCATION = "us-east1-a"
SUBNET = "b5383511-f0b9-4e00-9a1e-1859ff7def9c"  # default-subnet-us-east1-a
VM_TYPE = "c1a.4x"
IMAGE = "ubuntu22.04"
NAME = "liftoff-nemoclaw"
DISK = "liftoff-nemoclaw-data"
PUBKEY = Path.home() / ".ssh" / "liftoff_crusoe.pub"
P = f"/projects/{PROJECT}"


def _items(path: str) -> list[dict]:
    status, out = request("GET", path)
    if status != 200:
        raise SystemExit(f"GET {path} -> {status}: {out}")
    return out.get("items", [])


def find_vm() -> dict | None:
    return next((v for v in _items(f"{P}/compute/vms/instances") if v.get("name") == NAME), None)


def find_disk() -> dict | None:
    return next((d for d in _items(f"{P}/storage/disks") if d.get("name") == DISK), None)


def wait(pred, what: str, timeout: int = 600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        got = pred()
        if got:
            return got
        time.sleep(5)
    raise SystemExit(f"timed out waiting for {what}")


def public_ip(vm: dict) -> str | None:
    for nic in vm.get("network_interfaces", []):
        for ip in nic.get("ips", []):
            pub = ip.get("public_ipv4") or {}
            if pub.get("address"):
                return pub["address"]
    return None


def create() -> None:
    if find_vm():
        print("VM already exists")
        return status()
    disk = find_disk()
    if not disk:
        s, out = request("POST", f"{P}/storage/disks",
                         body={"name": DISK, "location": LOCATION, "size": "50GiB", "type": "persistent-ssd"})
        print("disk create ->", s, json.dumps(out)[:300])
        if s >= 300:
            raise SystemExit(1)
        disk = wait(lambda: (d := find_disk()) and d.get("id") and d, "disk")
    print("disk", disk["id"], disk.get("size"))
    body = {
        "name": NAME, "type": VM_TYPE, "location": LOCATION, "image": IMAGE,
        "ssh_public_key": PUBKEY.read_text().strip(),
        "disks": [{"disk_id": disk["id"], "mode": "read-write", "attachment_type": "data"}],
        "network_interfaces": [{"subnet": SUBNET}],
    }
    s, out = request("POST", f"{P}/compute/vms/instances", body=body)
    print("vm create ->", s, json.dumps(out)[:400])
    if s >= 300:
        raise SystemExit(1)
    vm = wait(lambda: (v := find_vm()) and v.get("state") in ("STATE_RUNNING", "RUNNING") and v, "VM running")
    print("running:", NAME, public_ip(vm))


def status() -> None:
    vm = find_vm()
    if not vm:
        print("no VM")
        return
    print(vm.get("state"), VM_TYPE, LOCATION, "ip:", public_ip(vm))


def delete() -> None:
    vm = find_vm()
    if vm:
        s, out = request("DELETE", f"{P}/compute/vms/instances/{vm['id']}")
        print("vm delete ->", s, str(out)[:200])
        wait(lambda: not find_vm(), "VM deleted")
    disk = find_disk()
    if disk:
        s, out = request("DELETE", f"{P}/storage/disks/{disk['id']}")
        print("disk delete ->", s, str(out)[:200])
        wait(lambda: not find_disk(), "disk deleted")
    print("deleted; nothing left billing")


if __name__ == "__main__":
    {"create": create, "status": status, "delete": delete}[sys.argv[1]]()
