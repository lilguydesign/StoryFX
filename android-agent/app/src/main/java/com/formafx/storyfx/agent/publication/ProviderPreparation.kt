package com.formafx.storyfx.agent.publication

import android.accessibilityservice.AccessibilityService
import android.app.KeyguardManager
import android.os.Build

/** Only dismiss Android's notification shade; never press Back in an unknown app. */
object ProviderPreparation {
    fun dismissShade(service: AccessibilityService) {
        val manager = service.getSystemService(KeyguardManager::class.java)
        check(!manager.isDeviceLocked && !manager.isKeyguardLocked)
        if (service.rootInActiveWindow?.packageName?.toString() != KeyguardShape.system) return
        if (Build.VERSION.SDK_INT < 31) error("NOTIFICATION_SHADE_ACTION_UNAVAILABLE")
        val action = AccessibilityService.GLOBAL_ACTION_DISMISS_NOTIFICATION_SHADE
        check(service.systemActions.any { it.id == action })
        check(service.performGlobalAction(action))
    }
}
