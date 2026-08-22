#!/usr/bin/env python3
"""Assemble chunked installer files and publish a public GitHub Release."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    root = Path("dist")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        sys.exit("dist/manifest.json is missing")
    manifest = json.loads(manifest_path.read_text())
    tag = manifest["tag"]
    version = manifest["version"]
    name = manifest.get("name") or f"PIVOT {version}"
    notes = manifest.get("notes") or name
    assembled_dir = Path("assembled")
    assembled_dir.mkdir(exist_ok=True)
    files: list[str] = []

    for asset in manifest["assets"]:
        asset_name = asset["name"]
        expected = asset["sha256"]
        chunk_dir = root / "chunks" / asset_name
        parts = sorted(chunk_dir.glob("*.b64"))
        if not parts:
            sys.exit(f"no chunks in {chunk_dir}")
        raw = b"".join(base64.b64decode(p.read_text()) for p in parts)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected:
            sys.exit(f"sha256 mismatch for {asset_name}: {digest} != {expected}")
        out = assembled_dir / asset_name
        out.write_bytes(raw)
        files.append(str(out))
        print(f"assembled {asset_name} ({len(raw)} bytes)")
        sig = root / f"{asset_name}.sig"
        if not sig.is_file():
            sys.exit(f"missing {sig}")
        files.append(str(sig))

    setup_name = manifest["assets"][0]["name"]
    sig_text = (root / f"{setup_name}.sig").read_text().strip()
    url = f"https://github.com/diny-hou/Pivot-releases/releases/download/{tag}/{setup_name}"
    update = {
        "version": version,
        "notes": notes,
        "pub_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": {
            "windows-x86_64": {
                "url": url,
                "signature": sig_text,
            }
        },
    }
    update_path = assembled_dir / "update.json"
    update_path.write_text(json.dumps(update, indent=2) + "\n")
    files.append(str(update_path))
    print(update_path.read_text())

    existing = subprocess.run(["gh", "release", "view", tag], capture_output=True, text=True)
    if existing.returncode == 0:
        cmd = ["gh", "release", "upload", tag, "--clobber", *files]
    else:
        cmd = ["gh", "release", "create", tag, "--title", name, "--notes", notes, *files]
    print("running", cmd[:5], "...")
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
