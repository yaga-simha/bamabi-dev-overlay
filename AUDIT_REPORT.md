# `bamabi` Multi-Repository Partitioning, Standalone Readiness & CI-Parity Audit Report

**Date:** 2026-11-20  
**Upstream Reference:** `https://github.com/yaga-simha/bevy_mod_abi`  
**Workspace Audited:** `/Users/simha/Desktop/bamabi/` (`bamabi-wire`, `bamabi-tools`, `bamabi-core`, `bamabi`, `bamabi-showcase`, `bamabi-dev-overlay`)  

---

## Publication & Verification Status (Post-M1–M6 Consolidation)

Following the M1 audit documented below, milestones **M2–M6** resolved blockers **B1–B9**, migrated cross-repo dependencies to standalone GitHub URLs (`branch = "main"`), restored standalone per-repo CI and documentation under dual `MIT OR Apache-2.0` licensing, and published all 6 repositories under `https://github.com/yaga-simha`:

| Layer | Repository | Role | GitHub URL | Published `main` SHA | CI Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Layer 0 | `bamabi-wire` | Wire ABI, C headers, guest/Rust SDKs | https://github.com/yaga-simha/bamabi-wire | `7a32b7b` | Passing (`5/5` jobs; [run 44700350937](https://github.com/yaga-simha/bamabi-wire/actions/runs/44700350937)) |
| Layer 1 | `bamabi-tools` | CLI tools (`bamabi-cli`, `bamabi-pack`, `bamabi-inspect`, `bamabi-lint`, `bamabi_codegen`, `bamabi-studio`) | https://github.com/yaga-simha/bamabi-tools | `c66399f` | Passing (`4/4` jobs; [run 44705237134](https://github.com/yaga-simha/bamabi-tools/actions/runs/44705237134)) |
| Layer 2 | `bamabi-core` | Core runtime (`bamabi_core`, `bamabi_vfs`, `bamabi_watcher`, `bamabi_engine_wgpu`) | https://github.com/yaga-simha/bamabi-core | `8d1011f` | Passing (`20/20` jobs; [run 44712672885](https://github.com/yaga-simha/bamabi-core/actions/runs/44712672885)) |
| Layer 3 | `bamabi` | Canonical host library facade | https://github.com/yaga-simha/bamabi | `5579892` | Passing (`5/5` jobs; [run 44725068412](https://github.com/yaga-simha/bamabi/actions/runs/44725068412)) |
| Layer 4 | `bamabi-showcase` | **Top-level integration repo** (examples, benches, `xtask`, polyglot & asymmetry integration tests) | https://github.com/yaga-simha/bamabi-showcase | `4e9fbff` | Partial (`10/11` jobs passing; `Test Matrix (windows-latest)` failed and deferred; [run 44741635916](https://github.com/yaga-simha/bamabi-showcase/actions/runs/44741635916)) |
| Overlay | `bamabi-dev-overlay` | Sibling Cargo `[patch]` manager (`overlay.py`), lockfile/license/DAG verifier (`sync_check.py`), & this audit report | https://github.com/yaga-simha/bamabi-dev-overlay | `081dc4c` (prior to adding `AUDIT_REPORT.md`) | Passing (`1/1` job; [run 44738392880](https://github.com/yaga-simha/bamabi-dev-overlay/actions/runs/44738392880)) |

**Overlay & Consistency Verification Summary:**
- `python3 sync_check.py --strict-git` passes (`3 ok, 0 warning(s), 0 error(s)`).
- `python3 overlay.py status` reports `Overlay config: DISABLED` and `Cargo.lock hygiene: CLEAN` across all 15 sibling crate directories.
- `python3 -m unittest discover -s tests -v` passes `14/14` tests.
- **Deferred Windows Issue:** `bamabi-showcase` `Test Matrix (windows-latest)` failed with exit code `101` while all 10 other CI jobs (including `ubuntu-latest`, `macos-latest`, polyglot `gcc`/`clang`/`cl.exe` asymmetry gates, `Heavy Examples & Standalone xtask CI`, `Quality Gates & Static Audits`, and `Benchmark Regression Gate`) passed; debugging `Test Matrix (windows-latest)` is intentionally deferred.
- **Note on Local `bamabi-wire` Checkout:** The local `/Users/simha/Desktop/bamabi/bamabi-wire` working tree contains unrelated concurrent edits outside the scope of this partitioning release and was intentionally left untouched; `origin/main` at `7a32b7b` is complete and passing CI.
- **Historical Context Note:** The detailed findings sections below (`§1` onward, originally authored at M1 prior to M2–M6 fixes and publication) document the baseline partitioning audit and the exact defects (`B1`–`B9` and CI gaps) that M2–M6 subsequently remediated.

---

## 1. Executive Summary & Top-Level Repository Identification

The original `yaga-simha/bevy_mod_abi` monorepo (**567 tracked/repository files** excluding `.git`) has been cleanly partitioned into an **acyclic 5-layer Cargo workspace DAG** plus **1 developer coordination/overlay repository** (`bamabi-dev-overlay`):

| Layer | Repository | Canonical Git URL | Crates / Primary Artifacts | Role in Ecosystem |
|---|---|---|---|---|
| **0** | `bamabi-wire` | `https://github.com/yaga-simha/bamabi-wire.git` | `bamabi_sys`, `bamabi_macros`, `bamabi_sdk_gen`, `bamabi_guest_sys`, `bamabi_guest`, `include/bamabi.h`, `spec.md`, `tests/standalone_c_test.c` | Zero-Bevy ABI `0.3.0` wire contract, procedural macros, polyglot header generator, and Rust guest SDK |
| **1** | `bamabi-tools` | `https://github.com/yaga-simha/bamabi-tools.git` | `bamabi_trust`, `bamabi_manifest`, `cargo-bam` | Zero-Bevy Ed25519 trust/signing, manifest DAG validation, and `cargo-bam` CLI |
| **2** | `bamabi-core` | `https://github.com/yaga-simha/bamabi-core.git` | `bamabi_host_sys`, `bamabi_host`, `bamabi_watcher`, `docs/ARCHITECTURE.md`, asymmetric & soak test suites/fixtures | Headless `bevy_ecs` + `bevy_app` host runtime, dynamic loader, and hot-reload watcher |
| **3** | `bamabi` | `https://github.com/yaga-simha/bamabi.git` | `bamabi_bridges`, `bamabi_render`, `bamabi_reflect`, **`bamabi`** | **Canonical Host Library Facade Repository** (Bevy `0.20.1` companion bridges/render/reflect + end-user `bamabi` facade crate) |
| **4** | `bamabi-showcase` | `https://github.com/yaga-simha/bamabi-showcase.git` | `xtask`, `examples/01..10`, `benches/*` (6 targets), `fuzz/*` (8 targets), `tests/bql_wire_contract_test.rs`, `docs/BENCHMARKS.md`, `docs/book/` | **Top-Level Integration Repository** (sole DAG sink integrating Layers 0–3, polyglot C99/C++17/Zig guests, benchmarks, fuzzing, and mdBook) |
| **Overlay** | `bamabi-dev-overlay` | `https://github.com/yaga-simha/bamabi-dev-overlay.git` | `sync_check.py`, `overlay.py`, `cargo-overlay.toml`, `tests/test_overlay.py`, `.github/workflows/ci.yml`, `README.md` | Cross-repo consistency verifier and local sibling Cargo `[patch]` overlay manager |

