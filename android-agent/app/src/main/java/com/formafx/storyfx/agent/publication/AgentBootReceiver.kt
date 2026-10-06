package com.formafx.storyfx.agent.publication

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.formafx.storyfx.agent.AgentSchedule
import com.formafx.storyfx.agent.EncryptedStore

/** No activity is forced open, no Accessibility permission is granted programmatically. */
class AgentBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action !in setOf(Intent.ACTION_LOCKED_BOOT_COMPLETED, Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_USER_UNLOCKED)) return
        if (!BootUnlockStore(context).userUnlocked()) return
        if (runCatching { EncryptedStore(context).session() != null }.getOrDefault(false)) AgentSchedule.enable(context)
        // The Android system, rather than this receiver, binds the enabled Accessibility service.
    }
}
