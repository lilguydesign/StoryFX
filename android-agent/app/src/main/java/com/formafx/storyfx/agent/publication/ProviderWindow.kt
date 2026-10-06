package com.formafx.storyfx.agent.publication

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo

/** Use the focused provider application, never a background chat or a System UI overlay. */
object ProviderWindow {
    fun root(service: AccessibilityService): AccessibilityNodeInfo? {
        val windows = service.windows
        val candidates = windows.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION && it.isFocused }
            .mapNotNull { it.root }.filter { it.packageName?.toString() == PublicationPolicy.provider }.distinct()
        if (candidates.size == 1) return candidates.single()
        if (windows.isNotEmpty()) return null
        return service.rootInActiveWindow?.takeIf { it.packageName?.toString() == PublicationPolicy.provider }
    }
}
