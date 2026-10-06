package com.formafx.storyfx.agent.publication

/** A process/service restart never rearms a PIN attempt in the same Android boot. */
object BootUnlockPolicy {
    fun eligible(consented: Boolean, hasCredential: Boolean, userUnlocked: Boolean,
                 bootCount: Int, invokedBoot: Int): Boolean =
        consented && hasCredential && !userUnlocked && bootCount >= 0 && invokedBoot != bootCount
}
