#!/usr/bin/env python3
"""Multi-repository consistency & standalone-readiness verifier for bamabi."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import tomllib

LAYERS: tuple[tuple[str, int], ...] = (
    ("bamabi-wire", 0),
    ("bamabi-tools", 1),
    ("bamabi-core", 2),
    ("bamabi", 3),
    ("bamabi-strata", 3),
    ("bamabi-showcase", 4),
)
LAYER_BY_NAME: dict[str, int] = dict(LAYERS)
REPO_DIRS: dict[str, str] = {
    "bamabi-strata": "strata",
}
OPTIONAL_REPOS: frozenset[str] = frozenset({"bamabi-strata"})
OVERLAY_REPO = "bamabi-dev-overlay"
ALL_REPOS: tuple[str, ...] = tuple(name for name, _ in LAYERS) + (OVERLAY_REPO,)

ABI_KEYS: tuple[str, ...] = (
    "bam_abi_version",
    "c_symbol_prefix",
    "workspace_version",
    "bevy_version",
    "rust_version",
    "edition",
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
    "strata_syntax": "bamabi-strata",
    "bamabi_native_rt": "bamabi-strata",
    "strata_sema": "bamabi-strata",
    "strata_mir": "bamabi-strata",
    "strata_codegen": "bamabi-strata",
    "strata_jit": "bamabi-strata",
    "strata_lsp": "bamabi-strata",
    "stratac": "bamabi-strata",
    "strata_docs": "bamabi-strata",
}

CANONICAL_GIT_URLS: dict[str, str] = {
    repo: f"https://github.com/yaga-simha/{repo}.git"
    for repo in ("bamabi-wire", "bamabi-tools", "bamabi-core", "bamabi", "bamabi-strata")
}

EXPECTED_LICENSE = "MIT OR Apache-2.0"
SKIP_DIRS = {".git", "target", ".zig-cache", "zig-out", "__pycache__"}
STALE_REF_RE = re.compile(r"\bbevy_mod_abi\b|\bbevy_abi_mod(?:_[A-Za-z0-9_]+)?\b")


class Reporter:
    def __init__(self) -> None:
        self.oks: list[str] = []
        self.warns: list[str] = []
        self.errors: list[str] = []

    def ok(self, msg: str) -> None:
        self.oks.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)


def resolve_repo_dir(root: Path, repo: str) -> Path:
    canonical = root / repo
    if canonical.is_dir():
        return canonical
    alt = REPO_DIRS.get(repo)
    if alt is not None:
        alt_dir = root / alt
        if alt_dir.is_dir():
            return alt_dir
    return canonical


def select_layers(
    root: Path, *, with_strata: bool = False, require_all: bool = False
) -> tuple[tuple[str, int], ...]:
    selected: list[tuple[str, int]] = []
    for repo, layer in LAYERS:
        if (
            repo in OPTIONAL_REPOS
            and not require_all
            and not (with_strata and repo == "bamabi-strata")
            and not resolve_repo_dir(root, repo).is_dir()
        ):
            continue
        selected.append((repo, layer))
    return tuple(selected)


def find_files(repo_dir: Path, predicate) -> list[Path]:
    results: list[Path] = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        root_path = Path(root)
        for fname in sorted(files):
            fpath = root_path / fname
            if predicate(fpath):
                results.append(fpath)
    return results


def load_toml(path: Path, reporter: Reporter) -> dict | None:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        reporter.error(f"Missing TOML file: {path}")
    except tomllib.TOMLDecodeError as exc:
        reporter.error(f"Invalid TOML in {path}: {exc}")
    return None


def check_abi_locks(
    root: Path,
    reporter: Reporter,
    layers: tuple[tuple[str, int], ...] = LAYERS,
) -> dict[str, str] | None:
    baseline: dict[str, str] | None = None
    baseline_repo: str | None = None
    all_valid = True

    for repo, expected_layer in layers:
        lock_path = resolve_repo_dir(root, repo) / "abi-lock.toml"
        data = load_toml(lock_path, reporter)
        if data is None:
            all_valid = False
            continue

        project = data.get("project")
        abi = data.get("abi")
        if not isinstance(project, dict) or not isinstance(abi, dict):
            reporter.error(f"{lock_path}: missing [project] or [abi] table")
            all_valid = False
            continue

        if project.get("name") != repo:
            reporter.error(
                f"{lock_path}: [project].name expected {repo!r}, got {project.get('name')!r}"
            )
            all_valid = False
        if project.get("layer") != expected_layer:
            reporter.error(
                f"{lock_path}: [project].layer expected {expected_layer}, got {project.get('layer')!r}"
            )
            all_valid = False

        values: dict[str, str] = {}
        missing_key = False
        for key in ABI_KEYS:
            val = abi.get(key)
            if not isinstance(val, str) or not val:
                reporter.error(f"{lock_path}: missing or non-string [abi].{key}")
                missing_key = True
                all_valid = False
            else:
                values[key] = val

        if missing_key:
            continue

        if baseline is None:
            baseline = values
            baseline_repo = repo
        else:
            for key in ABI_KEYS:
                if values[key] != baseline[key]:
                    reporter.error(
                        f"{lock_path}: [abi].{key} = {values[key]!r} differs from "
                        f"{baseline_repo} ({baseline[key]!r})"
                    )
                    all_valid = False

    if all_valid and baseline is not None:
        reporter.ok(
            f"abi-lock.toml parity verified across all {len(layers)} layer repos "
            f"(abi={baseline['bam_abi_version']}, version={baseline['workspace_version']}, "
            f"rust={baseline['rust_version']}, edition={baseline['edition']})"
        )
    return baseline


def check_license_files(
    root: Path,
    skip_overlay: bool,
    reporter: Reporter,
    layers: tuple[tuple[str, int], ...] = LAYERS,
) -> None:
    repos = [name for name, _ in layers]
    if not skip_overlay:
        repos.append(OVERLAY_REPO)
    missing_or_empty = False
    for repo in repos:
        repo_dir = resolve_repo_dir(root, repo)
        if not repo_dir.is_dir():
            reporter.error(f"Missing repository directory: {repo_dir}")
            missing_or_empty = True
            continue
        for fname in ("LICENSE-MIT", "LICENSE-APACHE"):
            fpath = repo_dir / fname
            if not fpath.is_file() or fpath.stat().st_size == 0:
                reporter.error(f"{repo}: missing or empty {fname}")
                missing_or_empty = True
    if not missing_or_empty:
        reporter.ok(
            f"LICENSE-MIT and LICENSE-APACHE present across all {len(repos)} checked repos"
        )


def resolve_pkg_field(pkg: dict, ws_pkg: dict, field: str):
    val = pkg.get(field)
    if isinstance(val, dict) and val.get("workspace") is True:
        return ws_pkg.get(field)
    return val


def iter_dependency_tables(manifest: dict):
    ws_deps = manifest.get("workspace", {}).get("dependencies")
    if isinstance(ws_deps, dict):
        yield "[workspace.dependencies]", ws_deps, True

    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        tbl = manifest.get(section)
        if isinstance(tbl, dict):
            yield f"[{section}]", tbl, False

    targets = manifest.get("target")
    if isinstance(targets, dict):
        for target_cfg, target_tbl in targets.items():
            if not isinstance(target_tbl, dict):
                continue
            for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                tbl = target_tbl.get(section)
                if isinstance(tbl, dict):
                    yield f"[target.{target_cfg}.{section}]", tbl, False


def check_repo_manifests_and_deps(
    root: Path,
    repo: str,
    layer: int,
    abi: dict[str, str] | None,
    strict_git: bool,
    reporter: Reporter,
) -> set[str]:
    repo_dir = resolve_repo_dir(root, repo)
    referenced_upstream_repos: set[str] = set()
    if not repo_dir.is_dir():
        return referenced_upstream_repos

    root_manifest_path = repo_dir / "Cargo.toml"
    root_manifest = load_toml(root_manifest_path, reporter)
    if root_manifest is None:
        return referenced_upstream_repos

    ws = root_manifest.get("workspace", {})
    ws_pkg = ws.get("package", {}) if isinstance(ws, dict) else {}
    ws_deps = ws.get("dependencies", {}) if isinstance(ws, dict) else {}
    raw_excludes = ws.get("exclude", []) if isinstance(ws, dict) else []
    ws_excludes = {
        e.strip("/") for e in raw_excludes if isinstance(e, str) and e.strip("/")
    }

    if isinstance(ws, dict) and ws:
        if not isinstance(ws_pkg, dict) or not ws_pkg:
            reporter.error(f"{root_manifest_path}: missing [workspace.package]")
        elif abi is not None:
            for field, abi_key in (
                ("version", "workspace_version"),
                ("edition", "edition"),
                ("rust-version", "rust_version"),
            ):
                actual = ws_pkg.get(field)
                expected = abi[abi_key]
                if actual != expected:
                    reporter.error(
                        f"{root_manifest_path}: [workspace.package].{field} expected {expected!r}, got {actual!r}"
                    )
            ws_license = ws_pkg.get("license")
            if ws_license != EXPECTED_LICENSE:
                reporter.error(
                    f"{root_manifest_path}: [workspace.package].license expected {EXPECTED_LICENSE!r}, got {ws_license!r}"
                )
            ws_repo = ws_pkg.get("repository")
            expected_repo_url = f"https://github.com/yaga-simha/{repo}"
            if not isinstance(ws_repo, str) or ws_repo.removesuffix(".git") != expected_repo_url:
                reporter.error(
                    f"{root_manifest_path}: [workspace.package].repository expected {expected_repo_url!r}, got {ws_repo!r}"
                )

    cargo_files = find_files(repo_dir, lambda p: p.name == "Cargo.toml")
    for manifest_path in cargo_files:
        manifest = (
            root_manifest
            if manifest_path == root_manifest_path
            else load_toml(manifest_path, reporter)
        )
        if manifest is None:
            continue

        rel_path = manifest_path.relative_to(root)
        for forbidden_section in ("patch", "replace"):
            if forbidden_section in manifest:
                reporter.error(
                    f"{rel_path}: tracked manifest must not contain [{forbidden_section}] overrides "
                    "(use bamabi-dev-overlay/cargo-overlay.toml / .cargo/config.toml instead)"
                )

        rel_to_repo = manifest_path.parent.relative_to(repo_dir).as_posix()
        is_excluded = rel_to_repo in ws_excludes
        if manifest_path != root_manifest_path and ("workspace" in manifest or is_excluded):
            sub_ws = manifest.get("workspace")
            if isinstance(sub_ws, dict):
                active_ws_pkg = (
                    sub_ws.get("package")
                    if isinstance(sub_ws.get("package"), dict)
                    else {}
                )
                active_ws_deps = (
                    sub_ws.get("dependencies")
                    if isinstance(sub_ws.get("dependencies"), dict)
                    else {}
                )
            else:
                active_ws_pkg = {}
                active_ws_deps = {}
            ws_source_label = str(rel_path)
        else:
            active_ws_pkg = ws_pkg
            active_ws_deps = ws_deps
            ws_source_label = f"{repo_dir.name}/Cargo.toml"

        pkg = manifest.get("package")
        if isinstance(pkg, dict):
            if abi is not None:
                pkg_version = resolve_pkg_field(pkg, active_ws_pkg, "version")
                if pkg_version != abi["workspace_version"]:
                    reporter.error(
                        f"{rel_path}: [package].version expected {abi['workspace_version']!r}, got {pkg_version!r}"
                    )
                pkg_edition = resolve_pkg_field(pkg, active_ws_pkg, "edition")
                if pkg_edition != abi["edition"]:
                    reporter.error(
                        f"{rel_path}: [package].edition expected {abi['edition']!r}, got {pkg_edition!r}"
                    )

            pkg_rust_version = pkg.get("rust-version")
            if (
                isinstance(pkg_rust_version, dict)
                and pkg_rust_version.get("workspace") is True
                and "rust-version" not in active_ws_pkg
            ):
                reporter.error(
                    f"{rel_path}: [package].rust-version uses workspace = true, "
                    f"but not defined in {ws_source_label} [workspace.package]"
                )
            resolved_rv = resolve_pkg_field(pkg, active_ws_pkg, "rust-version")
            if resolved_rv is not None and resolved_rv not in {"1.87", "1.95"}:
                reporter.error(
                    f"{rel_path}: [package].rust-version expected '1.87' or '1.95', got {resolved_rv!r}"
                )

            pkg_license = resolve_pkg_field(pkg, active_ws_pkg, "license")
            if pkg_license != EXPECTED_LICENSE:
                reporter.error(
                    f"{rel_path}: [package].license expected {EXPECTED_LICENSE!r}, got {pkg_license!r}"
                )

        for section_name, deps_tbl, is_ws_deps in iter_dependency_tables(manifest):
            for dep_key, dep_spec in deps_tbl.items():
                crate_name = (
                    dep_spec.get("package", dep_key)
                    if isinstance(dep_spec, dict)
                    else dep_key
                )
                owner_repo = CRATE_REPO.get(crate_name)
                if owner_repo is None or owner_repo == repo:
                    continue

                referenced_upstream_repos.add(owner_repo)
                owner_layer = LAYER_BY_NAME[owner_repo]
                if owner_layer >= layer:
                    reporter.error(
                        f"{rel_path} {section_name}.{dep_key}: layer violation — "
                        f"{repo} (L{layer}) depends on {crate_name} in {owner_repo} (L{owner_layer})"
                    )
                    continue

                if isinstance(dep_spec, dict) and dep_spec.get("workspace") is True:
                    if is_ws_deps:
                        reporter.error(
                            f"{rel_path} {section_name}.{dep_key}: workspace = true inside [workspace.dependencies]"
                        )
                    elif dep_key not in active_ws_deps and crate_name not in active_ws_deps:
                        reporter.error(
                            f"{rel_path} {section_name}.{dep_key}: workspace = true, "
                            f"but not defined in {ws_source_label} [workspace.dependencies]"
                        )
                    continue

                if isinstance(dep_spec, dict) and "path" in dep_spec:
                    dep_path = dep_spec["path"]
                    resolved = (manifest_path.parent / dep_path).resolve()
                    expected_prefix = resolve_repo_dir(root, owner_repo).resolve()
                    try:
                        resolved.relative_to(expected_prefix)
                    except ValueError:
                        reporter.error(
                            f"{rel_path} {section_name}.{dep_key}: path {dep_path!r} does not resolve inside {owner_repo}"
                        )
                    msg = (
                        f"{rel_path} {section_name}.{dep_key}: cross-repo local path dependency "
                        f"{dep_path!r} -> {owner_repo}"
                    )
                    if strict_git:
                        reporter.error(msg + " (forbidden under --strict-git)")
                    else:
                        reporter.warn("PRE-M6 PATH DEP: " + msg)
                    continue

                if isinstance(dep_spec, dict) and "git" in dep_spec:
                    expected_git = CANONICAL_GIT_URLS[owner_repo]
                    actual_git = dep_spec.get("git")
                    actual_branch = dep_spec.get("branch")
                    if actual_git != expected_git:
                        reporter.error(
                            f"{rel_path} {section_name}.{dep_key}: git URL expected {expected_git!r}, got {actual_git!r}"
                        )
                    if actual_branch != "main":
                        reporter.error(
                            f"{rel_path} {section_name}.{dep_key}: git dependency must specify branch = \"main\", got {actual_branch!r}"
                        )
                    if "rev" in dep_spec or "tag" in dep_spec:
                        conflicting = ", ".join(k for k in ("rev", "tag") if k in dep_spec)
                        reporter.error(
                            f"{rel_path} {section_name}.{dep_key}: git dependency must not specify {conflicting} alongside branch = \"main\""
                        )
                    continue

                msg = (
                    f"{rel_path} {section_name}.{dep_key}: cross-repo dependency on {crate_name} ({owner_repo}) "
                    "lacks git/path source"
                )
                if strict_git:
                    reporter.error(msg)
                else:
                    reporter.warn("PRE-M6 BARE DEP: " + msg)

    return referenced_upstream_repos


def check_deny_toml(
    root: Path,
    repo: str,
    layer: int,
    referenced_upstream_repos: set[str],
    strict_git: bool,
    reporter: Reporter,
    layers: tuple[tuple[str, int], ...] = LAYERS,
) -> None:
    deny_path = resolve_repo_dir(root, repo) / "deny.toml"
    deny_data = load_toml(deny_path, reporter)
    if deny_data is None:
        return

    sources = deny_data.get("sources")
    if not isinstance(sources, dict):
        reporter.error(f"{deny_path}: missing [sources] table")
        return

    if sources.get("unknown-registry") != "deny":
        reporter.error(f"{deny_path}: [sources].unknown-registry must be \"deny\"")
    if sources.get("unknown-git") != "deny":
        reporter.error(f"{deny_path}: [sources].unknown-git must be \"deny\"")

    if layer == 0:
        return

    allow_org = sources.get("allow-org", {})
    github_orgs = allow_org.get("github", []) if isinstance(allow_org, dict) else []
    allow_git = sources.get("allow-git", [])
    allow_git_norm = {
        u.removesuffix(".git") for u in allow_git if isinstance(u, str)
    }

    has_org = isinstance(github_orgs, list) and "yaga-simha" in github_orgs
    needed_repos = referenced_upstream_repos or {
        name for name, lyr in layers if lyr < layer
    }
    missing_urls = [
        CANONICAL_GIT_URLS[r]
        for r in sorted(needed_repos)
        if CANONICAL_GIT_URLS[r].removesuffix(".git") not in allow_git_norm
    ]

    if not has_org and missing_urls:
        msg = (
            f"{deny_path}: lacks [sources.allow-org] github = [\"yaga-simha\"] "
            f"or allow-git entries for {missing_urls}"
        )
        if strict_git:
            reporter.error(msg)
        else:
            reporter.warn("PRE-M6 DENY.TOML: " + msg)


def check_stale_refs(
    root: Path,
    reporter: Reporter,
    layers: tuple[tuple[str, int], ...] = LAYERS,
) -> None:
    found_stale = False
    for repo, _ in layers:
        repo_dir = resolve_repo_dir(root, repo)
        if not repo_dir.is_dir():
            continue

        def is_target_file(p: Path) -> bool:
            if p.name in {"Cargo.toml", "abi-lock.toml", "deny.toml", "Makefile", "build.zig"}:
                return True
            rel_parts = p.relative_to(repo_dir).parts
            if len(rel_parts) >= 3 and rel_parts[:2] == (".github", "workflows") and p.suffix in {".yml", ".yaml"}:
                return True
            return False

        for fpath in find_files(repo_dir, is_target_file):
            try:
                content = fpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                match = STALE_REF_RE.search(line)
                if match:
                    reporter.error(
                        f"{fpath.relative_to(root)}:{lineno}: stale monorepo/crate reference {match.group(0)!r}"
                    )
                    found_stale = True

    if not found_stale:
        reporter.ok("No stale `bevy_mod_abi` / `bevy_abi_mod*` references in manifests, CI, Makefiles, or build.zig")


def run_checks(
    root: Path,
    strict_git: bool,
    skip_overlay: bool,
    *,
    with_strata: bool = False,
    require_all: bool = False,
) -> Reporter:
    reporter = Reporter()
    layers = select_layers(root, with_strata=with_strata, require_all=require_all)
    abi = check_abi_locks(root, reporter, layers)
    check_license_files(root, skip_overlay, reporter, layers)

    for repo, layer in layers:
        refs = check_repo_manifests_and_deps(root, repo, layer, abi, strict_git, reporter)
        check_deny_toml(root, repo, layer, refs, strict_git, reporter, layers)

    check_stale_refs(root, reporter, layers)
    return reporter


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Verify ABI, version, license, dependency, and reference consistency across bamabi repos."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root,
        help=f"Federation root containing bamabi-* repos (default: {default_root})",
    )
    parser.add_argument(
        "--strict-git",
        action="store_true",
        help="Enforce canonical GitHub git dependencies (no cross-repo path deps) and deny.toml yaga-simha allowlist.",
    )
    parser.add_argument(
        "--skip-overlay-repo",
        action="store_true",
        help="Do not require bamabi-dev-overlay LICENSE-* files under --root.",
    )
    parser.add_argument(
        "--with-strata",
        action="store_true",
        help="Require optional bamabi-strata (strata/ or bamabi-strata/) repository to be present under --root.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Require all layer repositories (including optional ones like bamabi-strata) under --root.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    mode = "strict-git" if args.strict_git else "pre-m6-default"
    print(f"bamabi sync_check.py (root={root}, mode={mode})")

    reporter = run_checks(
        root,
        strict_git=args.strict_git,
        skip_overlay=args.skip_overlay_repo,
        with_strata=args.with_strata,
        require_all=args.require_all,
    )

    for item in reporter.oks:
        print(f"  [OK]    {item}")
    for item in reporter.warns:
        print(f"  [WARN]  {item}")
    for item in reporter.errors:
        print(f"  [ERROR] {item}")

    print(
        f"Summary: {len(reporter.oks)} ok, {len(reporter.warns)} warning(s), {len(reporter.errors)} error(s)"
    )
    return 0 if not reporter.errors else 1


if __name__ == "__main__":
    sys.exit(main())