### Top-Level Integration Repo vs. Canonical Host Library Facade Repo
- **`bamabi-showcase` (Layer 4) is the Top-Level Integration Repository:** It is the sole sink in the 5-layer DAG, directly consuming all four lower layers (`bamabi-wire`, `bamabi-tools`, `bamabi-core`, `bamabi`) and owning cross-layer automation (`xtask`), all 10 runnable example pipelines (`01`–`10` including C99/C++17/Zig polyglot guests), all 6 benchmark suites (`coupled_rust_mod`, `permutation_bench`, `shared_scenario`, `c_abi_c99_mod`, `c_abi_rust_mod`, `deterministic_gate`), the 8-target `bamabi_fuzz` crate, `tests/bql_wire_contract_test.rs`, `scripts/run_e2e_tests.sh`, and the mdBook user guide (`docs/book/`). Consequently, `bamabi-showcase` is the owner of thorough full-stack integration CI.
- **`bamabi` (Layer 3) is the Canonical Host Library Facade Repository:** Downstream Bevy `0.20.1` game/application developers depend on `bamabi` (which aggregates `bamabi_host`, `bamabi_bridges`, `bamabi_render`, `bamabi_reflect`, `prelude`, and 18 feature flags / 4 bridge presets). It has zero dependency on `bamabi-tools` (`cargo-bam`) and owns no examples, benchmarks, fuzzers, or `xtask`.

### Audit Summary Verdict
- **Partitioning completeness:** 100% of the **567 upstream files** in `yaga-simha/bevy_mod_abi` are accounted for across the 5 split repos with **zero unexplained missing or orphaned files**.
- **Critical M1–M6 findings:**
  1. `bamabi-dev-overlay/` was absent locally and has been created in **M1** with `sync_check.py`, `overlay.py`, `cargo-overlay.toml`, `tests/test_overlay.py`, `LICENSE-MIT`, `LICENSE-APACHE`, `.gitignore`, `.typos.toml`, `.github/workflows/ci.yml`, and `README.md`.
  2. Cross-repo dependencies in Layers 1–4 currently use `path = "../bamabi-*"`, `deny.toml` sets `allow-git = []` with `unknown-git = "deny"`, and Layers 1–4 CI workflows check out sibling repos.
  3. **9 cross-repo boundary & standalone-readiness defects (`B1`–`B9`)** prevent isolated standalone builds/tests in Layers 1, 2, 3, and 4 until resolved across Milestones M2–M6.
  4. **Metadata/version/license drift:** 13 excluded sub-crates omit `license`, 17 manifests remain at `version = "0.2.0"`, `LICENSE-APACHE` has 3 formatting hash variants, and `CHANGELOG.md` line 20 is stale in 3 repos.
  5. **CI parity gaps:** All 4 `.github/workflows/nightly.yml` jobs were dropped during the split, and several `ci.yml` jobs/checks (`asymmetry-rust`, `asymmetry-polyglot` 5-CC matrix + `cargo run`, `coverage >= 85%`, `benchmark-gate`, `soak_10k_reloads`, UBSan `asymmetric_c_mod`, `cargo-semver-checks`, `host_sys --lib` Miri, `fuzz` clippy, `#![forbid(unsafe_code)]`/idiom checks, Linux audio/X11/Wayland headers) are missing or partial.

---

## 2. Complete Upstream-to-Split Crate & Artifact Mapping (All 567 Upstream Files)

Direct comparison between `https://github.com/yaga-simha/bevy_mod_abi` (567 files excluding `.git`) and `/Users/simha/Desktop/bamabi/` (622 files across the 5 Rust repos + 10 files in newly created `bamabi-dev-overlay`, excluding `.git`, `target/`, `.zig-cache/`, `zig-out/`):

