package edu.auburn.insy6130.sentry.bridge.http;

public final class BridgeResponse {
    private final int statusCode;
    private final String body;

    public BridgeResponse(int statusCode, String body) {
        this.statusCode = statusCode;
        this.body = body;
    }

    public int statusCode() {
        return statusCode;
    }

    public String body() {
        return body;
    }
}
