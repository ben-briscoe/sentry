package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.BridgeResponse;

import java.awt.event.ActionEvent;

public final class ShowMissionBridgeViewAction extends MDAction {
    public ShowMissionBridgeViewAction() {
        super("SENTRY_BRIDGE_SHOW_MISSION_BRIDGE_VIEW", "Show Mission Bridge View", null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        String sessionId = ActionSupport.requireMissionSessionId();
        if (sessionId == null) {
            return;
        }

        try {
            BridgeResponse response = BridgeHttpClient.instance().getMissionBridgeView(sessionId);
            ActionSupport.showMessage(
                "Mission bridge view HTTP " + response.statusCode() + " body=" + response.body()
            );
        } catch (Exception exception) {
            ActionSupport.showMessage("Mission bridge view fetch failed: " + exception.getMessage());
        }
    }
}
