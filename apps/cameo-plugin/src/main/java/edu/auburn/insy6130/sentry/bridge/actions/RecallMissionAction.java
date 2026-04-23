package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.BridgeResponse;

import java.awt.event.ActionEvent;

public final class RecallMissionAction extends MDAction {
    private static final String COMMAND_BODY = "{\"kind\":\"recall\"}";

    public RecallMissionAction() {
        super("SENTRY_BRIDGE_RECALL_MISSION", "Recall Mission", null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        String sessionId = ActionSupport.requireMissionSessionId();
        if (sessionId == null) {
            return;
        }

        try {
            BridgeResponse response = BridgeHttpClient.instance().applyMissionCommand(sessionId, COMMAND_BODY);
            ActionSupport.showMessage(
                "Recall mission HTTP " + response.statusCode() + " body=" + response.body()
            );
        } catch (Exception exception) {
            ActionSupport.showMessage("Recall mission failed: " + exception.getMessage());
        }
    }
}
