package edu.auburn.insy6130.sentry.bridge.actions;

import com.nomagic.actions.AMConfigurator;
import com.nomagic.actions.ActionsCategory;
import com.nomagic.actions.ActionsManager;
import com.nomagic.actions.NMAction;
import com.nomagic.magicdraw.actions.MDActionsCategory;

import java.util.List;

public final class SentryMainMenuConfigurator implements AMConfigurator {
    private static final String CATEGORY_ID = "SENTRY_BRIDGE";
    private static final String CATEGORY_NAME = "SENTRY";

    private final List<NMAction> actions;

    public SentryMainMenuConfigurator(List<NMAction> actions) {
        this.actions = actions;
    }

    @Override
    public void configure(ActionsManager manager) {
        ActionsCategory category = (ActionsCategory) manager.getActionFor(CATEGORY_ID);
        if (category == null) {
            category = new MDActionsCategory(CATEGORY_ID, CATEGORY_NAME);
            category.setNested(true);
            manager.addCategory(category);
        }
        for (NMAction action : actions) {
            category.addAction(action);
        }
    }

    @Override
    public int getPriority() {
        return AMConfigurator.MEDIUM_PRIORITY;
    }
}
