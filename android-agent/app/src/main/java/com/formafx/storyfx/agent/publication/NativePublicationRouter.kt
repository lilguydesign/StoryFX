package com.formafx.storyfx.agent.publication

import org.json.JSONObject

interface NativePublicationAdapter {
    val provider: PublicationProvider
    fun execute(payload: JSONObject)
}

/** Provider selection is local and closed. An unimplemented provider never constructs a WhatsApp sender. */
object NativePublicationRouter {
    fun execute(provider: PublicationProvider, payload: JSONObject, whatsApp: () -> NativePublicationAdapter) {
        require(provider.adapterValidated) { "ADAPTER_NOT_VALIDATED" }
        require(provider == PublicationProvider.WHATSAPP_BUSINESS) { "PROVIDER_NOT_SUPPORTED" }
        require(payload.getString("platform") == provider.platform) { "PROVIDER_PAYLOAD_MISMATCH" }
        val adapter = whatsApp()
        require(adapter.provider == provider) { "PROVIDER_ADAPTER_MISMATCH" }
        adapter.execute(payload)
    }
}
