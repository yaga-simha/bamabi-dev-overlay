#!/usr/bin/env python3
"""Safe manager for local sibling Cargo `[patch]` overrides and Cargo.lock hygiene."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib

MANAGED_HEADER = "# MANAGED BY bamabi-dev-overlay/overlay.py"
TEMPLATE_PATH = Path(__file__).resolve().parent / "cargo-overlay.toml"

LAYER_REPOS: tuple[str, ...] = (
    "bamabi-wire",
    "bamabi-tools",
    "bamabi-core",
    "bamabi",
    "bamabi-showcase",
)

CRATE_REPO: dict[str, str] = {
    "bamabi_sys": "bamabi-wire",
    "bamabi_macros": "bamabi-wire",
    "bamabi_sdk_gen": "bamabi-wire",
    "bamabi_guest_sys": "bamabi-wire",
    "bamabi_guest": "bamabi-wire",
    "bamabi_trust": "bamabi-tools",
    "bamabi_manifest": "bamabi-tools",
    "cargo-bam": "bamabi-tools",
    "bamabi_host_sys": "bamabi-core",
    "bamabi_host": "bamabi-core",
    "bamabi_watcher": "bamabi-core",
    "bamabi_bridges": "bamabi",
    "bamabi_render": "bamabi",
    "bamabi_reflect": "bamabi",
    "bamabi": "bamabi",
}

SKIP_DIRS = {".git", "target", ".zig-cache", "zig-out", "__pycache__"}


def load_overlay_patch_tables(
    template_path: Path = TEMPLATE_PATH,
) -> dict[str, dict[str, str]]:
    with template_path.open("rb") as f:
        data = tomllib.load(f)
    patch = data.get("patch", {})
    tables: dict[str, dict[str, str]] = {}
    for repo_url, crates in patch.items():
        if not isinstance(crates, dict):
            continue
        crate_map: dict[str, str] = {}
        for crate_name, spec in crates.items():
            if isinstance(spec, dict) and isinstance(spec.get("path"), str):
                crate_map[crate_name] = spec["path"]
        if crate_map:
            tables[repo_url] = crate_map
    return tables


def load_overlay_crate_paths(template_path: Path = TEMPLATE_PATH) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for crates in load_overlay_patch_tables(template_path).values():
        for crate_name, rel_path in crates.items():
            entries.append((crate_name, rel_path))
    return entries


def build_partial_overlay_text(
    root: Path, template_path: Path = TEMPLATE_PATH
) -> tuple[str, int, int]:
    tables = load_overlay_patch_tables(template_path)
    total = sum(len(crates) for crates in tables.values())
    present_tables: dict[str, dict[str, str]] = {}
    present = 0
    for url, crates in tables.items():
        kept = {
            crate_name: rel_path
            for crate_name, rel_path in crates.items()
            if (root / rel_path / "Cargo.toml").is_file()
        }
        if kept:
            present_tables[url] = kept
            present += len(kept)

    if present == total:
        return template_path.read_text(encoding="utf-8"), present, total

    lines = [
        f"{MANAGED_HEADER} — DO NOT EDIT MANUALLY",
        "# Partial local sibling `[patch]` overlay for `<federation-root>/.cargo/config.toml`.",
        "# Paths are relative to the directory containing `.cargo/` (i.e., the federation root).",
    ]
    for url, kept in present_tables.items():
        lines.append("")
        lines.append(f'[patch."{url}"]')
        for crate_name, rel_path in kept.items():
            lines.append(f'{crate_name} = {{ path = "{rel_path}" }}')
    lines.append("")
    return "\n".join(lines), present, total


def verify_local_crates_exist(root: Path) -> list[str]:
    missing: list[str] = []
    for crate_name, rel_path in load_overlay_crate_paths():
        crate_dir = root / rel_path
        if not (crate_dir / "Cargo.toml").is_file():
            missing.append(f"{crate_name} ({crate_dir})")
    return missing


def discover_lockfiles(repo_dir: Path) -> list[Path]:
    if not repo_dir.is_dir():
        return []
    found: list[Path] = []
    for walk_root, dirs, files in os.walk(repo_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        if "Cargo.lock" in files:
            found.append(Path(walk_root) / "Cargo.lock")
    return found


def check_git_dirty_lockfiles(repo_dir: Path) -> list[Path]:
    if not (repo_dir / ".git").exists():
        return []
    head_check = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if head_check.returncode != 0:
        return []

    status = subprocess.run(
        ["git", "-C", str(repo_dir), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:
        return []

    dirty: list[Path] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        rel = line[3:].strip()
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1].strip()
        rel = rel.strip('"')
        if Path(rel).name == "Cargo.lock":
            dirty.append(repo_dir / rel)
    return dirty


def inspect_cargolock_hygiene(root: Path) -> tuple[list[str], list[str]]:
    """Return (non_standalone_issues, dirty_git_issues)."""
    non_standalone: list[str] = []
    dirty_issues: list[str] = []

    for repo in LAYER_REPOS:
        repo_dir = root / repo
        for lock_path in discover_lockfiles(repo_dir):
            try:
                with lock_path.open("rb") as f:
                    data = tomllib.load(f)
            except tomllib.TOMLDecodeError as exc:
                non_standalone.append(f"{lock_path.relative_to(root)}: invalid TOML ({exc})")
                continue

            for pkg in data.get("package", []):
                if not isinstance(pkg, dict):
                    continue
                name = pkg.get("name")
                if not isinstance(name, str):
                    continue
                owner = CRATE_REPO.get(name)
                if owner is None or owner == repo:
                    continue
                expected_prefix = f"git+https://github.com/yaga-simha/{owner}.git?branch=main#"
                source = pkg.get("source", "")
                if not isinstance(source, str) or not source.startswith(expected_prefix):
                    non_standalone.append(
                        f"{lock_path.relative_to(root)}: upstream crate {name!r} ({owner}) "
                        f"has non-standalone source={source!r} (expected prefix {expected_prefix!r})"
                    )

        for dirty_path in check_git_dirty_lockfiles(repo_dir):
            dirty_issues.append(
                f"{dirty_path.relative_to(root)}: uncommitted Cargo.lock modification in git"
            )

    return non_standalone, dirty_issues


def target_config_path(root: Path) -> Path:
    return root / ".cargo" / "config.toml"


def cmd_enable(root: Path, force: bool, partial: bool = False) -> int:
    if partial:
        content, present_count, total_count = build_partial_overlay_text(root)
        if present_count == 0 and not force:
            print(
                f"ERROR: No local sibling crate directories found under {root}; cannot write partial overlay.",
                file=sys.stderr,
            )
            return 1
        if present_count == 0:
            content = TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        missing = verify_local_crates_exist(root)
        if missing and not force:
            print("ERROR: Missing local crate directories required by cargo-overlay.toml:", file=sys.stderr)
            for item in missing:
                print(f"  - {item}", file=sys.stderr)
            return 1
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        total_count = len(load_overlay_crate_paths())
        present_count = total_count - len(missing)

    cfg_path = target_config_path(root)
    if cfg_path.exists():
        existing = cfg_path.read_text(encoding="utf-8")
        if MANAGED_HEADER not in existing and not force:
            print(
                f"ERROR: Refusing to overwrite unmanaged {cfg_path}; pass --force to overwrite.",
                file=sys.stderr,
            )
            return 1

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(content, encoding="utf-8")
    if partial and present_count < total_count:
        print(
            f"Enabled partial bamabi local sibling overlay ({present_count}/{total_count} crates) at: {cfg_path}"
        )
    else:
        print(f"Enabled bamabi local sibling overlay at: {cfg_path}")
    print(
        "Reminder: Do NOT commit Cargo.lock modifications generated while the local [patch] overlay is enabled."
    )
    return 0


def cmd_disable(root: Path, force: bool) -> int:
    cfg_path = target_config_path(root)
    if not cfg_path.exists():
        print(f"Overlay already disabled ({cfg_path} absent).")
    else:
        existing = cfg_path.read_text(encoding="utf-8")
        if MANAGED_HEADER not in existing and not force:
            print(
                f"ERROR: Refusing to remove unmanaged {cfg_path}; pass --force to remove.",
                file=sys.stderr,
            )
            return 1
        cfg_path.unlink()
        print(f"Disabled bamabi local sibling overlay (removed {cfg_path}).")
        cargo_dir = cfg_path.parent
        try:
            if cargo_dir.is_dir() and not any(cargo_dir.iterdir()):
                cargo_dir.rmdir()
        except OSError:
            pass

    non_standalone, dirty_issues = inspect_cargolock_hygiene(root)
    if non_standalone or dirty_issues:
        print("Cargo.lock hygiene warnings:")
        for issue in non_standalone + dirty_issues:
            print(f"  [WARN] {issue}")
    else:
        print("Cargo.lock hygiene: clean (all upstream bamabi dependencies resolve via GitHub git+https).")
    return 0


def cmd_status(root: Path, strict: bool) -> int:
    cfg_path = target_config_path(root)
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    strict_failed = False

    if not cfg_path.exists():
        print(f"Overlay config: DISABLED ({cfg_path} absent)")
    else:
        existing = cfg_path.read_text(encoding="utf-8")
        if MANAGED_HEADER in existing:
            if existing == template_text:
                print(f"Overlay config: ENABLED (managed, matches cargo-overlay.toml) at {cfg_path}")
            else:
                partial_text, present_count, total_count = build_partial_overlay_text(root)
                if present_count > 0 and existing == partial_text:
                    print(
                        f"Overlay config: ENABLED (managed, partial {present_count}/{total_count} crates) at {cfg_path}"
                    )
                else:
                    print(f"Overlay config: ENABLED (managed, DRIFTED from cargo-overlay.toml) at {cfg_path}")
                strict_failed = True
        else:
            print(f"Overlay config: PRESENT (unmanaged custom config) at {cfg_path}")
            strict_failed = True

    total_crates = len(load_overlay_crate_paths())
    missing = verify_local_crates_exist(root)
    if missing:
        if strict:
            print("Local crate paths: MISSING")
            for item in missing:
                print(f"  [ERROR] {item}")
            strict_failed = True
        else:
            present = total_crates - len(missing)
            if present == 0:
                print(f"Local crate paths: STANDALONE (0/{total_crates} sibling crates present under {root})")
            else:
                print(
                    f"Local crate paths: PARTIAL ({present}/{total_crates} sibling crates present; {len(missing)} absent)"
                )
                for item in missing:
                    print(f"  [INFO] absent: {item}")
    else:
        print(f"Local crate paths: OK (all {total_crates} crate directories verified)")

    non_standalone, dirty_issues = inspect_cargolock_hygiene(root)
    if non_standalone or dirty_issues:
        print("Cargo.lock hygiene: NON-STANDALONE / DIRTY")
        for issue in non_standalone + dirty_issues:
            print(f"  [WARN] {issue}")
        strict_failed = True
    else:
        print("Cargo.lock hygiene: CLEAN")

    if strict and strict_failed:
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Manage local multi-repo Cargo [patch] sibling overlay for bamabi."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for cmd_name in ("enable", "disable"):
        sub = subparsers.add_parser(cmd_name)
        sub.add_argument(
            "--root",
            type=Path,
            default=default_root,
            help=f"Federation root containing .cargo/ and bamabi-* repos (default: {default_root})",
        )
        sub.add_argument(
            "--force",
            action="store_true",
            help="Allow overwriting/removing unmanaged .cargo/config.toml or ignoring missing crates on enable.",
        )
        if cmd_name == "enable":
            sub.add_argument(
                "--partial",
                action="store_true",
                help="Write [patch] entries only for sibling crates present on disk.",
            )

    status_p = subparsers.add_parser("status")
    status_p.add_argument(
        "--root",
        type=Path,
        default=default_root,
        help=f"Federation root containing .cargo/ and bamabi-* repos (default: {default_root})",
    )
    status_p.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if Cargo.lock contains non-standalone/path-resolved upstream deps, dirty lockfiles, drifted config, or missing crates.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if args.command == "enable":
        return cmd_enable(root, force=args.force, partial=args.partial)
    if args.command == "disable":
        return cmd_disable(root, force=args.force)
    if args.command == "status":
        return cmd_status(root, strict=args.strict)
    return 2


if __name__ == "__main__":
    sys.exit(main())