| Upstream Area / Crate (`bevy_mod_abi`) | Upstream Files | Rename / Transform | Destination Repo & Path | Local Files | Notes |
|---|---:|---|---|---:|---|
| `crates/bevy_abi_mod_sys` | 22 | `bevy_abi_mod_sys` → `bamabi_sys` | `bamabi-wire/crates/bamabi_sys` | 22 | Exact 1:1 |
| `crates/bevy_abi_mod_macros` | 88 | `bevy_abi_mod_macros` → `bamabi_macros` | `bamabi-wire/crates/bamabi_macros` | 88 | Exact 1:1 (incl. 34 `tests/ui/*`) |
| `crates/bevy_abi_mod_sdk_gen` | 7 | `bevy_abi_mod_sdk_gen` → `bamabi_sdk_gen` | `bamabi-wire/crates/bamabi_sdk_gen` | 7 | Exact 1:1 |
| `crates/bevy_abi_mod_guest_sys` | 15 | `bevy_abi_mod_guest_sys` → `bamabi_guest_sys` | `bamabi-wire/crates/bamabi_guest_sys` | 15 | Exact 1:1 |
| `crates/bevy_abi_mod_guest` | 36 | `bevy_abi_mod_guest` → `bamabi_guest` | `bamabi-wire/crates/bamabi_guest` | 36 | Exact 1:1 |
| `include/bevy_abi_mod.h` | 1 | `bevy_abi_mod.h` → `bamabi.h` | `bamabi-wire/include/bamabi.h` | 1 | C99 wire header |
| `include/generated/testbed_components.h` | 1 | — | `bamabi-wire/include/generated/testbed_components.h` | 1 | **Boundary B4** (only consumed by `bamabi-core`) |
| `tests/standalone_c_test.c` | 1 | — | `bamabi-wire/tests/standalone_c_test.c` | 1 | Exact 1:1 |
| `spec.md` | 1 | — | `bamabi-wire/spec.md` | 1 | Updated for `bamabi-wire` |
| `crates/bevy_abi_mod_trust` | 9 | `bevy_abi_mod_trust` → `bamabi_trust` | `bamabi-tools/crates/bamabi_trust` | 9 | Exact 1:1 |
| `crates/bevy_abi_mod_manifest` | 5 | `bevy_abi_mod_manifest` → `bamabi_manifest` | `bamabi-tools/crates/bamabi_manifest` | 5 | Exact 1:1 |
| `crates/cargo-bam` | 15 | — | `bamabi-tools/crates/cargo-bam` | 15 | Exact 1:1 (`[package].name = "cargo-bam"`, `[lib].name = "cargo_bam"`) |
| `crates/bevy_abi_mod_host_sys` | 69 | `bevy_abi_mod_host_sys` → `bamabi_host_sys` | `bamabi-core/crates/bamabi_host_sys` | 69 | Exact 1:1 |
| `crates/bevy_abi_mod_host` | 49 | `bevy_abi_mod_host` → `bamabi_host` | `bamabi-core/crates/bamabi_host` | 48 | 1 file moved (`tests/e2e/example_pipelines.rs` → `bamabi-showcase/xtask/tests/`) |
| `crates/bevy_abi_mod_watcher` | 5 | `bevy_abi_mod_watcher` → `bamabi_watcher` | `bamabi-core/crates/bamabi_watcher` | 5 | Exact 1:1 (`watcher.rs` updated to `bamabi_sdk_gen`) |
| `docs/ARCHITECTURE.md` | 1 | — | `bamabi-core/docs/ARCHITECTURE.md` | 1 | Exact 1:1 |
| `tests/schedule_shuffle_fuzz.rs`, `tests/soak_10k_reloads.rs` | 2 | — | `bamabi-core/tests/` | 2 | **Boundary B3** (wired via `../../tests/` in `bamabi_host/Cargo.toml`) |
| `tests/asymmetric_c_mod/*` | 3 | — | `bamabi-core/tests/asymmetric_c_mod/` | 3 | `Makefile`, `mod.c`, `test_abi_layout.c` |
| `tests/asymmetric_rust_mod/*` | 3 | — | `bamabi-core/tests/asymmetric_rust_mod/` | 3 | Excluded sub-crate (`Cargo.toml`, `Cargo.lock`, `src/lib.rs`) |
| `tests/fixtures/` (`c_mods/*` 11 + `panic_abort_mod/*` 3) | 14 | — | `bamabi-core/tests/fixtures/` | 14 | 11 C99 fixtures + 1 excluded Rust sub-crate |
| `crates/bevy_abi_mod_bridges` | 19 | `bevy_abi_mod_bridges` → `bamabi_bridges` | `bamabi/crates/bamabi_bridges` | 19 | Exact 1:1 |
| `crates/bevy_abi_mod_render` | 10 | `bevy_abi_mod_render` → `bamabi_render` | `bamabi/crates/bamabi_render` | 11 | +1 added: `tests/common/mod.rs` (self-contained fallback C mod) |
| `crates/bevy_abi_mod_reflect` | 12 | `bevy_abi_mod_reflect` → `bamabi_reflect` | `bamabi/crates/bamabi_reflect` | 12 | Exact 1:1 |
| `crates/bevy_mod_abi` | 6 | `bevy_mod_abi` → `bamabi` | `bamabi/crates/bamabi` | 6 | Canonical host library facade crate |
| `crates/bevy_abi_mod` | 4 | **Removed** | *(none)* | 0 | Intentional retirement of deprecated forwarding shim crate |
| `xtask/` (`Cargo.toml` + `src/*`) | 4 | — | `bamabi-showcase/xtask/` | 6 | +2 split tests: `example_pipelines.rs` (moved), `sign_cli_e2e.rs` (extracted) |
| `examples/01..10` (hosts + 12 Rust + C99/C++17/Zig mods) | 100 | — | `bamabi-showcase/examples/01..10/` | 100 | Exact 1:1 |
| `benches/*` (6 crates/C99 targets) | 14 | — | `bamabi-showcase/benches/` | 14 | `coupled_rust_mod` (2), `permutation_bench` (2), `shared_scenario` (2), `c_abi_c99_mod` (2), `c_abi_rust_mod` (3), `deterministic_gate` (3) |
| `fuzz/*` (manifest, lock, 8 targets, 12 corpus files) | 22 | `bevy_abi_mod_fuzz` → `bamabi_fuzz` | `bamabi-showcase/fuzz/` | 22 | Exact 1:1 |
| `tests/bql_wire_contract_test.rs` | 1 | — | `bamabi-showcase/tests/bql_wire_contract_test.rs` | 1 | Wired by `examples/09_bql_wire_parity/Cargo.toml:17-19` |
| `docs/BENCHMARKS.md`, `docs/book/*` | 12 | — | `bamabi-showcase/docs/` | 12 | `BENCHMARKS.md` (1) + `book/` (11) |
| `scripts/run_e2e_tests.sh` | 1 | — | `bamabi-showcase/scripts/run_e2e_tests.sh` | 1 | Exact 1:1 |
| `Makefile`, `.cargo/config.toml` | 2 | — | `bamabi-showcase/` | 2 | `[alias] xtask` + `Makefile` |
| Shared root files (`Cargo.toml`, `Cargo.lock`, `CHANGELOG.md`, `README.md`, `deny.toml`, `.typos.toml`, `clippy.toml`, `rust-toolchain.toml`, `.gitignore`, `.gitattributes`) | 10 | Split per layer | All 5 Rust repos | 50 | 10 × 5 repos (`.gitattributes` in `bamabi-showcase` adds `fuzz/corpus/** binary`) |
| Root `GEMINI.md` | 1 | **Omitted** | *(none)* | 0 | Per-crate `crates/*/GEMINI.md` retained in all 15 crates |
| `.github/workflows/ci.yml` | 1 | Split per layer | All 5 Rust repos `.github/workflows/ci.yml` | 5 | 1 × 5 repos |
| `.github/workflows/nightly.yml` | 1 | **Missing** | *(none — target: `wire`, `core`, `showcase`)* | 0 | Must be restored in M2, M4, M6 (**Boundary B9**) |
| **Added in split (5 Rust repos)** | — | — | `LICENSE-MIT` (5), `LICENSE-APACHE` (5), `abi-lock.toml` (5), `bamabi_render/tests/common/mod.rs` (1), `xtask/tests/example_pipelines.rs` (1), `xtask/tests/sign_cli_e2e.rs` (1) | 18 | `example_pipelines.rs` moved from `bevy_abi_mod_host`; `sign_cli_e2e.rs` extracted from `signature_verification.rs:549-576,1152-1275` |
| **Added in M1 (Overlay repo)** | — | — | `bamabi-dev-overlay/` (`LICENSE-MIT`, `LICENSE-APACHE`, `.gitignore`, `.typos.toml`, `cargo-overlay.toml`, `sync_check.py`, `overlay.py`, `tests/test_overlay.py`, `.github/workflows/ci.yml`, `README.md`) | *(10)* | Recreated in M1 (**Boundary B1**) |
| **Totals** | **567** | | **5 Rust Repos (+ Overlay)** | **622 (+10)** | `186 + 43 + 159 + 62 + 172 = 622` |

