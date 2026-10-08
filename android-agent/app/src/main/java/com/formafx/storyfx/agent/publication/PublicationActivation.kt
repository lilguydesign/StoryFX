package com.formafx.storyfx.agent.publication

/** A server binding is not consent to resume this phone's global pilot. */
data class PublicationActivation(val globalEnabled: Boolean, val whatsAppEnabled: Boolean) {
    fun withBinding(enabled: Boolean) = copy(whatsAppEnabled = enabled)

    companion object {
        fun restore(explicitGlobal: Boolean?, legacyWhatsApp: Boolean, bootPermission: Boolean? = null) =
            PublicationActivation((explicitGlobal ?: legacyWhatsApp) && bootPermission != false, legacyWhatsApp)

        /** A crash between the two stores preserves the stop; only an explicit start reopens both. */
        fun persistGlobal(enabled: Boolean, ordinary: (Boolean) -> Unit, boot: (Boolean) -> Unit) {
            if (!enabled) boot(false)
            ordinary(enabled)
            if (enabled) boot(true)
        }

        /** Unknown direct-boot permission stays closed until the ordinary store is readable. */
        fun restoreBootPermission(userUnlocked: Boolean, saved: Boolean?, readGlobal: () -> Boolean,
                                  persist: (Boolean) -> Unit): Boolean {
            if (saved != null) return saved
            if (!userUnlocked) return false
            val enabled = readGlobal()
            persist(enabled)
            return enabled
        }
    }
}
