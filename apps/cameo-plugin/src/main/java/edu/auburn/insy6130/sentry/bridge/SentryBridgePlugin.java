package edu.auburn.insy6130.sentry.bridge;

import com.nomagic.magicdraw.actions.ActionsConfiguratorsManager;
import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.plugins.Plugin;
import edu.auburn.insy6130.sentry.bridge.actions.AssignPatrolAction;
import edu.auburn.insy6130.sentry.bridge.actions.CreateMissionSessionAction;
import edu.auburn.insy6130.sentry.bridge.actions.PingBridgeAction;
import edu.auburn.insy6130.sentry.bridge.actions.RecallMissionAction;
import edu.auburn.insy6130.sentry.bridge.actions.SentryMainMenuConfigurator;
import edu.auburn.insy6130.sentry.bridge.actions.ShowLiveDrmAnalysisSyncStatusAction;
import edu.auburn.insy6130.sentry.bridge.actions.ShowMissionBridgeViewAction;
import edu.auburn.insy6130.sentry.bridge.actions.ShowMissionSessionAction;
import edu.auburn.insy6130.sentry.bridge.actions.StartLiveDrmAnalysisSyncAction;
import edu.auburn.insy6130.sentry.bridge.actions.StopLiveDrmAnalysisSyncAction;
import edu.auburn.insy6130.sentry.bridge.actions.DrmAnalysisLiveSyncController;
import edu.auburn.insy6130.sentry.bridge.config.BridgeConfiguration;

import java.util.List;

public final class SentryBridgePlugin extends Plugin {
    @Override
    public void init() {
        ActionsConfiguratorsManager.getInstance()
            .addMainMenuConfigurator(
                new SentryMainMenuConfigurator(
                    List.of(
                        new PingBridgeAction(),
                        new CreateMissionSessionAction(),
                        new ShowMissionSessionAction(),
                        new ShowMissionBridgeViewAction(),
                        new AssignPatrolAction(),
                        new RecallMissionAction(),
                        new StartLiveDrmAnalysisSyncAction(),
                        new StopLiveDrmAnalysisSyncAction(),
                        new ShowLiveDrmAnalysisSyncStatusAction()
                    )
                )
            );
        Application.getInstance()
            .getGUILog()
            .showMessage("SENTRY Bridge plugin initialized. Base URL: " + BridgeConfiguration.baseUrl());
    }

    @Override
    public boolean close() {
        DrmAnalysisLiveSyncController.instance().stop();
        return true;
    }

    @Override
    public boolean isSupported() {
        return true;
    }
}
