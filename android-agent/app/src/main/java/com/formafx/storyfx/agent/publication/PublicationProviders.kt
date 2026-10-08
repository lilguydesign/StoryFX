package com.formafx.storyfx.agent.publication

import org.json.JSONObject

/** Provider availability is local code, never a package or executable received from the server. */
enum class PublicationProvider(val platform: String, val adapterValidated: Boolean) {
    WHATSAPP_BUSINESS("WhatsApp", true), FACEBOOK("Facebook", false);

    companion object {
        fun fromPlatform(value: String): PublicationProvider =
            requireNotNull(entries.singleOrNull { it.platform == value }) { "PROVIDER_NOT_SUPPORTED" }
    }
}

object PublicationProviders {
    fun validate(job: JSONObject, profiles: PublicationProfiles, localPrimary: String): JSONObject {
        val payload = job.getJSONObject("payload")
        val provider = PublicationProvider.fromPlatform(payload.getString("platform"))
        val profile = profiles.authorized.singleOrNull {
            it.profile == payload.getString("device") && it.provider == provider
        }
        requireNotNull(profile) { "PROFILE_NOT_AUTHORIZED" }
        // Facebook has no native implementation or physical destination/proof validation yet.
        // A server flag, explicit association or forged readiness can never activate it here.
        require(provider.adapterValidated) { "ADAPTER_NOT_VALIDATED" }
        require(profile.primary && profile.profile == profiles.requirePrimary(localPrimary).profile)
        return PublicationPolicy.validate(job, localPrimary)
    }

    fun description(profile: AuthorizedPublicationProfile): String = when {
        !profile.provider.adapterValidated -> "Facebook · adaptateur natif indisponible"
        !profile.enabled -> "WhatsApp · désactivé"
        !profile.ready || profile.reason.isNotEmpty() -> "WhatsApp · en attente"
        else -> "WhatsApp · prêt pour les tâches compatibles"
    }
}
