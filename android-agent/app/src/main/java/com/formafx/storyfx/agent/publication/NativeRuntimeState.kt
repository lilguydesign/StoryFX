package com.formafx.storyfx.agent.publication

import org.json.JSONObject

/** Physical availability only; image permission does not imply video permission or provider readiness. */
data class NativeRuntimeState(
    val globalEnabled: Boolean, val serviceReady: Boolean, val accessibilityEnabled: Boolean,
    val screenUnlocked: Boolean, val mediaPermission: Boolean
) {
    init { require(!serviceReady || accessibilityEnabled) }

    fun toJson() = JSONObject().put("contract_version", 1).put("global_enabled", globalEnabled)
        .put("service_ready", serviceReady).put("accessibility_enabled", accessibilityEnabled)
        .put("screen_unlocked", screenUnlocked).put("media_permission", mediaPermission)
}
