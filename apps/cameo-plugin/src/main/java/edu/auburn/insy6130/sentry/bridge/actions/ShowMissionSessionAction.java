package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.BridgeResponse;

import java.awt.event.ActionEvent;

public final class ShowMissionSessionAction extends MDAction {
    public ShowMissionSessionAction() {
        super("SENTRY_BRIDGE_SHOW_MISSION_SESSION", "Show Mission Session", null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        String sessionId = ActionSupport.requireMissionSessionId();
        if (sessionId == null) {
            return;
        }

        try {
            BridgeResponse response = BridgeHttpClient.instance().getMissionSession(sessionId);
            ActionSupport.showMessage(
                "Mission session snapshot HTTP " + response.statusCode() + " body=" + response.body()
            );
        } catch (Exception exception) {
            ActionSupport.showMessage("Mission session fetch failed: " + exception.getMessage());
        }
    }
}
