package com.formafx.storyfx.agent

/** Explicit private-pilot targets. Never fall back to the implicit default browser. */
object LoginBrowserTargets {
    val packages = listOf("com.sec.android.app.sbrowser", "com.microsoft.emmx", "org.mozilla.firefox")
    fun select(available: Collection<String>): String? = packages.firstOrNull { it in available }
}
