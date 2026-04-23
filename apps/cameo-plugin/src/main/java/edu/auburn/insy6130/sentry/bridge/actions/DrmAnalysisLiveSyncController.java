package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.simulation.StructuralFeatureListener;
import com.nomagic.magicdraw.simulation.ValuesManager;
import com.nomagic.magicdraw.simulation.values.ValueWrapper;
import com.nomagic.magicdraw.uml.Finder;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.StructuralFeature;
import edu.auburn.insy6130.sentry.bridge.http.BridgeHttpClient;
import edu.auburn.insy6130.sentry.bridge.http.BridgeResponse;
import edu.auburn.insy6130.sentry.bridge.state.BridgeSessionState;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;

public final class DrmAnalysisLiveSyncController {
    private static final DrmAnalysisLiveSyncController INSTANCE = new DrmAnalysisLiveSyncController();
    private static final String DRM_ANALYSIS_QUALIFIED_NAME = "SENTRY::Test::Design Reference Mission(DRM)::DRMAnalysis";
    private static final long SYNC_DEBOUNCE_MS = 150L;

    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor(new DaemonThreadFactory());
    private final Map<StructuralFeature, String> trackedFeatures = new LinkedHashMap<>();
    private final Map<String, StructuralFeature> trackedModelProperties = new LinkedHashMap<>();
    private final Map<String, Object> latestValues = new ConcurrentHashMap<>();
    private final StructuralFeatureListener listener = this::onValueUpdated;

    private ScheduledFuture<?> pendingSync;
    private boolean active;
    private String sessionId;
    private Object latestContext;
    private String lastStatus = "Live DRMAnalysis sync is idle.";

    private DrmAnalysisLiveSyncController() {
    }

    public static DrmAnalysisLiveSyncController instance() {
        return INSTANCE;
    }

    public synchronized String start() throws Exception {
        if (active) {
            return status();
        }

        Project project = ActionSupport.requireProject();
        if (project == null) {
            throw new IllegalStateException("No active project is open in MSOSA.");
        }

        this.sessionId = ActionSupport.ensureMissionSessionId();
        trackedFeatures.clear();
        trackedModelProperties.clear();
        latestValues.clear();
        latestContext = null;

        com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class drmAnalysis = Finder.byQualifiedName()
            .find(project, DRM_ANALYSIS_QUALIFIED_NAME, com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class.class);
        if (drmAnalysis == null) {
            drmAnalysis = Finder.byNameRecursively()
                .find(project, com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class.class, "DRMAnalysis");
        }
        if (drmAnalysis == null) {
            throw new IllegalStateException("Unable to find DRMAnalysis in the active project.");
        }

        Map<String, String> propertyBindings = new LinkedHashMap<>();
        propertyBindings.put("currentMissionMode", "mission_mode");
        propertyBindings.put("missionTime", "mission_time_s");
        propertyBindings.put("realTime", "real_time");
        propertyBindings.put("playbackSpeed", "playback_speed");
        propertyBindings.put("rate", "simulation_rate_hz");
        propertyBindings.put("currentSpeed", "current_speed_mps");
        propertyBindings.put("currentPropulsionPower", "current_propulsion_power_w");
        propertyBindings.put("currentTotalPower", "current_total_power_w");
        propertyBindings.put("remainingScenarioEnergy", "remaining_energy_j");
        propertyBindings.put("distanceToBaseRemaining", "distance_to_base_m");
        propertyBindings.put("distanceToPerimeterRemaining", "distance_to_perimeter_m");
        propertyBindings.put("patrolDistanceRemaining", "patrol_distance_remaining_m");
        propertyBindings.put("trackTimeRemaining", "track_time_remaining_s");
        propertyBindings.put("tier1EngagementTimeRemaining", "tier1_engagement_time_remaining_s");
        propertyBindings.put("lowBatteryTriggered", "low_battery_triggered");
        propertyBindings.put("returnedEarly", "returned_early");
        propertyBindings.put("missionComplete", "mission_complete");
        propertyBindings.put("flightFeasibility", "flight_feasible");
        propertyBindings.put("enduranceFeasibility", "endurance_feasible");
        propertyBindings.put("configurationSuitability", "configuration_suitable");
        propertyBindings.put("returnEnergyRequired", "return_energy_required_j");
        propertyBindings.put("currentLoad", "current_load_w");

        List<String> missingProperties = new ArrayList<>();
        for (Map.Entry<String, String> binding : propertyBindings.entrySet()) {
            Property property = Finder.byNameRecursively().find(drmAnalysis, Property.class, binding.getKey());
            if (property == null) {
                missingProperties.add(binding.getKey());
                continue;
            }
            trackedFeatures.put(property, binding.getValue());
            trackedModelProperties.put(binding.getKey(), property);
            ValuesManager.registerFeatureListener(property, listener);
        }

        active = true;
        BridgeSessionState.instance().liveSyncActive(true);
        BridgeSessionState.instance().liveSyncTarget(DRM_ANALYSIS_QUALIFIED_NAME);
        scheduleSync();

        if (missingProperties.isEmpty()) {
            lastStatus = "Live DRMAnalysis sync active for " + DRM_ANALYSIS_QUALIFIED_NAME
                + " using session " + sessionId + ".";
        } else {
            lastStatus = "Live DRMAnalysis sync active for " + DRM_ANALYSIS_QUALIFIED_NAME
                + " using session " + sessionId
                + ". Missing optional properties: " + String.join(", ", missingProperties);
        }
        return lastStatus;
    }

