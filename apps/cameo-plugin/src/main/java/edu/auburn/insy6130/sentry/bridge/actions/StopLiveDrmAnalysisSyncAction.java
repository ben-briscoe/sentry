package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;

import java.awt.event.ActionEvent;

public final class StopLiveDrmAnalysisSyncAction extends MDAction {
    public StopLiveDrmAnalysisSyncAction() {
        super("SENTRY_BRIDGE_STOP_LIVE_DRM_SYNC", "Stop Live DRMAnalysis Sync", null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        ActionSupport.showMessage(DrmAnalysisLiveSyncController.instance().stop());
    }
}
