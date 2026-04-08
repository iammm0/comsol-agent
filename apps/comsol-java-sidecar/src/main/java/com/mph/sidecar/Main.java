package com.mph.sidecar;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public final class Main {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final String TINY_PNG_BASE64 =
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn6mSgAAAAASUVORK5CYII=";

    private static final List<Map<String, Object>> API_REGISTRY = List.of(
        api("api_modelutil_create", "com.comsol.model.util.ModelUtil", "create"),
        api("api_model_save", "com.comsol.model.Model", "save"),
        api("api_geom_create", "com.comsol.model.geom.GeomFeature", "create"),
        api("api_phys_add", "com.comsol.model.physics.PhysicsList", "create"),
        api("api_mesh_run", "com.comsol.model.mesh.MeshSequence", "run"),
        api("api_study_create", "com.comsol.model.study.StudyList", "create"),
        api("api_solver_run", "com.comsol.model.study.Study", "run")
    );
    private static final ComsolRuntimeBridge COMSOL_BRIDGE = ComsolRuntimeBridge.create();

    private Main() {
    }

    public static void main(String[] args) throws IOException {
        final BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
        final PrintWriter writer = new PrintWriter(System.out, true);

        writer.println(jsonLine(readyEnvelope()));

        String line;
        while ((line = reader.readLine()) != null) {
            final String trimmed = line.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            try {
                final Map<String, Object> request = OBJECT_MAPPER.readValue(
                    trimmed,
                    new TypeReference<Map<String, Object>>() {
                    }
                );
                final Map<String, Object> response = handleRequest(request);
                writer.println(jsonLine(response));
            } catch (Exception ex) {
                writer.println(
                    jsonLine(
                        errorEnvelope("unknown", "INVALID_REQUEST", "Invalid request: " + ex.getMessage())
                    )
                );
            }
        }
    }

    private static Map<String, Object> handleRequest(Map<String, Object> request) {
        final String id = String.valueOf(request.getOrDefault("id", "unknown"));
        final String method = String.valueOf(request.getOrDefault("method", ""));
        final Map<String, Object> params = asMap(request.get("params"));

        switch (method) {
            case "system.ping":
                return successEnvelope(
                    id,
                    "pong",
                    mapOf(
                        "service", "comsol-java-sidecar",
                        "ts", Instant.now().toString(),
                        "version", "1.0.0",
                        "backend_mode", backendMode(),
                        "comsol_bridge", COMSOL_BRIDGE.healthSnapshot(),
                        "workspace_root", resolveWorkspaceRoot().toString(),
                        "java_version", System.getProperty("java.version")
                    )
                );
            case "comsol.perform_action":
                return handleComsolAction(id, params);
            case "comsol.preview_model":
                return handlePreviewModel(id, params);
            case "comsol.list_apis":
                return handleListApis(id, params);
            default:
                return errorEnvelope(id, "UNKNOWN_METHOD", "Unknown method: " + method);
        }
    }

    private static Map<String, Object> readyEnvelope() {
        return mapOf(
            "_ready", true,
            "ts", Instant.now().toString(),
            "service", "comsol-java-sidecar",
            "backend_mode", backendMode()
        );
    }

    private static Map<String, Object> successEnvelope(
        String id,
        String message,
        Map<String, Object> data
    ) {
        final Map<String, Object> result = new HashMap<>();
        result.put("id", id);
        result.put("ok", true);
        result.put("message", message);
        result.put("data", data);
        result.put("ts", Instant.now().toString());
        return result;
    }

    private static Map<String, Object> errorEnvelope(String id, String code, String message) {
        final Map<String, Object> result = new HashMap<>();
        result.put("id", id);
        result.put("ok", false);
        result.put("message", message);
        result.put(
            "data",
            mapOf(
                "code", code,
                "message", message
            )
        );
        result.put("ts", Instant.now().toString());
        return result;
    }

    private static String jsonLine(Map<String, Object> value) throws IOException {
        return OBJECT_MAPPER.writeValueAsString(value);
    }

    private static Map<String, Object> handleComsolAction(String id, Map<String, Object> params) {
        final String runId = asString(params.get("runId"), "run_" + System.currentTimeMillis());
        final String runSegment = sanitizeFileSegment(runId);
        final Map<String, Object> action = asMap(params.get("action"));
        final String actionType = asString(action.get("type"), "");

        if (actionType.isEmpty()) {
            return errorEnvelope(id, "VALIDATION_ERROR", "Missing action.type");
        }

        try {
            switch (actionType) {
                case "geometry.create":
                    final String geometryDetail = ensureModelBestEffort(runId, actionType, "Geometry command accepted");
                    return successEnvelope(
                        id,
                        "Geometry feature prepared",
                        mapOf(
                            "run_id", runId,
                            "action_type", actionType,
                            "feature", asString(action.get("feature"), "unknown"),
                            "detail", geometryDetail,
                            "backend_mode", backendMode()
                        )
                    );
                case "physics.add":
                    final String physicsDetail = ensureModelBestEffort(runId, actionType, "Physics command accepted");
                    return successEnvelope(
                        id,
                        "Physics feature prepared",
                        mapOf(
                            "run_id", runId,
                            "action_type", actionType,
                            "feature", asString(action.get("feature"), "unknown"),
                            "detail", physicsDetail,
                            "backend_mode", backendMode()
                        )
                    );
                case "mesh.generate":
                    final String meshDetail = ensureModelBestEffort(runId, actionType, "Mesh command accepted");
                    return successEnvelope(
                        id,
                        "Mesh generated",
                        mapOf(
                            "run_id", runId,
                            "action_type", actionType,
                            "feature", asString(action.get("feature"), "unknown"),
                            "detail", meshDetail,
                            "backend_mode", backendMode()
                        )
                    );
                case "study.setup":
                    final String studyDetail = ensureModelBestEffort(runId, actionType, "Study setup accepted");
                    return successEnvelope(
                        id,
                        "Study configured",
                        mapOf(
                            "run_id", runId,
                            "action_type", actionType,
                            "feature", asString(action.get("feature"), "unknown"),
                            "detail", studyDetail,
                            "backend_mode", backendMode()
                        )
                    );
                case "solve.run": {
                    final Path modelFile = resolveRelativeToWorkspace("models/" + runSegment + ".mph");
                    final Path logFile = resolveRelativeToWorkspace("models/" + runSegment + ".log");

                    boolean solvedWithComsol = false;
                    String solveDetail = "Solve completed in mock mode";
                    if (COMSOL_BRIDGE.isComsolActive()) {
                        try {
                            solvedWithComsol = COMSOL_BRIDGE.solveAndSave(runId, modelFile);
                            if (solvedWithComsol) {
                                solveDetail = "Solve completed via COMSOL Java API bridge";
                            }
                        } catch (ReflectiveOperationException ex) {
                            solveDetail = "COMSOL bridge solve failed, fallback to mock: " + compactError(ex);
                        }
                    }

                    if (!solvedWithComsol) {
                        writeTextFile(modelFile, "# Placeholder mph artifact generated by Java sidecar\nrunId=" + runId + "\n");
                    }
                    writeTextFile(
                        logFile,
                        solveDetail + "\ncompleted_at=" + Instant.now() + "\n"
                    );
                    return successEnvelope(
                        id,
                        solvedWithComsol ? "Solve finished (COMSOL bridge)" : "Solve finished",
                        mapOf(
                            "run_id", runId,
                            "action_type", actionType,
                            "model_path", modelFile.toString(),
                            "artifact_path", logFile.toString(),
                            "artifact_kind", "log",
                            "artifact_mime", "text/plain",
                            "detail", solveDetail,
                            "backend_mode", backendMode()
                        )
                    );
                }
                case "postprocess.export": {
                    final String artifact = asString(action.get("artifact"), "png");
                    if ("csv".equals(artifact)) {
                        final Path csvFile = resolveRelativeToWorkspace("models/" + runSegment + "_result.csv");
                        writeTextFile(csvFile, "x,y,value\n0,0,1\n");
                        return successEnvelope(
                            id,
                            "Postprocess exported",
                            mapOf(
                                "run_id", runId,
                                "action_type", actionType,
                                "artifact_path", csvFile.toString(),
                                "artifact_kind", "result_csv",
                                "artifact_mime", "text/csv",
                                "backend_mode", backendMode()
                            )
                        );
                    }

                    final Path pngFile = resolveRelativeToWorkspace("models/" + runSegment + "_result.png");
                    writeBinaryFile(pngFile, Base64.getDecoder().decode(TINY_PNG_BASE64));
                    return successEnvelope(
                        id,
                        "Postprocess exported",
                        mapOf(
                            "run_id", runId,
                            "action_type", actionType,
                            "artifact_path", pngFile.toString(),
                            "artifact_kind", "mesh_png",
                            "artifact_mime", "image/png",
                            "backend_mode", backendMode()
                        )
                    );
                }
                default:
                    return errorEnvelope(id, "UNSUPPORTED_ACTION", "Unsupported action.type: " + actionType);
            }
        } catch (IOException ex) {
            return errorEnvelope(id, "IO_ERROR", "Artifact write failed: " + ex.getMessage());
        }
    }

    private static Map<String, Object> handlePreviewModel(String id, Map<String, Object> params) {
        final String path = asString(params.get("path"), "");
        if (path.isEmpty()) {
            return errorEnvelope(id, "VALIDATION_ERROR", "Missing params.path");
        }

        String fileName = "model";
        try {
            final String rawName = Paths.get(path).getFileName().toString();
            if (!rawName.isEmpty()) {
                fileName = rawName;
            }
        } catch (InvalidPathException ignored) {
            // fallback to default name
        }

        final String noExt = fileName.endsWith(".mph")
            ? fileName.substring(0, fileName.length() - 4)
            : fileName;
        final String safeBase = sanitizeFileSegment(noExt);
        final Path previewPath;

        try {
            previewPath = resolveRelativeToWorkspace("models/" + safeBase + "_preview.png");
            writeBinaryFile(previewPath, Base64.getDecoder().decode(TINY_PNG_BASE64));
        } catch (IOException ex) {
            return errorEnvelope(id, "IO_ERROR", "Preview export failed: " + ex.getMessage());
        }

        return successEnvelope(
            id,
            "Preview exported",
            mapOf(
                "image_base64", TINY_PNG_BASE64,
                "artifact_path", previewPath.toString(),
                "artifact_kind", "mesh_png",
                "artifact_mime", "image/png",
                "backend_mode", backendMode()
            )
        );
    }

    private static Map<String, Object> handleListApis(String id, Map<String, Object> params) {
        final String query = asString(params.get("query"), "").trim().toLowerCase();
        final int limit = Math.max(1, asInt(params.get("limit"), 200));
        final int offset = Math.max(0, asInt(params.get("offset"), 0));

        final List<Map<String, Object>> filtered = API_REGISTRY
            .stream()
            .filter(item -> {
                if (query.isEmpty()) {
                    return true;
                }
                final String wrapper = asString(item.get("wrapper_name"), "").toLowerCase();
                final String owner = asString(item.get("owner"), "").toLowerCase();
                final String methodName = asString(item.get("method_name"), "").toLowerCase();
                return wrapper.contains(query) || owner.contains(query) || methodName.contains(query);
            })
            .collect(Collectors.toList());

        final int total = filtered.size();
        final int from = Math.min(offset, total);
        final int to = Math.min(from + limit, total);
        final List<Map<String, Object>> window = new ArrayList<>(filtered.subList(from, to));

        return successEnvelope(
            id,
            "APIs listed",
            mapOf(
                "apis", window,
                "total", total,
                "limit", limit,
                "offset", from
            )
        );
    }

    private static Map<String, Object> asMap(Object value) {
        if (value instanceof Map) {
            final Map<?, ?> source = (Map<?, ?>) value;
            final Map<String, Object> mapped = new HashMap<>();
            for (Map.Entry<?, ?> entry : source.entrySet()) {
                mapped.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return mapped;
        }
        return new HashMap<>();
    }

    private static String asString(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        final String result = String.valueOf(value);
        return result.isEmpty() ? fallback : result;
    }

    private static int asInt(Object value, int fallback) {
        if (value == null) {
            return fallback;
        }
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static Map<String, Object> api(String wrapperName, String owner, String methodName) {
        return mapOf(
            "wrapper_name", wrapperName,
            "owner", owner,
            "method_name", methodName
        );
    }

    private static String backendMode() {
        return COMSOL_BRIDGE.backendMode();
    }

    private static String ensureModelBestEffort(String runId, String actionType, String fallbackDetail) {
        if (!COMSOL_BRIDGE.isComsolActive()) {
            return fallbackDetail;
        }
        try {
            COMSOL_BRIDGE.ensureModel(runId);
            return fallbackDetail + " (COMSOL bridge active)";
        } catch (ReflectiveOperationException ex) {
            return fallbackDetail + " (COMSOL bridge fallback on " + actionType + ": " + compactError(ex) + ")";
        }
    }

    private static String compactError(Throwable error) {
        if (error == null) {
            return "unknown";
        }
        final String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) {
            return error.getClass().getSimpleName();
        }
        return message.length() <= 180 ? message : message.substring(0, 180) + "...";
    }

    private static Path resolveWorkspaceRoot() {
        final String fromEnv = System.getenv("MPH_AGENT_ROOT");
        if (fromEnv != null && !fromEnv.trim().isEmpty()) {
            return Paths.get(fromEnv).toAbsolutePath().normalize();
        }
        return Paths.get("").toAbsolutePath().normalize();
    }

    private static Path ensureModelsRoot() throws IOException {
        final Path modelsRoot = resolveWorkspaceRoot().resolve("models").normalize();
        Files.createDirectories(modelsRoot);
        return modelsRoot;
    }

    private static void writeTextFile(Path filePath, String content) throws IOException {
        Files.createDirectories(filePath.getParent());
        Files.write(filePath, content.getBytes(StandardCharsets.UTF_8));
    }

    private static void writeBinaryFile(Path filePath, byte[] bytes) throws IOException {
        Files.createDirectories(filePath.getParent());
        Files.write(filePath, bytes);
    }

    private static Path resolveRelativeToWorkspace(String relativePath) throws IOException {
        final Path modelsRoot = ensureModelsRoot();
        final String normalized = relativePath.replace('\\', '/');
        final String suffix = normalized.startsWith("models/")
            ? normalized.substring("models/".length())
            : normalized;
        final Path resolved = modelsRoot.resolve(suffix).normalize();
        if (!resolved.startsWith(modelsRoot)) {
            throw new IOException("Path escapes models root: " + relativePath);
        }
        return resolved;
    }

    private static String sanitizeFileSegment(String value) {
        final String source = value == null ? "item" : value;
        final String sanitized = source
            .replaceAll("[^a-zA-Z0-9._-]+", "_")
            .replaceAll("_+", "_")
            .replaceAll("^_", "")
            .replaceAll("_$", "");
        return sanitized.isEmpty() ? "item" : sanitized;
    }

    private static Map<String, Object> mapOf(Object... kv) {
        final Map<String, Object> map = new HashMap<>();
        for (int i = 0; i < kv.length - 1; i += 2) {
            map.put(String.valueOf(kv[i]), kv[i + 1]);
        }
        return map;
    }
}
