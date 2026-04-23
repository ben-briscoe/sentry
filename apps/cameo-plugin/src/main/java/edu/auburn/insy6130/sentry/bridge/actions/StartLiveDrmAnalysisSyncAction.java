package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;

import java.awt.event.ActionEvent;

public final class StartLiveDrmAnalysisSyncAction extends MDAction {
    public StartLiveDrmAnalysisSyncAction() {
        super("SENTRY_BRIDGE_START_LIVE_DRM_SYNC", "Start Live DRMAnalysis Sync", null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        try {
            String status = DrmAnalysisLiveSyncController.instance().start();
            ActionSupport.showMessage(status);
        } catch (Exception exception) {
            ActionSupport.showMessage("Start live DRMAnalysis sync failed: " + exception.getMessage());
        }
    }
}
