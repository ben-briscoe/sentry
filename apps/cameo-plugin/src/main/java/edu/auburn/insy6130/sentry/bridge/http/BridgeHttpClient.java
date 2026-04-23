package edu.auburn.insy6130.sentry.bridge.http;

import edu.auburn.insy6130.sentry.bridge.config.BridgeConfiguration;

import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class BridgeHttpClient {
    private static final BridgeHttpClient INSTANCE = new BridgeHttpClient();
    private static final Pattern SESSION_ID_PATTERN = Pattern.compile("\"session_id\"\\s*:\\s*\"([^\"]+)\"");

    private final HttpClient client = HttpClient.newBuilder()
        .connectTimeout(BridgeConfiguration.connectTimeout())
        .version(HttpClient.Version.HTTP_1_1)
        .build();

    private BridgeHttpClient() {
    }

    public static BridgeHttpClient instance() {
        return INSTANCE;
    }

    public HealthCheckResult pingHealth() throws IOException, InterruptedException {
        HttpResponse<String> response = send("GET", "/api/health", null);
        return new HealthCheckResult(response.statusCode(), response.body());
    }

    public BridgeResponse createMissionSession() throws IOException, InterruptedException {
        HttpResponse<String> response = send("POST", "/api/mission/session", "{}");
        return new BridgeResponse(response.statusCode(), response.body());
    }

    public BridgeResponse getMissionSession(String sessionId) throws IOException, InterruptedException {
        HttpResponse<String> response = send("GET", "/api/mission/" + sessionId, null);
        return new BridgeResponse(response.statusCode(), response.body());
    }

    public BridgeResponse getMissionBridgeView(String sessionId) throws IOException, InterruptedException {
        HttpResponse<String> response = send("GET", "/api/mission/" + sessionId + "/bridge", null);
        return new BridgeResponse(response.statusCode(), response.body());
    }

    public BridgeResponse applyMissionCommand(String sessionId, String commandJson) throws IOException, InterruptedException {
        HttpResponse<String> response = send("POST", "/api/mission/" + sessionId + "/command", commandJson);
        return new BridgeResponse(response.statusCode(), response.body());
    }

    public BridgeResponse syncMissionSession(String sessionId, String syncJson) throws IOException, InterruptedException {
        HttpResponse<String> response = send("POST", "/api/mission/" + sessionId + "/sync", syncJson);
        return new BridgeResponse(response.statusCode(), response.body());
    }

    public BridgeResponse acknowledgeMissionBridge(String sessionId, String ackJson) throws IOException, InterruptedException {
        HttpResponse<String> response = send("POST", "/api/mission/" + sessionId + "/bridge/ack", ackJson);
        return new BridgeResponse(response.statusCode(), response.body());
    }

    public static String extractSessionId(String responseBody) {
        return extractStringField(responseBody, "session_id");
    }

    public static String extractStringField(String responseBody, String fieldName) {
        Pattern pattern = Pattern.compile("\"" + Pattern.quote(fieldName) + "\"\\s*:\\s*\"([^\"]*)\"");
        Matcher matcher = pattern.matcher(responseBody);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return null;
    }

    public static Integer extractIntegerField(String responseBody, String fieldName) {
        Pattern pattern = Pattern.compile("\"" + Pattern.quote(fieldName) + "\"\\s*:\\s*(\\d+)");
        Matcher matcher = pattern.matcher(responseBody);
        if (matcher.find()) {
            return Integer.parseInt(matcher.group(1));
        }
        return null;
    }

    public static Double extractDoubleField(String responseBody, String fieldName) {
        Pattern pattern = Pattern.compile("\"" + Pattern.quote(fieldName) + "\"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)");
        Matcher matcher = pattern.matcher(responseBody);
        if (matcher.find()) {
            return Double.parseDouble(matcher.group(1));
        }
        return null;
    }

    public static Boolean extractBooleanField(String responseBody, String fieldName) {
        Pattern pattern = Pattern.compile("\"" + Pattern.quote(fieldName) + "\"\\s*:\\s*(true|false)");
        Matcher matcher = pattern.matcher(responseBody);
        if (matcher.find()) {
            return Boolean.parseBoolean(matcher.group(1));
        }
        return null;
    }

    private HttpResponse<String> send(String method, String path, String jsonBody) throws IOException, InterruptedException {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
            .timeout(BridgeConfiguration.requestTimeout())
            .uri(BridgeConfiguration.apiUri(path))
            .version(HttpClient.Version.HTTP_1_1)
            .header("Accept", "application/json");

        if (jsonBody != null) {
            builder.header("Content-Type", "application/json");
        }

        if ("POST".equalsIgnoreCase(method)) {
            builder.POST(HttpRequest.BodyPublishers.ofString(jsonBody == null ? "" : jsonBody));
        } else {
            builder.GET();
        }

        return client.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }
}
