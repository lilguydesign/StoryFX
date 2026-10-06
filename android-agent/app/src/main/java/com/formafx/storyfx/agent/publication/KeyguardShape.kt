package com.formafx.storyfx.agent.publication

object KeyguardShape {
    const val system = "com.android.systemui"
    fun accepts(packageName: String, emptyPasswordEntry: Boolean, ids: Set<String>): Boolean =
        packageName == system && emptyPasswordEntry && (0..9).all { "$system:id/key$it" in ids }
}
