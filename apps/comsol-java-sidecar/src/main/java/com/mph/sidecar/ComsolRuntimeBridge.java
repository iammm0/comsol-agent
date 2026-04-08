package com.mph.sidecar;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;
import java.util.stream.Stream;

final class ComsolRuntimeBridge {
    private final boolean enabled;
    private final boolean available;
    private final String backendMode;
    private final String message;
    private final Class<?> modelUtilClass;
    private final List<String> jarPaths;
    private final Map<String, Object> runModels = new ConcurrentHashMap<>();

    private ComsolRuntimeBridge(
        boolean enabled,
        boolean available,
        String backendMode,
        String message,
        Class<?> modelUtilClass,
        List<String> jarPaths
    ) {
        this.enabled = enabled;
        this.available = available;
        this.backendMode = backendMode;
        this.message = message;
        this.modelUtilClass = modelUtilClass;
        this.jarPaths = jarPaths;
    }

    public static ComsolRuntimeBridge create() {
        final boolean enabled = isComsolRequested();
        if (!enabled) {
            return new ComsolRuntimeBridge(
                false,
                false,
                "mock",
                "COMSOL bridge disabled",
                null,
                Collections.emptyList()
            );
        }

        try {
            final List<Path> jarFiles = discoverJarFiles();
            if (jarFiles.isEmpty()) {
                return new ComsolRuntimeBridge(
                    true,
                    false,
                    "mock",
                    "COMSOL jars not found (set COMSOL_JAR_DIR or COMSOL_HOME)",
                    null,
                    Collections.emptyList()
                );
            }

            final URL[] urls = jarFiles
                .stream()
                .map(path -> {
                    try {
                        return path.toUri().toURL();
                    } catch (Exception ex) {
                        throw new RuntimeException(ex);
                    }
                })
                .toArray(URL[]::new);

            final URLClassLoader classLoader = new URLClassLoader(
                urls,
                ComsolRuntimeBridge.class.getClassLoader()
            );
            final Class<?> modelUtil = Class.forName(
                "com.comsol.model.util.ModelUtil",
                true,
                classLoader
            );

            invokeBestEffortStatic(modelUtil, "initStandalone", true);
            invokeBestEffortStatic(modelUtil, "initStandalone");

            final List<String> jarPaths = jarFiles
                .stream()
                .map(path -> path.toAbsolutePath().normalize().toString())
                .collect(Collectors.toList());

            return new ComsolRuntimeBridge(
                true,
                true,
                "comsol",
                "COMSOL bridge initialized",
                modelUtil,
                jarPaths
            );
        } catch (Exception ex) {
            return new ComsolRuntimeBridge(
                true,
                false,
                "mock",
                "COMSOL bridge init failed: " + compactError(ex),
                null,
                Collections.emptyList()
            );
        }
    }

    public String backendMode() {
        return this.backendMode;
    }

    public boolean isComsolActive() {
        return this.enabled && this.available;
    }

    public Map<String, Object> healthSnapshot() {
        final Map<String, Object> health = new HashMap<>();
        health.put("enabled", this.enabled);
        health.put("available", this.available);
        health.put("backend_mode", this.backendMode);
        health.put("message", this.message);
        health.put("jar_count", this.jarPaths.size());
        return health;
    }

    public void ensureModel(String runId) throws ReflectiveOperationException {
        if (!isComsolActive()) {
            return;
        }
        getOrCreateModel(runId);
    }

    public boolean solveAndSave(String runId, Path modelPath) throws ReflectiveOperationException {
        if (!isComsolActive()) {
            return false;
        }
        final Object model = getOrCreateModel(runId);

        // Solver execution is best-effort because method signatures differ by COMSOL version.
        invokeBestEffortInstance(model, "solve");
        invokeBestEffortInstance(model, "run");
        invokeBestEffortInstance(model, "runAll");

        invokeRequired(model, "save", modelPath.toString());
        return true;
    }

    private Object getOrCreateModel(String runId) throws ReflectiveOperationException {
        final String normalized = runId == null || runId.isBlank() ? "run" : runId;
        final Object existing = runModels.get(normalized);
        if (existing != null) {
            return existing;
        }

        final String modelTag = "model_" + sanitizeSegment(normalized);
        Object model;
        try {
            model = invokeRequiredStatic(this.modelUtilClass, "create", modelTag);
        } catch (ReflectiveOperationException firstError) {
            model = invokeRequiredStatic(this.modelUtilClass, "create");
        }
        runModels.put(normalized, model);
        return model;
    }

