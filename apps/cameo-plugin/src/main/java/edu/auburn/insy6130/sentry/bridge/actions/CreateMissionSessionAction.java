package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.BridgeResponse;
import edu.auburn.insy6130.sentry.bridge.state.BridgeSessionState;

import java.awt.event.ActionEvent;

public final class CreateMissionSessionAction extends MDAction {
    public CreateMissionSessionAction() {
        super("SENTRY_BRIDGE_CREATE_MISSION_SESSION", "Create Mission Session", null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        try {
            BridgeResponse response = BridgeHttpClient.instance().createMissionSession();
            String sessionId = BridgeHttpClient.extractSessionId(response.body());
            if (response.statusCode() >= 200 && response.statusCode() < 300 && sessionId != null) {
                BridgeSessionState.instance().missionSessionId(sessionId);
                ActionSupport.showMessage(
                    "SENTRY mission-service session created: " + sessionId + " body=" + response.body()
                );
                return;
            }

            ActionSupport.showMessage(
                "Mission session creation returned HTTP " + response.statusCode() + " body=" + response.body()
            );
        } catch (Exception exception) {
            ActionSupport.showMessage("Mission session creation failed: " + exception.getMessage());
        }
    }
}
