package edu.auburn.insy6130.sentry.bridge.config;

import java.net.URI;
import java.time.Duration;

public final class BridgeConfiguration {
    private static final String BASE_URL_PROPERTY = "sentry.bridge.baseUrl";
    private static final String BASE_URL_ENV = "SENTRY_BRIDGE_BASE_URL";
    private static final String CONNECT_TIMEOUT_PROPERTY = "sentry.bridge.connectTimeoutMs";
    private static final String REQUEST_TIMEOUT_PROPERTY = "sentry.bridge.requestTimeoutMs";

    private BridgeConfiguration() {
    }

    public static String baseUrl() {
        String candidate = System.getProperty(BASE_URL_PROPERTY);
        if (candidate == null || candidate.isBlank()) {
            candidate = System.getenv(BASE_URL_ENV);
        }
        if (candidate == null || candidate.isBlank()) {
            return "http://127.0.0.1:8000";
        }
        return candidate.endsWith("/") ? candidate.substring(0, candidate.length() - 1) : candidate;
    }

    public static URI apiUri(String path) {
        String normalized = path.startsWith("/") ? path : "/" + path;
        return URI.create(baseUrl() + normalized);
    }

    public static Duration connectTimeout() {
        return Duration.ofMillis(longProperty(CONNECT_TIMEOUT_PROPERTY, 3000L));
    }

    public static Duration requestTimeout() {
        return Duration.ofMillis(longProperty(REQUEST_TIMEOUT_PROPERTY, 5000L));
    }

    private static long longProperty(String name, long fallback) {
        String raw = System.getProperty(name);
        if (raw == null || raw.isBlank()) {
            return fallback;
        }
        try {
            return Long.parseLong(raw);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }
}
