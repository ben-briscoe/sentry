package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.BridgeResponse;
import edu.auburn.insy6130.sentry.bridge.state.BridgeSessionState;

final class ActionSupport {
    private ActionSupport() {
    }

    static void showMessage(String message) {
        Application.getInstance().getGUILog().showMessage(message);
    }

    static String requireMissionSessionId() {
        String sessionId = BridgeSessionState.instance().missionSessionId();
        if (sessionId == null || sessionId.isBlank()) {
            showMessage("No active SENTRY mission-service session. Run 'Create Mission Session' first.");
            return null;
        }
        return sessionId;
    }

    static String ensureMissionSessionId() throws Exception {
        String sessionId = BridgeSessionState.instance().missionSessionId();
        if (sessionId != null && !sessionId.isBlank()) {
            return sessionId;
        }

        BridgeResponse response = BridgeHttpClient.instance().createMissionSession();
        sessionId = BridgeHttpClient.extractSessionId(response.body());
        if (response.statusCode() >= 200 && response.statusCode() < 300 && sessionId != null) {
            BridgeSessionState.instance().missionSessionId(sessionId);
            return sessionId;
        }

        throw new IllegalStateException(
            "Mission session creation returned HTTP " + response.statusCode() + " body=" + response.body()
        );
    }

    static Project requireProject() {
        Project project = Application.getInstance().getProject();
        if (project == null) {
            showMessage("No active project is open in MSOSA.");
            return null;
        }
        return project;
    }
}