    private static boolean isComsolRequested() {
        final String forceMock = System.getenv("MPH_AGENT_MOCK_COMSOL");
        if ("1".equals(forceMock)) {
            return false;
        }
        final String toggle = System.getenv("MPH_AGENT_ENABLE_COMSOL");
        if (toggle != null && !toggle.trim().isEmpty()) {
            final String normalized = toggle.trim().toLowerCase();
            if ("0".equals(normalized) || "false".equals(normalized) || "off".equals(normalized)) {
                return false;
            }
            if ("1".equals(normalized) || "true".equals(normalized) || "on".equals(normalized)) {
                return true;
            }
        }
        return System.getenv("COMSOL_JAR_DIR") != null || System.getenv("COMSOL_HOME") != null;
    }

    private static List<Path> discoverJarFiles() {
        final LinkedHashSet<Path> roots = new LinkedHashSet<>();
        final String jarDirEnv = System.getenv("COMSOL_JAR_DIR");
        if (jarDirEnv != null && !jarDirEnv.isBlank()) {
            final String[] parts = jarDirEnv.split(java.io.File.pathSeparator);
            Arrays.stream(parts)
                .map(String::trim)
                .filter(item -> !item.isEmpty())
                .map(Paths::get)
                .forEach(roots::add);
        }

        final String comsolHome = System.getenv("COMSOL_HOME");
        if (comsolHome != null && !comsolHome.isBlank()) {
            final Path home = Paths.get(comsolHome);
            roots.add(home.resolve("plugins"));
            roots.add(home.resolve("Multiphysics").resolve("plugins"));
            roots.add(home.resolve("multiphysics").resolve("plugins"));
        }

        final List<Path> jarFiles = new ArrayList<>();
        for (Path root : roots) {
            if (root == null) {
                continue;
            }
            final Path normalized = root.toAbsolutePath().normalize();
            if (!Files.exists(normalized) || !Files.isDirectory(normalized)) {
                continue;
            }
            try (Stream<Path> stream = Files.walk(normalized, 2)) {
                stream
                    .filter(path -> Files.isRegularFile(path) && path.toString().toLowerCase().endsWith(".jar"))
                    .forEach(jarFiles::add);
            } catch (Exception ignored) {
                // Skip unreadable roots and keep probing other candidates.
            }
        }
        return jarFiles
            .stream()
            .map(path -> path.toAbsolutePath().normalize())
            .distinct()
            .collect(Collectors.toList());
    }

    private static Object invokeRequiredStatic(Class<?> type, String name, Object... args)
        throws ReflectiveOperationException {
        return invoke(type, null, true, name, args);
    }

    private static Object invokeRequired(Object target, String name, Object... args)
        throws ReflectiveOperationException {
        return invoke(target.getClass(), target, false, name, args);
    }

    private static void invokeBestEffortStatic(Class<?> type, String name, Object... args) {
        try {
            invoke(type, null, true, name, args);
        } catch (Exception ignored) {
            // No-op best-effort.
        }
    }

    private static void invokeBestEffortInstance(Object target, String name, Object... args) {
        try {
            invoke(target.getClass(), target, false, name, args);
        } catch (Exception ignored) {
            // No-op best-effort.
        }
    }

    private static Object invoke(
        Class<?> type,
        Object receiver,
        boolean requireStatic,
        String name,
        Object... args
    ) throws ReflectiveOperationException {
        Method lastCandidate = null;
        for (Method method : type.getMethods()) {
            if (!method.getName().equals(name)) {
                continue;
            }
            if (method.getParameterCount() != args.length) {
                continue;
            }
            final boolean isStatic = Modifier.isStatic(method.getModifiers());
            if (isStatic != requireStatic) {
                continue;
            }
            lastCandidate = method;
            try {
                method.setAccessible(true);
                return method.invoke(receiver, args);
            } catch (IllegalArgumentException ignored) {
                // Keep probing overloads.
            } catch (InvocationTargetException ex) {
                final Throwable cause = ex.getCause() == null ? ex : ex.getCause();
                throw new ReflectiveOperationException(cause.getMessage(), cause);
            }
        }

        final String owner = type.getName();
        if (lastCandidate != null) {
            throw new ReflectiveOperationException(
                "No compatible overload for " + owner + "#" + name + " with " + args.length + " args"
            );
        }
        throw new NoSuchMethodException(owner + "#" + name);
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

    private static String sanitizeSegment(String value) {
        final String source = value == null ? "item" : value;
        final String sanitized = source
            .replaceAll("[^a-zA-Z0-9._-]+", "_")
            .replaceAll("_+", "_")
            .replaceAll("^_", "")
            .replaceAll("_$", "");
        return sanitized.isEmpty() ? "item" : sanitized;
    }
}
