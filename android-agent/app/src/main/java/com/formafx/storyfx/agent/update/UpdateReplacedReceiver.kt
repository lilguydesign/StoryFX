package com.formafx.storyfx.agent.update

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.formafx.storyfx.agent.AgentSchedule
import com.formafx.storyfx.agent.EncryptedStore

class UpdateReplacedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        // Resume the visible agent's existing synchronization, never social publication.
        if (runCatching { EncryptedStore(context).session() != null }.getOrDefault(false))
            AgentSchedule.enable(context)
    }
}