### Accounting Verification
- **Removed/omitted/moved upstream files (7):**
  1. `crates/bevy_abi_mod/{Cargo.toml, GEMINI.md, README.md, src/lib.rs}` (4 files): Intentional retirement of the deprecated forwarding shim (`bamabi/crates/bamabi/README.md:7`, `bamabi-showcase/docs/book/src/overview.md:3`).
  2. `crates/bevy_abi_mod_host/tests/e2e/example_pipelines.rs` (1 file): Intentionally moved to `bamabi-showcase/xtask/tests/example_pipelines.rs` (`bamabi-core/crates/bamabi_host/tests/e2e/main.rs` cleanly removed `pub mod example_pipelines;`).
  3. Root `GEMINI.md` (1 file): Intentionally omitted at repo roots while all 15 per-crate `crates/*/GEMINI.md` files were retained.
  4. `.github/workflows/nightly.yml` (1 file): Missing gap (addressed by **B9** across M2, M4, M6).
- **Orphaned / git state:** All 5 Rust repos + `bamabi-dev-overlay` are initialized on unborn `main` (`git init -b main`, 0 commits, 0 remotes), with zero junk or orphaned files.

---

## 3. Metadata, Licensing, Version & `CHANGELOG.md` Audit

1. **`LICENSE-MIT` (Consistent across all 6 repos):**
   - Present in all 5 Rust repos and copied identically into `bamabi-dev-overlay/` (SHA256 `f9c4c77baa3828004ee54b8a4f2db2e88ed44a6237a493965bf551fac0fcb62d`, 1,023 bytes).
2. **`LICENSE-APACHE` (3 SHA256 formatting variants across the 5 Rust repos):**
   - `bamabi-wire`, `bamabi-tools`, `bamabi-dev-overlay`: `2504a9d3b1624f6d790df927a3fad76e6857d4b59d0e94f1e489878922b7cf4d` (10,106 B — canonical baseline).
   - `bamabi-core`, `bamabi`: `2032cb643ba8211e605e248923f02440f53c20fc10b7894fe972c81bf22f9050` (10,112 B — wraps lines 39–40 `"Object form"` and 178–179 `"implied."`).
   - `bamabi-showcase`: `ac65c2f1f14dd174338f1d09b16bbf5427cd5838dbc2dc41d692131aaeecaa52` (10,106 B — wraps lines 39–40 `"Object form"`).
   - *Action:* Canonicalize `LICENSE-APACHE` to the `bamabi-wire` SHA256 (`2504a9d3...`) during M4/M5/M6.
3. **13 Manifests Missing `license = "MIT OR Apache-2.0"`:**
   - **`bamabi-core` (2 — both omit `publish = false`, defaulting to `publish = true`!):**
     - `tests/asymmetric_rust_mod/Cargo.toml`
     - `tests/fixtures/panic_abort_mod/Cargo.toml`
   - **`bamabi-showcase` (11):**
     - `benches/c_abi_rust_mod/Cargo.toml`
     - `examples/01_minimal_handshake/guest_mod/Cargo.toml`
     - `examples/02_multi_system_pipeline/guest_mod/Cargo.toml`
     - `examples/03_cross_language_interop/rust_mod/Cargo.toml`
     - `examples/04_visual_game/mods/{mod_gravity,mod_rainbow,mod_vortex}/Cargo.toml`
     - `examples/05_cute_3d_winit/mods/{mod_boing,mod_carousel}/Cargo.toml`
     - `examples/06_cross_mod_components/mods/{mod_overcharge_siphon,mod_shield_emitter}/Cargo.toml`
4. **17 Manifests at Stale `version = "0.2.0"` (Expected `"0.3.0"`):**
   - **`bamabi-core` (2):** `tests/asymmetric_rust_mod/Cargo.toml`, `tests/fixtures/panic_abort_mod/Cargo.toml`.
   - **`bamabi-showcase` (15):** The 11 excluded crates listed above, plus:
     - `examples/04_visual_game/Cargo.toml` (workspace member — should use `version.workspace = true`)
     - `examples/05_cute_3d_winit/Cargo.toml` (workspace member — should use `version.workspace = true`)
     - `benches/deterministic_gate/Cargo.toml` (excluded crate)
     - `benches/shared_scenario/Cargo.toml` (excluded crate)
   - *Verification note:* Running `python3 /Users/simha/Desktop/bamabi/bamabi-dev-overlay/sync_check.py` directly reports these exact **30 errors** (`17` stale `0.2.0` + `13` missing `license`) and `57` pre-M6 path/`deny.toml` warnings.
5. **`CHANGELOG.md` Line 20 Mismatch:**
   - `bamabi-wire`, `bamabi-tools` (`d74048429719bca269449bb65cba6ae1b4c328a6cfa68854cc2f5dd9228c77e2`, 20,389 B):  
     `"  - Established canonical top-level \`bamabi\` host facade crate matching \`github.com/yaga-simha/bamabi\` and re-exporting \`bamabi_host\`, companion crates, \`prelude\`, and all 18 optional feature flags plus 4 curated bridge presets."`
   - `bamabi-core`, `bamabi`, `bamabi-showcase` (`4351bedd574493fb9aad8f595f80074c1047cbde025ede48fc4afabe506b5092`, 20,328 B):  
     Stale wording: `"  - Added crates.io umbrella alias crate \`bamabi\` matching \`github.com/yaga-simha/bamabi\` and forwarding \`bamabi::*\`, \`prelude\`, and all 17 optional feature flags 1:1."`
   - *Action:* Sync `CHANGELOG.md` line 20 in `bamabi-core`, `bamabi`, and `bamabi-showcase` to match `bamabi-wire`/`bamabi-tools`.
6. **`abi-lock.toml` Parity (100% Consistent):**
   - All 5 layer repos define `[project].layer` (`0..4`) and identical `[abi]` values: `bam_abi_version = "0x0003_0000"`, `c_symbol_prefix = "bamabi"`, `workspace_version = "0.3.0"`, `bevy_version = "0.20.1"`, `rust_version = "1.95"`, `edition = "2024"`.
   - Note: Layer 0 crates (`bamabi_sys`, `bamabi_macros`, `bamabi_guest_sys`, `bamabi_guest`) and guest mod fixtures intentionally declare `rust-version = "1.87"` for guest MSRV compatibility, while workspaces declare `rust-version = "1.95"`.
