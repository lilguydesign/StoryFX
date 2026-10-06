package com.formafx.storyfx.agent.publication

/** A gesture completion race never proves success while either Android lock remains. */
object KeyguardOutcome {
    fun confirmed(pinAttemptReserved: Boolean, deviceLocked: Boolean, keyguardLocked: Boolean, interactive: Boolean) =
        pinAttemptReserved && !deviceLocked && !keyguardLocked && interactive
}
