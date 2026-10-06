package com.formafx.storyfx.agent.publication

import android.app.Activity
import android.app.KeyguardManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Build
import android.view.WindowManager

/** Ask Android to display its normal lock challenge. No credentials enter this activity. */
class UnlockActivity : Activity() {
    private var requested = false
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true); setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or WindowManager.LayoutParams.FLAG_SECURE)
        Handler(Looper.getMainLooper()).postDelayed({ if (!isFinishing) finish() }, 30000)
    }
    override fun onPostResume() {
        super.onPostResume()
        if (requested) return
        requested = true
        window.decorView.postDelayed({ getSystemService(KeyguardManager::class.java).requestDismissKeyguard(this,
            object : KeyguardManager.KeyguardDismissCallback() {
                override fun onDismissSucceeded() { finish() }
                override fun onDismissCancelled() { finish() }
                override fun onDismissError() { finish() }
            }) }, 300)
    }
}
