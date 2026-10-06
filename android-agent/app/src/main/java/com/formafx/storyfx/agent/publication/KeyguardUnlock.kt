package com.formafx.storyfx.agent.publication

import android.app.KeyguardManager
import android.content.Intent
import android.os.PowerManager
import android.view.accessibility.AccessibilityNodeInfo
import com.formafx.storyfx.agent.EncryptedStore

/** One persisted attempt on a recognized numeric System UI keypad; no screen logging. */
class KeyguardUnlock(private val service: PublicationService, private val ui: (() -> Unit) -> Unit) {
    private val manager get() = service.getSystemService(KeyguardManager::class.java)
    private fun locked() = manager.isDeviceLocked || manager.isKeyguardLocked
    private fun interactive() = service.getSystemService(PowerManager::class.java).isInteractive
    private fun nodes(): List<AccessibilityNodeInfo> {
        val root = service.rootInActiveWindow ?: return emptyList()
        if (root.packageName?.toString() != KeyguardShape.system) return emptyList()
        val found = mutableListOf<AccessibilityNodeInfo>()
        fun walk(node: AccessibilityNodeInfo) {
            check(found.size < 1000)
            if (node.isVisibleToUser) found.add(node)
            for (i in 0 until node.childCount) node.getChild(i)?.let(::walk)
        }
        walk(root)
        return found
    }
    private fun entry(values: List<AccessibilityNodeInfo>) = values.singleOrNull {
        it.packageName?.toString() == KeyguardShape.system &&
            it.viewIdResourceName == "${KeyguardShape.system}:id/pinEntry" && it.isPassword
    }
    private fun click(target: AccessibilityNodeInfo) {
        var current: AccessibilityNodeInfo? = target
        repeat(4) {
            check(current?.packageName?.toString() == KeyguardShape.system)
            if (current?.isClickable == true) {
                check(current!!.performAction(AccessibilityNodeInfo.ACTION_CLICK)); return
            }
            current = current?.parent
        }
        error("KEYGUARD_CONTROL_UNAVAILABLE")
    }
    fun attempt(store: EncryptedStore, authorize: () -> Boolean): Boolean {
        if (!locked() && interactive()) { store.unlockSucceeded(); return true }
        if (store.unlockAttempted() || !store.publicationEnabled() || !authorize()) return false
        val pin = store.unlockPin() ?: return false
        try {
            ui { service.startActivity(Intent(service, UnlockActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            Thread.sleep(300)
            if (!locked() && interactive()) { store.unlockSucceeded(); return true }
            var recognized = false
            repeat(20) {
                if (!recognized) {
                    ui {
                        val values = nodes()
                        recognized = KeyguardShape.accepts(values.firstOrNull()?.packageName?.toString().orEmpty(),
                            entry(values)?.text.isNullOrEmpty() && entry(values) != null,
                            values.mapNotNull { it.viewIdResourceName }.toSet())
                    }
                    if (!recognized) Thread.sleep(300)
                }
            }
            if (!recognized || !authorize()) return false
            store.markUnlockAttempt()
            for (digit in pin) {
                if (!locked()) break
                check(authorize())
                ui {
                    check(locked())
                    val values = nodes(); check(entry(values) != null)
                    val target = values.single { it.viewIdResourceName == "${KeyguardShape.system}:id/key$digit" }
                    click(target)
                }
                Thread.sleep(100)
            }
            if (locked()) {
                check(authorize())
                ui {
                    val values = nodes(); check(entry(values) != null && locked())
                    click(values.single { it.viewIdResourceName == "${KeyguardShape.system}:id/key_enter" })
                }
            }
            Thread.sleep(1500)
            if (locked()) return false
            store.unlockSucceeded()
            return true
        } catch (_: Exception) { return false }
        finally { pin.fill('\u0000') }
    }
}
