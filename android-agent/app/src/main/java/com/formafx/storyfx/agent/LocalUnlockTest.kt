package com.formafx.storyfx.agent

/** Visible, owner-requested diagnostic consent dies with the process or after one minute. */
internal object LocalUnlockTest {
    private var profile = ""
    private var installation = ""
    private var deadline = 0L
    @Synchronized fun request(profile: String, installation: String) {
        this.profile = profile; this.installation = installation
        deadline = android.os.SystemClock.elapsedRealtime() + 60000
    }
    @Synchronized fun pending(profile: String, installation: String): Boolean =
        deadline > android.os.SystemClock.elapsedRealtime() && this.profile == profile && this.installation == installation
    @Synchronized fun clear() { deadline = 0L; profile = ""; installation = "" }
}
