#!/usr/bin/env python3
"""Unit tests for bamabi-dev-overlay (`sync_check.py`, `overlay.py`, `cargo-overlay.toml`)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
import unittest

OVERLAY_DIR = Path(__file__).resolve().parent.parent
if str(OVERLAY_DIR) not in sys.path:
    sys.path.insert(0, str(OVERLAY_DIR))

import overlay  # noqa: E402
import sync_check  # noqa: E402


REPO_CRATES: dict[str, list[str]] = {
    "bamabi-wire": [
        "bamabi_sys",
        "bamabi_macros",
        "bamabi_sdk_gen",
        "bamabi_guest_sys",
        "bamabi_guest",
    ],
    "bamabi-tools": [
        "bamabi_trust",
        "bamabi_manifest",
        "cargo-bam",
    ],
    "bamabi-core": [
        "bamabi_host_sys",
        "bamabi_host",
        "bamabi_watcher",
    ],
    "bamabi": [
        "bamabi_bridges",
        "bamabi_render",
        "bamabi_reflect",
        "bamabi",
    ],
}

LAYERS = (
    ("bamabi-wire", 0),
    ("bamabi-tools", 1),
    ("bamabi-core", 2),
    ("bamabi", 3),
    ("bamabi-showcase", 4),
)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_valid_fixture(root: Path, *, strict_git: bool = False, deny_mode: str = "allow_org") -> None:
    for repo, layer in LAYERS:
        repo_dir = root / repo
        repo_dir.mkdir(parents=True, exist_ok=True)
        write_file(repo_dir / "LICENSE-MIT", "MIT License\n")
        write_file(repo_dir / "LICENSE-APACHE", "Apache License 2.0\n")
        write_file(
            repo_dir / "abi-lock.toml",
            f"""[project]
name = "{repo}"
layer = {layer}

