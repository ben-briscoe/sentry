package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.actions.MDAction;

import java.awt.event.ActionEvent;

public final class ShowLiveDrmAnalysisSyncStatusAction extends MDAction {
    public ShowLiveDrmAnalysisSyncStatusAction() {
        super("SENTRY_BRIDGE_SHOW_LIVE_DRM_SYNC_STATUS", "Show Live DRMAnalysis Sync Status", null, null);
    }

    @Override
    public void actionPerformed(ActionEvent event) {
        ActionSupport.showMessage(DrmAnalysisLiveSyncController.instance().status());
    }
}