7. **`bamabi-showcase/Cargo.toml` `default-members`:**
   - Upstream `Cargo.toml` defined `default-members` excluding heavy GUI/Winit/Zig targets (`coupled_rust_mod`, `permutation_bench`, `example_04_visual_game`, `example_05_cute_3d_winit`, `example_08_zig_guest`) so bare `cargo test` stayed lightweight without Linux display/audio/Zig toolchains. `bamabi-showcase/Cargo.toml` dropped `default-members`, causing bare `cargo test` to build all 13 workspace members. M6 should evaluate restoring `default-members` (or explicitly documenting/testing heavy members in `ci.yml` with Linux deps + Zig `0.16.0`).

---

## 4. Cross-Repo Boundary & Standalone-Readiness Fix Table (`B1`–`B9`)

| ID | Repo / Layer | Exact File(s) & Lines | Current Defect | Required Fix Before Finalization | Target Milestone |
|---|---|---|---|---|---|
| **B1** | Overlay | `/Users/simha/Desktop/bamabi/bamabi-dev-overlay/` (was missing) | Referenced by all 5 `README.md`s, `bamabi-wire/spec.md:117`, and `bamabi-core/docs/ARCHITECTURE.md:193`, but absent locally | Create `bamabi-dev-overlay` (`sync_check.py`, `overlay.py`, `cargo-overlay.toml`, `tests/test_overlay.py`, `LICENSE-MIT`, `LICENSE-APACHE`, `.gitignore`, `.typos.toml`, `.github/workflows/ci.yml`, `README.md`) — **completed in M1** (pushed to GitHub in M6) | **M1** (+ push M6) |
| **B2** | L1–L4 | Workspace `Cargo.toml`s (`bamabi-tools:34-35`, `bamabi-core:38-42`, `bamabi:35-40`, `bamabi-showcase:62-69`), 20 direct/excluded `Cargo.toml`s (incl. `examples/09_bql_wire_parity:25-27`, `examples/10_bevy20_full_companion:10-24`, `fuzz`, 3 benches, 12 guest mods, 2 core fixtures), `deny.toml:57-61` in all repos, plus `bamabi/crates/bamabi/tests/bridges_integration.rs:57-67,203-299` | Cross-repo deps use `path = "../bamabi-*"` / `../../../bamabi-*`; `deny.toml` sets `allow-git = []` & `unknown-git = "deny"`; `bridges_integration.rs` compiles temp guest mods against `../bamabi-wire/crates/bamabi_guest` | Convert all cross-repo deps to `git = "https://github.com/yaga-simha/<repo>.git", branch = "main"`; add `[sources.allow-org]\ngithub = ["yaga-simha"]` to `deny.toml`; update `bridges_integration.rs` (M5) to fall back to `bamabi-wire` git URL when `BAM_WIRE_DIR`/sibling absent; regenerate tracked `Cargo.lock`s with `git+https://` sources | **M3–M6** |
| **B3** | L2 (`bamabi-core`) | `crates/bamabi_host/Cargo.toml:66-72`, `tests/schedule_shuffle_fuzz.rs:1061-1083,1118-1120`, `tests/soak_10k_reloads.rs:622-644,663-666` | `[[test]]` points outside crate (`../../tests/...`), breaking `cargo package` / `cargo publish` (flagged in `crates/bamabi_host/GEMINI.md:51`); temp guest crates fail without `../bamabi-wire` on disk | Move `schedule_shuffle_fuzz.rs` and `soak_10k_reloads.rs` into `crates/bamabi_host/tests/` (updating `Cargo.toml` `[[test]]` paths) and fall back to `bamabi-wire` git URL when `BAM_WIRE_DIR`/sibling absent | **M4** |
| **B4** | L0 / L2 / L4 | `bamabi-wire/include/generated/testbed_components.h`, `bamabi-core/tests/asymmetric_c_mod/{mod.c:2,Makefile:15,19,test_abi_layout.c:5}`, `bamabi_host/tests/support/helpers.rs:230-250`, `bamabi_host_sys/tests/signature_loader_security_tests.rs:84-94` | `testbed_components.h` (5,808 lines) lives only in `bamabi-wire` (regenerated by `bamabi-showcase/xtask`) while only `#include`d by `bamabi-core/tests/asymmetric_c_mod/mod.c`; `bamabi-core` C fixtures/tests fail standalone without `../bamabi-wire/include` | Render `bamabi.h` via `bamabi_sdk_gen::render_c99_header()` into `target/include/` in `bamabi-core` helpers when sibling absent; vendor/mirror `generated/testbed_components.h` under `bamabi-core/tests/asymmetric_c_mod/include/generated/` (updating `Makefile`/helpers); keep `bamabi-wire/include/` in sync when sibling present | **M2 / M4 / M6** |
| **B5** | L2 (`bamabi-core`) | `crates/bamabi_host/tests/lifecycle/schema_evolution.rs:53-89`, `tests/asymmetric_rust_mod/Cargo.toml:1-14`, `tests/fixtures/panic_abort_mod/Cargo.toml:1-19` | Temp guest crates & excluded Rust fixtures hardcode `../bamabi-wire` paths; both excluded fixtures omit `license` (defaulting `publish = true`) and have stale `version = "0.2.0"` | Add `license = "MIT OR Apache-2.0"`, `publish = false`, `version = "0.3.0"`, and `bamabi-wire` git URLs to both fixtures; update `schema_evolution.rs` to fall back to `bamabi-wire` git URL when sibling absent | **M4** |
| **B6** | L1 (`bamabi-tools`) | `crates/cargo-bam/src/scaffold.rs:60-68`, `crates/cargo-bam/tests/cli_integration.rs:14-35`, `crates/cargo-bam/tests/pack_watch_doctor_e2e.rs:422-441` | `scaffold.rs` emits unpublished crates.io `bamabi_guest = { version = "0.3.0", ... }`; integration tests assert `../../../bamabi-wire/crates/bamabi_guest/Cargo.toml` exists on disk, failing standalone | Default `scaffold.rs` Rust template to `git = "https://github.com/yaga-simha/bamabi-wire.git", branch = "main"` (preserving local path override if `--guest-sdk-path` or sibling desired) and decouple integration tests to use git URL / standalone fallback when `../bamabi-wire` absent | **M3** |
| **B7** | L4 (`bamabi-showcase`) | `xtask/src/main.rs:598-612` (+ callers at L798, L845, L876, L888, L1037, L1375-1376, L1511, L1530, L1547, L1567, L1626, L1644-1648, L1764, L1790-1791, L1929-1932, L2004-2005), `xtask/tests/sign_cli_e2e.rs:79-107`, `examples/08_zig_guest/zig_mod/build.zig:8,13`, 5 Makefiles (`examples/{03,05,07,09}`, `benches/c_abi_c99_mod`), 3 example hosts (`examples/03_cross_language_interop/src/main.rs:339`, `examples/07_cpp17_guest/src/lib.rs:226,616`, `examples/09_bql_wire_parity/src/lib.rs:560`), `Cargo.toml` | `xtask`, `sign_cli_e2e.rs`, `build.zig`, Makefiles, and example hosts hardcode `../bamabi-wire/include` and `../bamabi-core/tests/`; 11 excluded sub-crates miss `license` and 15 crates are `0.2.0`; `Cargo.toml` omits `default-members` | Stage `target/include/bamabi.h` via `bamabi_sdk_gen::render_c99_header()` when sibling `bamabi-wire` absent; make `xtask` & `sign_cli_e2e.rs` self-contained standalone (gating sibling-repo steps on sibling presence / `BAM_*_DIR`); add `license = "MIT OR Apache-2.0"` and `0.3.0` to all non-compliant crates; evaluate restoring `default-members` | **M6** |
| **B8** | L0–L4 | `LICENSE-APACHE` (3 hashes), `CHANGELOG.md:20` (L2–L4), `crates/*/GEMINI.md` (15 files), `README.md`s, `docs/{ARCHITECTURE,BENCHMARKS,book/*}` | Formatting variance in `LICENSE-APACHE`; stale `CHANGELOG.md:20` in L2–L4; stale `"Standalone Repository Split Checklist"` in 15 `GEMINI.md` files; docs assume sibling `../bamabi-*` paths | Canonicalize `LICENSE-APACHE` to `bamabi-wire` hash; sync `CHANGELOG.md:20`; clean split checklists from `GEMINI.md`; improve `README.md`s, `docs/`, and crate docs (`cargo doc` clean) for standalone per-repo workflows + optional `bamabi-dev-overlay` | **M2–M6** |
| **B9** | L0–L4 | Missing `.github/workflows/nightly.yml`; `.github/workflows/ci.yml` sibling checkouts & omitted jobs | Upstream `nightly.yml` (`fuzz`, `tsan-and-loom`, `miri-big-endian`, `randomize-layout-and-proptest`) missing everywhere; L1–L4 `ci.yml` check out sibling repos; multiple upstream `ci.yml` + `xtask` gates dropped | Remove sibling checkouts from L1–L4 `ci.yml`; restore full CI + `nightly.yml` parity per owning layer (see Section 5) | **M2–M6** |

