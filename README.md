# `bamabi-dev-overlay`

Developer coordination, cross-repository consistency verification (`sync_check.py`), and local Cargo `[patch]` sibling overlay management (`overlay.py` + `cargo-overlay.toml`) for the federated **`bamabi`** (`ABI 0.3.0`, `v0.3.0`, Bevy `v0.20.1`) multi-repository ecosystem.

## Architecture (6 Layered Repositories + Overlay)

Refactored from the original [`bevy_mod_abi`](https://github.com/yaga-simha/bevy_mod_abi) monorepo into a strictly acyclic DAG across 6 layer repositories (5 core + `bamabi-strata`) plus this coordination repository:

| Layer | Repository | Local Dir | GitHub URL | Role |
|---|---|---|---|---|
| **0** | `bamabi-wire` | `bamabi-wire/` | `https://github.com/yaga-simha/bamabi-wire.git` | Zero-Bevy ABI wire contract, derives, polyglot headers (`bamabi.h`), and Rust guest SDK (`bamabi_sys`, `bamabi_macros`, `bamabi_sdk_gen`, `bamabi_guest_sys`, `bamabi_guest`) |
| **1** | `bamabi-tools` | `bamabi-tools/` | `https://github.com/yaga-simha/bamabi-tools.git` | Zero-Bevy Ed25519 trust (`bamabi_trust`), manifest DAG (`bamabi_manifest`), and `cargo-bam` CLI |
| **2** | `bamabi-core` | `bamabi-core/` | `https://github.com/yaga-simha/bamabi-core.git` | Headless `bevy_ecs` + `bevy_app` host runtime (`bamabi_host_sys`, `bamabi_host`, `bamabi_watcher`) and `docs/ARCHITECTURE.md` |
| **3** | `bamabi` | `bamabi/` | `https://github.com/yaga-simha/bamabi.git` | **Canonical host library facade** and Bevy `0.20.1` companion bridges/render/reflect crates (`bamabi_bridges`, `bamabi_render`, `bamabi_reflect`, `bamabi`) |
| **3** | `bamabi-strata` *(optional)* | `strata/` (or `bamabi-strata/`) | `https://github.com/yaga-simha/bamabi-strata.git` | **Strata DSL compiler & native runtime** (`strata_syntax`, `strata_sema`, `strata_mir`, `strata_codegen`, `strata_jit`, `strata_lsp`, `stratac`, `bamabi_native_rt`, `strata_docs`); peer to `bamabi` (may depend on L0–L2, never on `bamabi` L3 or `bamabi-showcase` L4) |
| **4** | `bamabi-showcase` | `bamabi-showcase/` | `https://github.com/yaga-simha/bamabi-showcase.git` | **Top-level integration repository**: `xtask`, runnable examples (`01`–`10`), benchmarks (`docs/BENCHMARKS.md`), fuzz targets, wire-contract tests, and mdBook (`docs/book/`) |
| **Overlay** | **`bamabi-dev-overlay`** *(this repo)* | `bamabi-dev-overlay/` | `https://github.com/yaga-simha/bamabi-dev-overlay.git` | Cross-repo consistency verifier (`sync_check.py`) and local sibling `[patch]` overlay manager (`overlay.py`) |

## Standalone vs. Local Sibling `[patch]` Workflow

Each Layer 1–4 repository is configured to build and pass CI **standalone** by resolving upstream layers via canonical GitHub `git` URLs (`https://github.com/yaga-simha/<repo>.git`, `branch = "main"`).

When developing across multiple sibling repositories locally under a common parent directory (e.g., `<federation-root>/bamabi-*`):

1. **Enable the local sibling `[patch]` overlay** (writes `<root>/.cargo/config.toml` from `cargo-overlay.toml` without modifying any tracked `Cargo.toml` inside the layer repos):
   ```bash
   # Require all 15 sibling crates across bamabi-{wire,tools,core} and bamabi:
   python3 bamabi-dev-overlay/overlay.py enable

   # Or patch only the sibling crates currently checked out on disk:
   python3 bamabi-dev-overlay/overlay.py enable --partial
   ```
2. **Check status & `Cargo.lock` hygiene**:
   ```bash
   python3 bamabi-dev-overlay/overlay.py status
   python3 bamabi-dev-overlay/overlay.py status --strict
   ```
3. **Disable the overlay before committing or verifying standalone builds**:
   ```bash
   python3 bamabi-dev-overlay/overlay.py disable
   ```

> **Important (`Cargo.lock` Hygiene):** When `[patch]` is active, Cargo strips `source = "git+https://github.com/yaga-simha/..."` from patched entries in `Cargo.lock`. Never commit `Cargo.lock` diffs generated while the overlay is enabled; run `overlay.py disable` and ensure tracked `Cargo.lock` files (including `strata/Cargo.lock` when present) retain their `git+https://` sources (`overlay.py status --strict` checks this automatically).

## Consistency Verification (`sync_check.py`)

Requires Python 3.11+ (standard library only; zero third-party dependencies) and the 5 core layer repositories (`bamabi-wire`, `bamabi-tools`, `bamabi-core`, `bamabi`, `bamabi-showcase`) present under `--root`. `bamabi-strata` (`strata/` or `bamabi-strata/`) is automatically checked whenever present on disk, and can be strictly required via `--with-strata` or `--require-all`.

```bash
# Pre-M6 / default check: validates abi-lock.toml parity, versions, editions,
# rust-version, dual MIT/Apache-2.0 licenses, and stale monorepo references;
# reports cross-repo `path = "../..."` deps as warnings.
python3 bamabi-dev-overlay/sync_check.py

# Strict standalone Git check (post-M6): fails on any cross-repo `path` dep,
# missing `branch = "main"`, missing `.git` suffix, or missing `yaga-simha`
# allowlist in `deny.toml`.
python3 bamabi-dev-overlay/sync_check.py --strict-git

# Require optional `bamabi-strata` (`strata/` or `bamabi-strata/`) to be present:
python3 bamabi-dev-overlay/sync_check.py --strict-git --with-strata
```

### What `sync_check.py` Validates
- **`abi-lock.toml` parity** across `bamabi-wire`, `bamabi-tools`, `bamabi-core`, `bamabi`, `bamabi-showcase`, and (when present or required) `bamabi-strata` (`[project].name`, `[project].layer`, and all 6 `[abi]` keys).
- **Versions, editions & MSRV**: `[workspace.package]` matches `abi-lock.toml` (`version = "0.3.0"`, `edition = "2024"`, `rust-version = "1.95"`), and every workspace member and excluded sub-crate declares `version = "0.3.0"` and `edition = "2024"`.
- **Dual licensing**: `LICENSE-MIT` and `LICENSE-APACHE` exist and are non-empty in all checked repositories (plus `bamabi-dev-overlay`), and every `[package]` (including excluded sub-crates) resolves `license = "MIT OR Apache-2.0"`.
- **Cross-repo dependencies & `deny.toml`**: Validates DAG ordering (`owner_layer < current_layer`), canonical `https://github.com/yaga-simha/<repo>.git` + `branch = "main"` URLs, and `[sources.allow-org]` / `allow-git` in `deny.toml` under `--strict-git`.
- **Stale monorepo reference scan**: Flags `bevy_mod_abi` / `bevy_abi_mod*` in `Cargo.toml`, `abi-lock.toml`, `deny.toml`, `.github/workflows/*.yml`, `Makefile`, and `build.zig` without false-positiving on historical provenance prose in `README.md` or `docs/`.

## Local & CI Self-Test

```bash
python3 -m py_compile sync_check.py overlay.py tests/test_overlay.py
python3 -m unittest discover -s tests -v
typos
```

## License

Dual-licensed under `MIT OR Apache-2.0` (`LICENSE-MIT` and `LICENSE-APACHE`).
