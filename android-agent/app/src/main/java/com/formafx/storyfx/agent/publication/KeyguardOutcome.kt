package com.formafx.storyfx.agent.publication

/** A gesture completion race never proves success while either Android lock remains. */
object KeyguardOutcome {
    fun awake(deviceLocked: Boolean, keyguardLocked: Boolean, interactive: Boolean, userUnlocked: Boolean) =
        !deviceLocked && !keyguardLocked && interactive && userUnlocked
    fun confirmed(pinAttemptReserved: Boolean, deviceLocked: Boolean, keyguardLocked: Boolean,
                  interactive: Boolean, userUnlocked: Boolean = true) =
        pinAttemptReserved && awake(deviceLocked, keyguardLocked, interactive, userUnlocked)
}