---

## 5. Complete Job-by-Job CI Parity Matrix (`ci.yml` + `nightly.yml` + `xtask`)

Upstream `https://github.com/yaga-simha/bevy_mod_abi` defines **10 jobs in `.github/workflows/ci.yml`**, **4 jobs in `.github/workflows/nightly.yml`**, and **6 `cargo xtask` composite commands** (`lint`, `ci`, `header`, `gen-component-headers`, `fixtures`, `miri`). Every upstream job and check maps cleanly into the split repositories as follows:

### 5.1 `.github/workflows/ci.yml` (Upstream 10 Jobs)

| Upstream Job & Step / Check | Current Split Coverage | Standalone / Parity Gap | Target Owner & Required Action (M2–M6) |
|---|---|---|---|
| **1. `quality-gates`** (`ubuntu-26.04`, `fetch-depth: 0`) | | | |
| 1.1 `actions/checkout@v6` (`fetch-depth: 0`) | Single-repo in `bamabi-wire` (no `fetch-depth: 0`); **L1–L4 check out sibling repos** | **BROKEN-STANDALONE** in L1–L4; missing `fetch-depth: 0` in `bamabi-wire` breaks `cargo-semver-checks` | **All 6 repos**: standalone single-repo checkout (`bamabi-wire` adds `fetch-depth: 0`) |
| 1.2 Linux system deps (`libasound2-dev libudev-dev libx11-dev libxi-dev libxkbcommon-dev libwayland-dev libegl-dev libxcursor-dev libxrandr-dev libxinerama-dev pkg-config`) | **MISSING** everywhere | `bamabi/Cargo.lock` has `alsa-sys`; `bamabi-showcase/Cargo.lock` has `alsa-sys`, `wayland-sys`, `x11-dl`, `x11rb` — fails linking on Linux | **`bamabi`** (`libasound2-dev pkg-config` or full list) & **`bamabi-showcase`** (full X11/Wayland/ALSA/udev list) |
| 1.3 Rust targets (`i686-unknown-linux-gnu`, `wasm32-unknown-unknown`) | `PRESENT` in `bamabi-wire` | None | **`bamabi-wire`** (`static-wire-and-audit`) |
| 1.4 `Swatinem/rust-cache@v2` | `PRESENT` (L1–L4 specify `workspaces: <repo>`) | Remove `workspaces: <repo>` once sibling checkouts are removed; ensure `Cargo.lock` uses `git+https://` | **All 5 Rust repos** |
| 1.5 `crate-ci/typos@v1.31.1` | `PRESENT` (L1–L4 scope `files: <repo>`) | Remove `files:` filter once single-repo checkout is restored | **All 6 repos** |
| 1.6 `cargo deny --all-features check advisories licenses bans sources` | `PARTIAL` (`deny.toml` has `allow-git = []`) | **BROKEN-STANDALONE** once git deps are used | **All 5 Rust repos** (update `deny.toml` in L1–L4 with `allow-org.github = ["yaga-simha"]`) |
| 1.7 `cargo fmt --all -- --check` | `PRESENT` in L0–L4 | None | **All 5 Rust repos** |
| 1.8 `cargo xtask lint`:<br>a) `clippy` default + `--all-features`<br>b) `sig-verification` isolated clippy<br>c) `verify_zero_bevy_deps`<br>d) `verify_headless_host_isolation`<br>e) `verify_forbid_unsafe` (14 `crates/*` paths in upstream `safe_crates` array -> 12 active crates after `bevy_abi_mod` retirement + `xtask`)<br>f) `sdk_gen` header parity + C99<br>g) `component_header_gen` + C99<br>h) `audit_bevy_idioms` | **PARTIAL**: `xtask` moved to L4, so L0–L3 dropped `b`, `e`, `h`, and default `clippy`; L4 `xtask` requires sibling checkouts | Critical silent loss of `#![forbid(unsafe_code)]`, Bevy-idiom audits, `signature-verification` clippy, and standalone `xtask` headers | **Per-repo `ci.yml`**:<br>- `L0` (`wire`): default+all clippy, `#![forbid(unsafe_code)]` (3 crates), zero-Bevy, `sdk_gen` parity + C99<br>- `L1` (`tools`): default+all clippy, `#![forbid(unsafe_code)]` (3 crates), zero-Bevy<br>- `L2` (`core`): default+`sig-verif`+all clippy, `#![forbid(unsafe_code)]` (2 crates), headless isolation, Bevy idioms<br>- `L3` (`bamabi`): default+`sig-verif`+all clippy, feature isolation, `#![forbid(unsafe_code)]` (4 crates), Bevy idioms<br>- `L4` (`showcase`): default+all clippy, `#![forbid(unsafe_code)]` (`xtask`), standalone `xtask` header/component-header checks |
| 1.9 `cargo xtask header --check --test-c99` | `PARTIAL` in `wire` (`cc` only, no `sdk_gen` parity or `-pedantic`); `BROKEN-STANDALONE` in `showcase` | `wire` misses `sdk_gen` byte-parity check; `showcase` hardcodes `../bamabi-wire` | **`bamabi-wire`** (Rust parity test + `-pedantic` C99) & **`bamabi-showcase`** (standalone `target/include` + `BAM_WIRE_DIR` support) |
| 1.10 `cargo xtask gen-component-headers --check` | `BROKEN-STANDALONE` in `showcase` | Hardcodes `../bamabi-wire/include/generated/testbed_components.h` | **`bamabi-showcase`** (standalone check in `target/include` or `BAM_WIRE_DIR`) & **`bamabi-wire`** (C99 `-fsyntax-only`) |
| 1.11 `cargo clippy --manifest-path fuzz/Cargo.toml --bins -- -D warnings` | **MISSING** in `bamabi-showcase` | Excluded `fuzz/` crate never linted | **`bamabi-showcase`** (`ci.yml`) |
| 1.12 `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps` (default + `--all-features`) | `PARTIAL` (`L0–L3` run `--all-features` only; `L4` default only) | Feature-gated doc links untested in one mode | **All 5 Rust repos** (both default & `--all-features`) |
| 1.13 `cargo-semver-checks` on `bamabi_sys` | **MISSING** in `bamabi-wire` | `bamabi_sys/Cargo.toml:20-21` retains semver metadata, but `ci.yml` dropped check | **`bamabi-wire`** (`static-wire-and-audit` with `fetch-depth: 0`) |
| 1.14 `mdbook build docs/book` | `PRESENT` in `bamabi-showcase` | Recommend pinning `mdbook@0.4.48` per upstream | **`bamabi-showcase`** (`ci.yml`) |
| **2. `test-matrix`** (`ubuntu, macos, windows`) | | | |
| 2.1 3-OS matrix + `CARGO_PROFILE_{DEV,TEST}_DEBUG=line-tables-only` + Linux disk cleanup | `PARTIAL` (3-OS present, debug/disk guards missing) | Heavy Bevy workspaces risk runner disk/OOM | **`L0–L4` `ci.yml`** (add `line-tables-only` & Linux disk cleanup in `L2`, `L3`, `L4`) |
| 2.2 Windows `ilammy/msvc-dev-cmd@v1` + `VCToolsInstallDir` `PATH` fix | `PARTIAL` (`VCToolsInstallDir` `cygpath` fix missing) | Git Bash `/usr/bin/link` can shadow MSVC `link.exe` | **`L0–L4` `ci.yml`** |
| 2.3 Workspace & feature test matrix + `cargo test --doc --all-features` | `PARTIAL` / `BROKEN-STANDALONE` | `L1` misses `bamabi_trust --no-default-features` & `cargo-bam header`; `L2`/`L3` miss `--features signature-verification` standalone; `L4` misses `--doc --all-features` | **L0–L4 `ci.yml`** (after `B2`–`B7` decoupling) |
| 2.4 `cargo run -p cargo-bam -- doctor [--require-c]` & `header --out target/ci_sdk_check` | `PARTIAL` (`bamabi-tools` omits `header` and `--require-c`) | `header` subcommand & `--require-c` untested | **`bamabi-tools`** (`ci.yml`) |
| 2.5 `BAM_SOAK_CYCLES=10000 cargo test -p bamabi_host --test soak_10k_reloads --release` (Linux) | **MISSING** | Only debug default-cycle run in `bamabi-core` | **`bamabi-core`** (`ci.yml` `test-matrix`, Linux) |
| **3. `heavy-examples`** | `PARTIAL / BROKEN` in `bamabi-showcase` | Lacks Linux X11/Wayland/ALSA/udev headers & explicit headless binary smoke checks (`01`..`10`) | **`bamabi-showcase`** (`ci.yml` `heavy-examples-and-e2e`) |
| **4. `asymmetry-rust`** (6-cell `[1.95.0/stable/nightly] x [O0/O3] x [unwind/abort]`) | **COMPLETELY MISSING** in `bamabi-core` | Both `asymmetric_rust_mod` & `panic_abort_mod` live in `bamabi-core`, but job was omitted | **`bamabi-core`** (`ci.yml` `asymmetry-rust`, standalone) |
| **5. `asymmetry-polyglot`** (5-cell `[ubuntu+gcc, ubuntu+clang, macos+clang, windows+gcc, windows+cl.exe]`, Zig `0.16.0 -Doptimize=ReleaseFast`, `cargo run` on `07` & `08`) | **MISSING** matrix (`L4` uses default CC only, debug `zig build`, no `cargo run` on `07`/`08`; `L2` uses default CC only for `asymmetric_c_mod`) | Missing compiler/OS matrix & standalone `target/include/bamabi.h` for Zig/C/C++ | **`bamabi-showcase`** (`asymmetry-polyglot` 5-cell matrix), **`bamabi-core`** (C99 `gcc`/`clang`/`cl.exe`), **`bamabi-tools`** (`doctor --require-c`), **`bamabi`** (`bridges_integration` standalone) |
| **6. `benchmark-gate`** (`valgrind` + `iai-callgrind` `deterministic_gate`, `chunk_throughput -- --test`) | **COMPLETELY MISSING** in `bamabi-core` & `bamabi-showcase` | `deterministic_gate` (`L4`) and `chunk_throughput` (`L2`) never executed in CI | **`bamabi-showcase`** (`iai-callgrind` `deterministic_gate` + permutation smoke) & **`bamabi-core`** (`chunk_throughput -- --test`) |
| **7. `coverage`** (`>= 85%` on `bamabi_host_sys/src/{ffi,system}/`) | **COMPLETELY MISSING** | Neither `bamabi-core` nor `bamabi` runs `cargo-llvm-cov` | **`bamabi-core`** (`cargo-llvm-cov --fail-under-lines 85` on `ffi/` + `system/`) & **`bamabi`** (optional coverage check) |
| **8. `miri`** (`-Zmiri-tree-borrows`) | `PRESENT` in `bamabi-wire`; **MISSING** in `bamabi-core` | `bamabi_host_sys --lib` Miri check dropped | **`bamabi-wire`** (`sys`, `guest_sys`, `guest`, `macros`) & **`bamabi-core`** (`bamabi_host_sys --lib`) |
| **9. `loom`** (`loom_drop_trampoline --release`) | `PRESENT` in `bamabi-core` (`quality-and-tests`) | None (keep or split into dedicated `loom` job) | **`bamabi-core`** (`ci.yml`) |
| **10. `sanitizers`** (C99 ASan+UBSan in `wire`; UBSan `asymmetric_c_mod` in `core`) | `PRESENT` in `bamabi-wire`; **MISSING** in `bamabi-core` | `bamabi-core` dropped UBSan-instrumented `asymmetric_c_mod` run | **`bamabi-wire`** (`standalone_c_test.c`) & **`bamabi-core`** (`sanitizers` UBSan `asymmetric_c_mod`) |