[abi]
bam_abi_version = "0x0003_0000"
c_symbol_prefix = "bamabi"
workspace_version = "0.3.0"
bevy_version = "0.20.1"
rust_version = "1.95"
edition = "2024"
""",
        )

        if deny_mode == "allow_org" and strict_git:
            sources_block = """[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
allow-git = []

[sources.allow-org]
github = ["yaga-simha"]
"""
        elif deny_mode == "allow_git" and strict_git:
            urls = ", ".join(
                f'"{sync_check.CANONICAL_GIT_URLS[r]}"'
                for r, lyr in LAYERS
                if lyr < layer
            )
            sources_block = f"""[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
allow-git = [{urls}]
"""
        else:
            sources_block = """[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
allow-git = []
"""
        write_file(repo_dir / "deny.toml", sources_block)

        crates = REPO_CRATES.get(repo, [])
        members_list = ", ".join(f'"crates/{c}"' for c in crates)
        if repo == "bamabi-showcase":
            members_list = '"xtask"'
            write_file(
                repo_dir / "xtask" / "Cargo.toml",
                """[package]
name = "xtask"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true

[dependencies]
bamabi_sys = { workspace = true }
bamabi = { workspace = true }
""",
            )
            write_file(repo_dir / "xtask" / "src" / "main.rs", "fn main() {}\n")

        ws_deps_lines: list[str] = []
        if layer >= 1:
            if strict_git:
                ws_deps_lines.append(
                    'bamabi_sys = { version = "0.3.0", git = "https://github.com/yaga-simha/bamabi-wire.git", branch = "main" }'
                )
            else:
                ws_deps_lines.append(
                    'bamabi_sys = { version = "0.3.0", path = "../bamabi-wire/crates/bamabi_sys" }'
                )
        if layer >= 2:
            if strict_git:
                ws_deps_lines.append(
                    'bamabi_trust = { version = "0.3.0", git = "https://github.com/yaga-simha/bamabi-tools.git", branch = "main" }'
                )
            else:
                ws_deps_lines.append(
                    'bamabi_trust = { version = "0.3.0", path = "../bamabi-tools/crates/bamabi_trust" }'
                )
        if layer >= 3:
            if strict_git:
                ws_deps_lines.append(
                    'bamabi_host = { version = "0.3.0", git = "https://github.com/yaga-simha/bamabi-core.git", branch = "main" }'
                )
            else:
                ws_deps_lines.append(
                    'bamabi_host = { version = "0.3.0", path = "../bamabi-core/crates/bamabi_host" }'
                )
        if layer >= 4:
            if strict_git:
                ws_deps_lines.append(
                    'bamabi = { version = "0.3.0", git = "https://github.com/yaga-simha/bamabi.git", branch = "main" }'
                )
            else:
                ws_deps_lines.append(
                    'bamabi = { version = "0.3.0", path = "../bamabi/crates/bamabi" }'
                )

        ws_deps_str = "\n".join(ws_deps_lines)
        exclude_block = ""
        if repo == "bamabi-showcase":
            exclude_block = 'exclude = ["examples/01_minimal/guest_mod"]\n'
            guest_dep = (
                'bamabi_guest = { git = "https://github.com/yaga-simha/bamabi-wire.git", branch = "main" }'
                if strict_git
                else 'bamabi_guest = { path = "../../../../bamabi-wire/crates/bamabi_guest" }'
            )
            write_file(
                repo_dir / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml",
                f"""[package]
name = "minimal_guest_mod"
version = "0.3.0"
edition = "2024"
license = "MIT OR Apache-2.0"

[workspace]

[dependencies]
{guest_dep}
""",
            )

        write_file(
            repo_dir / "Cargo.toml",
            f"""[workspace]
resolver = "2"
members = [{members_list}]
{exclude_block}
[workspace.package]
version = "0.3.0"
edition = "2024"
rust-version = "1.95"
license = "MIT OR Apache-2.0"
repository = "https://github.com/yaga-simha/{repo}"

[workspace.dependencies]
{ws_deps_str}
""",
        )

        for crate in crates:
            crate_dir = repo_dir / "crates" / crate
            write_file(
                crate_dir / "Cargo.toml",
                f"""[package]
name = "{crate}"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true
""",
            )
            write_file(crate_dir / "src" / "lib.rs", "")

    overlay_dir = root / "bamabi-dev-overlay"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    write_file(overlay_dir / "LICENSE-MIT", "MIT License\n")
    write_file(overlay_dir / "LICENSE-APACHE", "Apache License 2.0\n")


class OverlayAndSyncCheckTests(unittest.TestCase):
    def test_sync_check_valid_pre_m6_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=False)
            self.assertEqual(sync_check.main(["--root", str(root)]), 0)
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

    def test_sync_check_valid_strict_git_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True, deny_mode="allow_org")
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True, deny_mode="allow_git")
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 0)

    def test_sync_check_abi_lock_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=False)
            lock_path = root / "bamabi-core" / "abi-lock.toml"
            lock_path.write_text(
                lock_path.read_text(encoding="utf-8").replace("0x0003_0000", "0x0004_0000"),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=False)
            lock_path = root / "bamabi" / "abi-lock.toml"
            lock_path.write_text(
                lock_path.read_text(encoding="utf-8").replace("layer = 3", "layer = 9"),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)

    def test_sync_check_missing_license_files_and_manifest_license(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=False)
            (root / "bamabi-dev-overlay" / "LICENSE-APACHE").unlink()
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=False)
            excluded = root / "bamabi-showcase" / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml"
            excluded.write_text(
                excluded.read_text(encoding="utf-8").replace('license = "MIT OR Apache-2.0"\n', ""),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)

    def test_sync_check_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=False)
            excluded = root / "bamabi-showcase" / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml"
            excluded.write_text(
                excluded.read_text(encoding="utf-8").replace('version = "0.3.0"', 'version = "0.2.0"'),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)

    def test_sync_check_stale_monorepo_refs_vs_readme_prose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=False)
            write_file(
                root / "bamabi-wire" / "README.md",
                "Refactored from https://github.com/yaga-simha/bevy_mod_abi and bevy_abi_mod_sys.\n",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 0)

            write_file(
                root / "bamabi-wire" / ".github" / "workflows" / "ci.yml",
                "name: ci\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo test -p bevy_abi_mod_sys\n",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)

    def test_sync_check_strict_git_failures(self) -> None:
        # 1) Excluded sub-crate still uses path = "../..."
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            excluded = root / "bamabi-showcase" / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml"
            excluded.write_text(
                excluded.read_text(encoding="utf-8").replace(
                    'git = "https://github.com/yaga-simha/bamabi-wire.git", branch = "main"',
                    'path = "../../../../bamabi-wire/crates/bamabi_guest"',
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # 2) Git dep missing branch = "main" or missing .git suffix
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            tools_manifest = root / "bamabi-tools" / "Cargo.toml"
            tools_manifest.write_text(
                tools_manifest.read_text(encoding="utf-8").replace(', branch = "main"', ""),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            tools_manifest = root / "bamabi-tools" / "Cargo.toml"
            tools_manifest.write_text(
                tools_manifest.read_text(encoding="utf-8").replace("bamabi-wire.git", "bamabi-wire"),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # 3) deny.toml lacking allow-org/allow-git
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True, deny_mode="none")
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # 4) [target.*.dev-dependencies] cross-repo path dep caught under --strict-git
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            xtask_manifest = root / "bamabi-showcase" / "xtask" / "Cargo.toml"
            xtask_manifest.write_text(
                xtask_manifest.read_text(encoding="utf-8")
                + '\n[target.\'cfg(target_os = "linux")\'.dev-dependencies]\n'
                + 'bamabi_host = { path = "../../bamabi-core/crates/bamabi_host" }\n',
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # 5) Git dep with both branch = "main" and rev/tag rejected
        for extra_field in ('rev = "0123456789abcdef"', 'tag = "v0.3.0"'):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                create_valid_fixture(root, strict_git=True)
                tools_manifest = root / "bamabi-tools" / "Cargo.toml"
                tools_manifest.write_text(
                    tools_manifest.read_text(encoding="utf-8").replace(
                        'branch = "main" }',
                        f'branch = "main", {extra_field} }}',
                    ),
                    encoding="utf-8",
                )
                self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

    def test_sync_check_excluded_subcrate_workspace_isolation(self) -> None:
        # Excluded sub-crate with [workspace] and version.workspace = true without own [workspace.package]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            excluded = root / "bamabi-showcase" / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml"
            excluded.write_text(
                excluded.read_text(encoding="utf-8").replace(
                    'version = "0.3.0"',
                    "version.workspace = true",
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # Excluded sub-crate with [workspace] and workspace = true dep without own [workspace.dependencies]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            excluded = root / "bamabi-showcase" / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml"
            excluded.write_text(
                excluded.read_text(encoding="utf-8").replace(
                    'bamabi_guest = { git = "https://github.com/yaga-simha/bamabi-wire.git", branch = "main" }',
                    "bamabi_guest = { workspace = true }",
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # Excluded sub-crate defining its own [workspace.package] and [workspace.dependencies] passes
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            excluded = root / "bamabi-showcase" / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml"
            write_file(
                excluded,
                """[package]
name = "minimal_guest_mod"
version.workspace = true
edition.workspace = true
license.workspace = true

[workspace]

[workspace.package]
version = "0.3.0"
edition = "2024"
license = "MIT OR Apache-2.0"

[workspace.dependencies]
bamabi_guest = { git = "https://github.com/yaga-simha/bamabi-wire.git", branch = "main" }

[dependencies]
bamabi_guest = { workspace = true }
""",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 0)

    def test_sync_check_rejects_tracked_patch_and_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            tools_manifest = root / "bamabi-tools" / "Cargo.toml"
            tools_manifest.write_text(
                tools_manifest.read_text(encoding="utf-8")
                + '\n[patch."https://github.com/yaga-simha/bamabi-wire.git"]\n'
                + 'bamabi_sys = { path = "../bamabi-wire/crates/bamabi_sys" }\n',
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            xtask_manifest = root / "bamabi-showcase" / "xtask" / "Cargo.toml"
            xtask_manifest.write_text(
                xtask_manifest.read_text(encoding="utf-8")
                + '\n[replace]\n'
                + '"bamabi_sys:0.3.0" = { path = "../../bamabi-wire/crates/bamabi_sys" }\n',
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root)]), 1)
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

    def test_overlay_enable_status_disable_and_safety_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)

            self.assertEqual(overlay.main(["status", "--root", str(root)]), 0)
            self.assertFalse((root / ".cargo" / "config.toml").exists())

            self.assertEqual(overlay.main(["enable", "--root", str(root)]), 0)
            cfg = root / ".cargo" / "config.toml"
            self.assertTrue(cfg.is_file())
            self.assertIn(overlay.MANAGED_HEADER, cfg.read_text(encoding="utf-8"))
            self.assertEqual(overlay.main(["status", "--root", str(root), "--strict"]), 0)

            self.assertEqual(overlay.main(["disable", "--root", str(root)]), 0)
            self.assertFalse(cfg.exists())
            self.assertFalse((root / ".cargo").exists())

            # Unmanaged user .cargo/config.toml protection
            write_file(cfg, "[build]\njobs = 4\n")
            self.assertEqual(overlay.main(["enable", "--root", str(root)]), 1)
            self.assertIn("jobs = 4", cfg.read_text(encoding="utf-8"))
            self.assertEqual(overlay.main(["disable", "--root", str(root)]), 1)
            self.assertTrue(cfg.is_file())

            # --force overrides safety guard
            self.assertEqual(overlay.main(["enable", "--root", str(root), "--force"]), 0)
            self.assertIn(overlay.MANAGED_HEADER, cfg.read_text(encoding="utf-8"))
            self.assertEqual(overlay.main(["disable", "--root", str(root)]), 0)
            self.assertFalse(cfg.exists())

    def test_overlay_cargolock_hygiene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            lock_path = root / "bamabi-tools" / "Cargo.lock"

            # Path-resolved / patched lockfile lacking git+https source
            write_file(
                lock_path,
                """version = 4

[[package]]
name = "bamabi_sys"
version = "0.3.0"
""",
            )
            self.assertEqual(overlay.main(["status", "--root", str(root), "--strict"]), 1)

            # Reject wrong repo, missing .git suffix, or pinned ?rev= instead of ?branch=main#
            for bad_source in (
                "git+https://github.com/yaga-simha/bamabi-WRONG.git?branch=main#abc",
                "git+https://github.com/yaga-simha/bamabi-wire?branch=main#abc",
                "git+https://github.com/yaga-simha/bamabi-wire.git?rev=deadbeef#abc",
            ):
                write_file(
                    lock_path,
                    f"""version = 4

[[package]]
name = "bamabi_sys"
version = "0.3.0"
source = "{bad_source}"
""",
                )
                self.assertEqual(
                    overlay.main(["status", "--root", str(root), "--strict"]),
                    1,
                    msg=f"expected failure for {bad_source}",
                )

            # Standalone git-resolved lockfile
            write_file(
                lock_path,
                """version = 4

[[package]]
name = "bamabi_sys"
version = "0.3.0"
source = "git+https://github.com/yaga-simha/bamabi-wire.git?branch=main#abc"
""",
            )
            self.assertEqual(overlay.main(["status", "--root", str(root), "--strict"]), 0)

    def test_repo_cargo_overlay_toml_matches_15_crates(self) -> None:
        overlay_toml = OVERLAY_DIR / "cargo-overlay.toml"
        with overlay_toml.open("rb") as f:
            data = tomllib.load(f)

        patch = data.get("patch", {})
        expected_urls = {
            "https://github.com/yaga-simha/bamabi-wire.git",
            "https://github.com/yaga-simha/bamabi-tools.git",
            "https://github.com/yaga-simha/bamabi-core.git",
            "https://github.com/yaga-simha/bamabi.git",
        }
        self.assertEqual(set(patch.keys()), expected_urls)

        seen_crates: dict[str, str] = {}
        for url, crates in patch.items():
            repo_name = url.rsplit("/", 1)[-1].removesuffix(".git")
            for crate_name, spec in crates.items():
                self.assertEqual(spec["path"], f"{repo_name}/crates/{crate_name}")
                seen_crates[crate_name] = repo_name

        self.assertEqual(len(seen_crates), 15)
        self.assertIn("cargo-bam", seen_crates)
        self.assertEqual(seen_crates, overlay.CRATE_REPO)

    def test_overlay_partial_enable_and_nonstrict_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            # Remove bamabi-core and bamabi to simulate a partial sibling checkout
            shutil.rmtree(root / "bamabi-core")
            shutil.rmtree(root / "bamabi")

            # Strict enable refuses missing siblings
            self.assertEqual(overlay.main(["enable", "--root", str(root)]), 1)
            self.assertFalse((root / ".cargo" / "config.toml").exists())

            # Partial enable writes only present crates (8/15: wire + tools)
            self.assertEqual(overlay.main(["enable", "--partial", "--root", str(root)]), 0)
            cfg = root / ".cargo" / "config.toml"
            self.assertTrue(cfg.is_file())
            cfg_data = tomllib.loads(cfg.read_text(encoding="utf-8"))
            self.assertEqual(
                set(cfg_data["patch"].keys()),
                {
                    "https://github.com/yaga-simha/bamabi-wire.git",
                    "https://github.com/yaga-simha/bamabi-tools.git",
                },
            )

            # Non-strict status reports PARTIAL without [ERROR] and exits 0; --strict exits 1
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = overlay.main(["status", "--root", str(root)])
            out = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("PARTIAL", out)
            self.assertNotIn("[ERROR]", out)
            self.assertEqual(overlay.main(["status", "--root", str(root), "--strict"]), 1)

            # Disable and remove remaining repos -> STANDALONE non-strict status
            self.assertEqual(overlay.main(["disable", "--root", str(root)]), 0)
            shutil.rmtree(root / "bamabi-wire")
            shutil.rmtree(root / "bamabi-tools")
            self.assertEqual(overlay.main(["enable", "--partial", "--root", str(root)]), 1)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = overlay.main(["status", "--root", str(root)])
            self.assertEqual(rc, 0)
            self.assertIn("STANDALONE", buf.getvalue())
            self.assertNotIn("[ERROR]", buf.getvalue())

        # Partial enable with all 15 crates present produces exact cargo-overlay.toml
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            self.assertEqual(overlay.main(["enable", "--partial", "--root", str(root)]), 0)
            self.assertEqual(overlay.main(["status", "--root", str(root), "--strict"]), 0)

    def test_sync_check_excluded_no_workspace_table_repo_and_rust_version(self) -> None:
        # 1) Excluded crate without [workspace] table cannot use workspace = true
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            shared_dir = root / "bamabi-showcase" / "benches" / "shared_scenario"
            write_file(
                shared_dir / "Cargo.toml",
                """[package]
name = "shared_scenario"
version.workspace = true
edition = "2024"
license = "MIT OR Apache-2.0"
""",
            )
            root_manifest = root / "bamabi-showcase" / "Cargo.toml"
            root_manifest.write_text(
                root_manifest.read_text(encoding="utf-8").replace(
                    'exclude = ["examples/01_minimal/guest_mod"]',
                    'exclude = ["examples/01_minimal/guest_mod", "benches/shared_scenario"]',
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # 2) Missing or mismatched [workspace.package].repository is rejected
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            tools_manifest = root / "bamabi-tools" / "Cargo.toml"
            tools_manifest.write_text(
                tools_manifest.read_text(encoding="utf-8").replace(
                    'repository = "https://github.com/yaga-simha/bamabi-tools"\n',
                    "",
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)

        # 3) Disallowed literal rust-version is rejected; 1.87 is allowed
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_valid_fixture(root, strict_git=True)
            excluded = root / "bamabi-showcase" / "examples" / "01_minimal" / "guest_mod" / "Cargo.toml"
            excluded.write_text(
                excluded.read_text(encoding="utf-8").replace(
                    'edition = "2024"',
                    'edition = "2024"\nrust-version = "1.87"',
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 0)

            excluded.write_text(
                excluded.read_text(encoding="utf-8").replace(
                    'rust-version = "1.87"',
                    'rust-version = "1.80"',
                ),
                encoding="utf-8",
            )
            self.assertEqual(sync_check.main(["--root", str(root), "--strict-git"]), 1)


if __name__ == "__main__":
    unittest.main()
