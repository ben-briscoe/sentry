package edu.auburn.insy6130.sentry.bridge.state;

public final class BridgeSessionState {
    private static final BridgeSessionState INSTANCE = new BridgeSessionState();

    private String missionSessionId;
    private boolean liveSyncActive;
    private String liveSyncTarget;

    private BridgeSessionState() {
    }

    public static BridgeSessionState instance() {
        return INSTANCE;
    }

    public String missionSessionId() {
        return missionSessionId;
    }

    public void missionSessionId(String missionSessionId) {
        this.missionSessionId = missionSessionId;
    }

    public boolean hasMissionSession() {
        return missionSessionId != null && !missionSessionId.isBlank();
    }

    public void clearMissionSession() {
        missionSessionId = null;
    }

    public boolean liveSyncActive() {
        return liveSyncActive;
    }

    public void liveSyncActive(boolean liveSyncActive) {
        this.liveSyncActive = liveSyncActive;
    }

    public String liveSyncTarget() {
        return liveSyncTarget;
    }

    public void liveSyncTarget(String liveSyncTarget) {
        this.liveSyncTarget = liveSyncTarget;
    }
}