### 5.2 `.github/workflows/nightly.yml` (Upstream 4 Jobs — Currently 0/5 Repos Have `nightly.yml`)

| Upstream Nightly Job | Exact Scope | Target Owner(s) |
|---|---|---|
| **N1. `fuzz`** | 5-target matrix (`fuzz_read_extensible`, `fuzz_system_desc`, `fuzz_commands`, `fuzz_cstr_array`, `fuzz_sshsig_and_krl`) for `600s` against `fuzz/corpus/<target>` (+ check all 8 bins in `fuzz/Cargo.toml`) | **`bamabi-showcase`** (`nightly.yml`) |
| **N2. `tsan-and-loom`** | `loom_drop_trampoline --release` + uninstrumented fixtures + `-Zsanitizer=thread -Zbuild-std --target x86_64-unknown-linux-gnu -p bamabi_host --test scheduling --test lifecycle` | **`bamabi-core`** (`nightly.yml`) |
| **N3. `miri-big-endian`** | `MIRIFLAGS="-Zmiri-tree-borrows"` on `s390x-unknown-linux-gnu`: `sys`, `guest_sys`, `guest` (`bamabi-wire`); `host_sys --lib` (`bamabi-core`) | **`bamabi-wire`** & **`bamabi-core`** (`nightly.yml`) |
| **N4. `randomize-layout-and-proptest`** | `RUSTFLAGS="-Zrandomize-layout"` + `PROPTEST_CASES="2048"`: `sys`, `guest_sys`, `guest`, `macros` (`bamabi-wire`); unrandomized fixtures then `host_sys --lib` (default & `signature-verification`) + `bamabi_host` (`bamabi-core`) | **`bamabi-wire`** & **`bamabi-core`** (`nightly.yml`) |

