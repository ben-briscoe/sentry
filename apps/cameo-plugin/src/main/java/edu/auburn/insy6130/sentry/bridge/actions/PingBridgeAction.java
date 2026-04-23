package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;
import com.nomagic.magicdraw.core.Application;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.HealthCheckResult;

import java.awt.event.ActionEvent;

public final class PingBridgeAction extends MDAction {
    public PingBridgeAction() {
        this("SENTRY_BRIDGE_PING", "Ping SENTRY Bridge");
    }

    public PingBridgeAction(String id, String name) {
        super(id, name, null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        try {
            HealthCheckResult result = BridgeHttpClient.instance().pingHealth();
            Application.getInstance()
                .getGUILog()
                .showMessage(
                    "SENTRY bridge reachable: HTTP "
                        + result.statusCode()
                        + " body="
                        + result.body()
                );
        } catch (Exception exception) {
            Application.getInstance()
                .getGUILog()
                .showMessage("SENTRY bridge ping failed: " + exception.getMessage());
        }
    }
}
