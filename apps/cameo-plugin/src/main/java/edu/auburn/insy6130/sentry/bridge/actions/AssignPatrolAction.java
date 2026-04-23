package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.BridgeResponse;

import java.awt.event.ActionEvent;

public final class AssignPatrolAction extends MDAction {
    private static final String COMMAND_BODY = "{\"kind\":\"assign_patrol\"}";

    public AssignPatrolAction() {
        super("SENTRY_BRIDGE_ASSIGN_PATROL", "Assign Patrol", null, null);
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
                "Assign patrol HTTP " + response.statusCode() + " body=" + response.body()
            );
        } catch (Exception exception) {
            ActionSupport.showMessage("Assign patrol failed: " + exception.getMessage());
        }
    }
}
