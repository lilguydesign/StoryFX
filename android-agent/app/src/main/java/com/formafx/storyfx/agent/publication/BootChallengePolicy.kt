package com.formafx.storyfx.agent.publication

/** Early boot can expose neither lock flag before the real credential challenge exists. */
object BootChallengePolicy {
    fun ready(userUnlocked: Boolean, deviceLocked: Boolean, keyguardLocked: Boolean,
              recognizedEmptyKeypad: Boolean): Boolean =
        !userUnlocked && (deviceLocked || keyguardLocked) && recognizedEmptyKeypad
}