### 5.3 Overlay Repo CI (`bamabi-dev-overlay/.github/workflows/ci.yml`)
- Standalone single-repo workflow (`ubuntu-latest`, Python 3.12):
  1. Verify `LICENSE-MIT` and `LICENSE-APACHE` exist and are non-empty.
  2. `python3 -m py_compile sync_check.py overlay.py tests/test_overlay.py`.
  3. Validate `cargo-overlay.toml` via `tomllib` (4 canonical repo keys, 15 crate paths including `"cargo-bam"`).
  4. `python3 -m unittest discover -s tests -v`.
  5. `crate-ci/typos@v1.31.1`.

---

## 6. GitHub Publication & Local Overlay Contract

1. **Canonical Cross-Repo Git Dependency Format (Layers 1–4, workspaces AND excluded sub-crates):**
   - Always specify the `.git` suffix and `branch = "main"`:
     - `https://github.com/yaga-simha/bamabi-wire.git` (`branch = "main"`)
     - `https://github.com/yaga-simha/bamabi-tools.git` (`branch = "main"`)
     - `https://github.com/yaga-simha/bamabi-core.git` (`branch = "main"`)
     - `https://github.com/yaga-simha/bamabi.git` (`branch = "main"`)
   - Zero cross-repo `path = "../..."` entries remain in any tracked `Cargo.toml` once Milestones M3–M6 complete (`sync_check.py --strict-git` enforces this).
2. **`deny.toml` Source Allowlist (Layers 1–4):**
   - Retain `unknown-registry = "deny"`, `unknown-git = "deny"`, `allow-registry = ["https://github.com/rust-lang/crates.io-index"]`, and add:
     ```toml
     [sources.allow-org]
     github = ["yaga-simha"]
     ```
     (Verified supported by `cargo-deny 0.21.0`.)
3. **Local Sibling `[patch]` Overlay (`bamabi-dev-overlay`):**
   - Managed via `python3 bamabi-dev-overlay/overlay.py {enable,status,disable}`, which safely writes/removes `<federation-root>/.cargo/config.toml` guarded by `# MANAGED BY bamabi-dev-overlay/overlay.py`.
   - `cargo-overlay.toml` defines all 4 `[patch."https://github.com/yaga-simha/<repo>.git"]` tables covering all 15 crates (including `"cargo-bam"`, keyed by `[package].name`) with paths `"bamabi-<repo>/crates/<crate>"` (resolved relative to `<federation-root>/`, the parent of `.cargo/`, verified empirically with Cargo 1.98.1).
   - **Important:** Cargo requires the upstream git repo URL in `[patch."..."]` to be reachable during initial lockfile/git fetch if not already cached, and `Cargo.lock` must **not** be committed while `[patch]` is active (because Cargo strips `source = "git+..."` from patched entries). `overlay.py status --strict` and `disable` audit all 22 `Cargo.lock` files across the 5 repos for non-standalone entries and uncommitted git lockfile changes.
4. **GitHub Creation & SSH Push Protocol (M2–M6):**
   - Create 6 **public** repositories under `yaga-simha` (`bamabi-wire`, `bamabi-tools`, `bamabi-core`, `bamabi`, `bamabi-showcase`, `bamabi-dev-overlay`), branch `main`, and push via SSH (`git@github.com:yaga-simha/<repo>.git`) because `gh` OAuth tokens without `workflow` scope cannot push `.github/workflows/*.yml` over HTTPS.
   - Push strictly in topological layer order (**M2:** `bamabi-wire` → **M3:** `bamabi-tools` → **M4:** `bamabi-core` → **M5:** `bamabi` → **M6:** `bamabi-showcase` & `bamabi-dev-overlay`) so every downstream `Cargo.lock` resolves against live upstream `main` commits and every standalone CI run passes immediately on push.