    public synchronized String stop() {
        if (!active) {
            lastStatus = "Live DRMAnalysis sync is already idle.";
            return lastStatus;
        }

        for (StructuralFeature feature : trackedFeatures.keySet()) {
            ValuesManager.unregisterFeatureListener(feature, listener);
        }
        trackedFeatures.clear();
        trackedModelProperties.clear();
        latestValues.clear();
        latestContext = null;

        if (pendingSync != null) {
            pendingSync.cancel(false);
            pendingSync = null;
        }

        active = false;
        sessionId = null;
        BridgeSessionState.instance().liveSyncActive(false);
        BridgeSessionState.instance().liveSyncTarget(null);
        lastStatus = "Live DRMAnalysis sync stopped.";
        return lastStatus;
    }

    public synchronized String status() {
        if (!active) {
            return lastStatus;
        }
        return lastStatus
            + " Tracked features=" + trackedFeatures.size()
            + ", session=" + sessionId + ".";
    }

    private void onValueUpdated(Object context, StructuralFeature feature, ValueWrapper wrapper) {
        String key = trackedFeatures.get(feature);
        if (key == null || !active) {
            return;
        }
        latestContext = context;
        latestValues.put(key, wrapper.getValue());
        scheduleSync();
    }

    private synchronized void scheduleSync() {
        if (!active || sessionId == null || sessionId.isBlank()) {
            return;
        }
        if (pendingSync != null) {
            pendingSync.cancel(false);
        }
        pendingSync = executor.schedule(this::pushSnapshotSafely, SYNC_DEBOUNCE_MS, TimeUnit.MILLISECONDS);
    }

    private void pushSnapshotSafely() {
        try {
            pushSnapshot();
        } catch (Exception exception) {
            lastStatus = "Live DRMAnalysis sync failed: " + exception.getMessage();
        }
    }

    private void pushSnapshot() throws IOException, InterruptedException {
        String localSessionId;
        synchronized (this) {
            if (!active || sessionId == null || sessionId.isBlank()) {
                return;
            }
            localSessionId = sessionId;
        }

        String body = buildSyncBody();
        BridgeResponse response = BridgeHttpClient.instance().syncMissionSession(localSessionId, body);
        Object missionMode = latestValues.get("mission_mode");
        String pendingCommand = null;
        Integer commandRevision = null;
        Integer commandRevisionApplied = null;
        Integer routeRevision = null;
        Integer routeRevisionApplied = null;

        try {
            BridgeResponse bridgeView = BridgeHttpClient.instance().getMissionBridgeView(localSessionId);
            pendingCommand = BridgeHttpClient.extractStringField(bridgeView.body(), "pending_command_kind");
            commandRevision = BridgeHttpClient.extractIntegerField(bridgeView.body(), "command_revision");
            commandRevisionApplied = BridgeHttpClient.extractIntegerField(bridgeView.body(), "command_revision_applied");
            routeRevision = BridgeHttpClient.extractIntegerField(bridgeView.body(), "route_revision");
            routeRevisionApplied = BridgeHttpClient.extractIntegerField(bridgeView.body(), "route_revision_applied");
            applyPendingBridgeCommandIfAny(
                localSessionId,
                bridgeView.body(),
                pendingCommand,
                commandRevision,
                commandRevisionApplied
            );
        } catch (Exception ignored) {
            // Keep sync status useful even if the optional bridge-view fetch fails.
        }

        StringBuilder statusBuilder = new StringBuilder();
        statusBuilder.append("Live DRMAnalysis sync HTTP ").append(response.statusCode());
        if (missionMode != null) {
            statusBuilder.append(" mode=").append(missionMode);
        }
        if (pendingCommand != null && !pendingCommand.isBlank()) {
            statusBuilder.append(" pending=").append(pendingCommand);
        } else {
            statusBuilder.append(" pending=none");
        }
        if (commandRevision != null) {
            statusBuilder.append(" cmdRev=").append(commandRevision);
            if (commandRevisionApplied != null) {
                statusBuilder.append("/").append(commandRevisionApplied);
            }
        }
        if (routeRevision != null) {
            statusBuilder.append(" routeRev=").append(routeRevision);
            if (routeRevisionApplied != null) {
                statusBuilder.append("/").append(routeRevisionApplied);
            }
        }
        lastStatus = statusBuilder.toString();
    }

