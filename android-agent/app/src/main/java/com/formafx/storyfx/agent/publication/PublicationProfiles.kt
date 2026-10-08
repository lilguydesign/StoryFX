package com.formafx.storyfx.agent.publication

import org.json.JSONObject
import java.util.UUID

data class AuthorizedPublicationProfile(
    val profileId: String?, val profile: String, val provider: PublicationProvider,
    val primary: Boolean, val enabled: Boolean, val ready: Boolean, val reason: String
)

/** An in-memory snapshot from this authenticated device's settings; never a reusable local grant. */
class PublicationProfiles private constructor(
    private val binding: String, private val bindingEnabled: Boolean,
    val authorized: List<AuthorizedPublicationProfile>, val explicitContract: Boolean
) {
    fun requirePrimary(localPrimary: String): AuthorizedPublicationProfile {
        require(localPrimary.isNotBlank() && localPrimary == binding && bindingEnabled) { "PRIMARY_BINDING_CHANGED" }
        val primary = requireNotNull(authorized.singleOrNull { it.primary }) { "PRIMARY_BINDING_REQUIRED" }
        require(primary.profile == localPrimary && primary.provider == PublicationProvider.WHATSAPP_BUSINESS)
        require(primary.enabled && primary.ready && primary.reason.isEmpty()) { "PRIMARY_NOT_READY" }
        return primary
    }

    companion object {
        fun read(settings: JSONObject): PublicationProfiles {
            val binding = settings.optJSONObject("binding")
            val name = binding?.let { text(it, "profile", 80) }.orEmpty()
            val enabledValue = binding?.opt("enabled")
            require(binding == null || enabledValue is Int && enabledValue in 0..1)
            val enabled = enabledValue == 1
            val explicit = settings.has("authorized_profiles")
            val values = if (explicit) {
                val array = settings.getJSONArray("authorized_profiles")
                require(array.length() <= 100)
                (0 until array.length()).map { parse(array.getJSONObject(it)) }
            } else if (binding != null) {
                // A backend rollback authorizes only its original primary, never catalog siblings.
                val reason = text(binding, "reason", 128, allowEmpty = true)
                listOf(AuthorizedPublicationProfile(null, name, PublicationProvider.WHATSAPP_BUSINESS,
                    true, enabled, enabled && reason.isEmpty(), reason))
            } else emptyList()
            require(values.map { it.profile }.distinct().size == values.size) { "AMBIGUOUS_PROFILE" }
            val ids = values.mapNotNull { it.profileId }
            require(ids.distinct().size == ids.size) { "AMBIGUOUS_PROFILE_ID" }
            val primary = values.filter { it.primary }
            require(if (binding == null) values.isEmpty() else primary.size == 1 && primary[0].profile == name)
            require(values.all { it.primary == (it.provider == PublicationProvider.WHATSAPP_BUSINESS) })
            return PublicationProfiles(name, enabled, values.toList(), explicit)
        }

        private fun parse(value: JSONObject): AuthorizedPublicationProfile {
            require(value.has("profile_id"))
            val id = if (value.isNull("profile_id")) null else text(value, "profile_id", 36).also {
                require(UUID.fromString(it).toString() == it)
            }
            val primary = boolean(value, "primary")
            val enabled = boolean(value, "enabled")
            val ready = boolean(value, "ready")
            require(id != null || primary && !enabled && !ready)
            return AuthorizedPublicationProfile(id, text(value, "profile", 80),
                PublicationProvider.fromPlatform(text(value, "platform", 20)), primary, enabled, ready,
                text(value, "reason", 128, allowEmpty = true))
        }

        private fun boolean(value: JSONObject, key: String): Boolean {
            val result = value.get(key)
            require(result is Boolean)
            return result
        }

        private fun text(value: JSONObject, key: String, limit: Int, allowEmpty: Boolean = false): String {
            val result = value.get(key)
            require(result is String && result.length <= limit && (allowEmpty || result.isNotBlank()))
            return result
        }
    }
}
