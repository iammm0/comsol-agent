# comsol-java-sidecar

Java JSON-RPC sidecar for COMSOL execution in the `rewrite-ts` architecture.

## What it does

- Reads one JSON-RPC-like request per stdin line.
- Writes one JSON response per stdout line.
- Emits startup handshake:
  - `{"_ready": true, "ts": "...", "service": "comsol-java-sidecar"}`

## Supported methods

- `system.ping`
- `comsol.perform_action`
- `comsol.preview_model`
- `comsol.list_apis`

## Runtime modes

- Default mode is `mock`.
- When `MPH_AGENT_ENABLE_COMSOL=1` (or `COMSOL_HOME` / `COMSOL_JAR_DIR` is set), sidecar attempts reflective COMSOL Java API initialization.
- If reflective init fails, sidecar automatically falls back to `mock` mode and reports details in `system.ping -> data.comsol_bridge`.

## Build

This module currently uses Gradle (`build.gradle`) and the Shadow plugin to produce:

- `build/libs/comsol-java-sidecar-all.jar`

If Gradle wrapper is available:

```bash
./gradlew shadowJar
```

On Windows:

```powershell
.\gradlew.bat shadowJar
```

If wrapper is not committed, install Gradle locally and run:

```bash
gradle shadowJar
```

This module now includes `gradlew` / `gradlew.bat` and wrapper files.

## Run manually

```bash
java -jar build/libs/comsol-java-sidecar-all.jar
```

## Notes

- Current implementation is sidecar-protocol-complete and action-routed.
- Returned `model_path` / `artifact_path` values are normalized absolute filesystem paths.
- `solve.run` attempts real `ModelUtil.create/save` via reflection when COMSOL mode is active.
- Real COMSOL Java API execution hooks should be implemented behind `comsol.perform_action` branches.