    private void applyPendingBridgeCommandIfAny(
        String localSessionId,
        String bridgeViewBody,
        String pendingCommand,
        Integer commandRevision,
        Integer commandRevisionApplied
    ) throws IOException, InterruptedException {
        if (!"set_playback_speed".equals(pendingCommand)) {
            return;
        }
        if (commandRevision == null) {
            return;
        }
        if (commandRevisionApplied != null && commandRevisionApplied >= commandRevision) {
            return;
        }
        if (latestContext == null) {
            lastStatus = "Live DRMAnalysis sync waiting for runtime context before applying playback-speed command.";
            return;
        }

        Double playbackSpeed = BridgeHttpClient.extractDoubleField(bridgeViewBody, "pending_playback_speed");
        Boolean realTime = BridgeHttpClient.extractBooleanField(bridgeViewBody, "pending_real_time");
        if (playbackSpeed == null) {
            lastStatus = "Live DRMAnalysis sync received set_playback_speed without a pending_playback_speed value.";
            return;
        }

        if (realTime != null) {
            updateTrackedProperty("realTime", realTime);
        }
        updateTrackedProperty("playbackSpeed", playbackSpeed);

        String ackJson = "{\"command_revision_applied\":" + commandRevision
            + ",\"note\":\"Applied playback speed from browser bridge.\"}";
        BridgeHttpClient.instance().acknowledgeMissionBridge(localSessionId, ackJson);
        lastStatus = "Live DRMAnalysis sync applied playback speed "
            + playbackSpeed + "x"
            + (realTime != null ? " realTime=" + realTime : "")
            + " cmdRev=" + commandRevision + ".";
    }

    private void updateTrackedProperty(String propertyName, Object newValue) {
        StructuralFeature feature = trackedModelProperties.get(propertyName);
        if (feature == null) {
            throw new IllegalStateException("Missing tracked DRMAnalysis property: " + propertyName);
        }
        Object oldValue = latestValues.get(trackedFeatures.get(feature));
        ValuesManager.updateValue(
            latestContext,
            feature,
            new ValueWrapper(oldValue, newValue, System.currentTimeMillis())
        );
        String apiKey = trackedFeatures.get(feature);
        if (apiKey != null) {
            latestValues.put(apiKey, newValue);
        }
    }

    private String buildSyncBody() {
        Map<String, Object> snapshot = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : latestValues.entrySet()) {
            snapshot.put(entry.getKey(), normalizeValue(entry.getValue()));
        }

        Object missionTimeSeconds = snapshot.get("mission_time_s");
        if (missionTimeSeconds instanceof Number) {
            snapshot.put("time_ms", ((Number) missionTimeSeconds).doubleValue() * 1000.0);
        }

        Object missionMode = snapshot.get("mission_mode");
        if (!snapshot.containsKey("mission_complete") && missionMode instanceof String) {
            String mode = (String) missionMode;
            snapshot.put(
                "mission_complete",
                mode.contains("MISSION_SUCCESS") || mode.contains("MISSION_FAIL")
            );
        }

        StringBuilder builder = new StringBuilder();
        builder.append("{\"modeled_state\":{");
        boolean needsComma = false;
        for (Map.Entry<String, Object> entry : snapshot.entrySet()) {
            if (Objects.equals(entry.getKey(), "return_energy_required_j")) {
                continue;
            }
            needsComma = appendJsonField(builder, needsComma, entry.getKey(), entry.getValue());
        }

        String attributesJson = "{\"source\":\"plugin_live_drmanalysis\",\"target\":\""
            + escapeJson(DRM_ANALYSIS_QUALIFIED_NAME) + "\"";
        Object returnEnergy = snapshot.get("return_energy_required_j");
        if (returnEnergy != null) {
            attributesJson += ",\"return_energy_required_j\":" + numericLiteral(returnEnergy);
        }
        attributesJson += "}";
        if (needsComma) {
            builder.append(',');
        }
        builder.append("\"attributes\":").append(attributesJson).append("}}");
        return builder.toString();
    }

    private static Object normalizeValue(Object value) {
        if (value instanceof Number || value instanceof Boolean || value instanceof String) {
            return value;
        }
        if (value instanceof NamedElement) {
            NamedElement named = (NamedElement) value;
            if (named.getQualifiedName() != null && !named.getQualifiedName().isBlank()) {
                return named.getQualifiedName();
            }
            if (named.getName() != null && !named.getName().isBlank()) {
                return named.getName();
            }
        }
        return value == null ? null : value.toString();
    }

    private static boolean appendJsonField(StringBuilder builder, boolean needsComma, String key, Object value) {
        if (value == null) {
            return needsComma;
        }
        if (needsComma) {
            builder.append(',');
        }
        builder.append('"').append(escapeJson(key)).append('"').append(':');
        if (value instanceof Number) {
            builder.append(numericLiteral(value));
        } else if (value instanceof Boolean) {
            builder.append(((Boolean) value) ? "true" : "false");
        } else {
            builder.append('"').append(escapeJson(String.valueOf(value))).append('"');
        }
        return true;
    }

    private static String numericLiteral(Object value) {
        return Double.toString(((Number) value).doubleValue());
    }

    private static String escapeJson(String value) {
        return value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r");
    }

    private static final class DaemonThreadFactory implements ThreadFactory {
        @Override
        public Thread newThread(Runnable runnable) {
            Thread thread = new Thread(runnable, "sentry-drm-live-sync");
            thread.setDaemon(true);
            return thread;
        }
    }
}
