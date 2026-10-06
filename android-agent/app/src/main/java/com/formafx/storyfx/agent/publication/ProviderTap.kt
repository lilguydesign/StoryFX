package com.formafx.storyfx.agent.publication

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.app.KeyguardManager
import android.graphics.Path
import android.graphics.Rect
import android.os.PowerManager
import android.view.accessibility.AccessibilityManager

/** Only the exact, bounded provider node resolved locally may request this tap. */
object ProviderTap {
    fun perform(service: AccessibilityService, x: Int, y: Int): Boolean {
        val lock = service.getSystemService(KeyguardManager::class.java)
        check(!lock.isDeviceLocked && !lock.isKeyguardLocked)
        check(service.getSystemService(PowerManager::class.java).isInteractive)
        check(!service.getSystemService(AccessibilityManager::class.java).isTouchExplorationEnabled)
        check(service.magnificationController.scale == 1f)
        val root = requireNotNull(ProviderWindow.root(service))
        val bounds = Rect().also(root::getBoundsInScreen)
        check(bounds.contains(x, y))
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        return service.dispatchGesture(GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 80)).build(), null, null)
    }
}
