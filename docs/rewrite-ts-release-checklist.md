# rewrite-ts Release Checklist

This checklist is for the TypeScript-only desktop runtime:

- `apps/desktop` (Tauri + SolidJS)
- `apps/agent-sidecar` (Node/TS bridge runtime)
- `apps/comsol-java-sidecar` (Java COMSOL execution sidecar)

## 1. Preflight

1. Confirm branch is `rewrite-ts`.
2. Confirm Node version is `>=22` (`node -v`).
3. Confirm JDK is available (`java -version`).
4. If building Java sidecar locally, ensure one of:
   - outbound network can reach `https://services.gradle.org/`, or
   - `apps/comsol-java-sidecar/build/libs/comsol-java-sidecar-all.jar` already exists.

## 2. Quality Gates

Run from workspace root:

```bash
npm run build
npm run lint
npm run test
```

Run Rust check:

```bash
cd apps/desktop/src-tauri
cargo check
```

Expected: all commands succeed.

## 3. Runtime Packaging Prep

Run desktop runtime prep:

```bash
npm run prepare:runtime -w @mph-agent/desktop
```

If local network blocks Gradle distribution download, use:

```bash
MPH_AGENT_SKIP_JAVA_BUILD=1 npm run prepare:runtime -w @mph-agent/desktop
```

On Windows `cmd`:

```bat
set MPH_AGENT_SKIP_JAVA_BUILD=1&& npm run prepare:runtime -w @mph-agent/desktop
```

Behavior:

- Node sidecar is always prepared.
- Java sidecar build is skipped with warning when Gradle host is unreachable.
- App remains runnable with COMSOL mock fallback if Java jar is missing.

## 4. COMSOL Mode Validation

### Mock mode (default/fallback)

1. Start app.
2. Run `/doctor` and confirm COMSOL info shows mock backend.
3. Run one `run` request and confirm model path/artifact path are absolute paths.

### COMSOL bridge mode (when environment is available)

Set environment before starting desktop:

- `MPH_AGENT_ENABLE_COMSOL=1`
- and either `COMSOL_JAR_DIR` or `COMSOL_HOME`

Then verify:

1. `/doctor` reports Java sidecar health and COMSOL bridge availability.
2. `run` with `solve.run` action returns success and absolute `model_path`.
3. If COMSOL reflection fails, response still succeeds with fallback detail in artifact log.

## 5. CI Expectations

`rewrite-ts` CI should pass all jobs:

1. TypeScript build/tests on `windows-latest`, `macos-latest`, `ubuntu-latest`.
2. `cargo check` on all three OSes.
3. Java sidecar build using wrapper (`./gradlew --no-daemon shadowJar`) on Ubuntu.

## 6. Release Output Sanity

Before publishing installers:

1. Launch packaged app on each target OS.
2. Verify conversation flow, stream events, abort, settings, and model preview.
3. Verify `Open Model` / `Open Folder` works with absolute paths.
4. Verify app handles missing COMSOL runtime gracefully (no crash).
5. Archive build logs and checksums with release artifacts.
