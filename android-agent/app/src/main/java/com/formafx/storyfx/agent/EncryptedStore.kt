package com.formafx.storyfx.agent

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class EncryptedStore(context: Context) : QueueStore, AgentAuthStateStore {
    private val prefs = context.getSharedPreferences("storyfx_private", Context.MODE_PRIVATE)
    private val alias = "storyfx_agent_local_v1"

    fun installationId(): String {
        val saved = prefs.getString("installation_id", null)
        if (saved != null) return saved
        val id = UUID.randomUUID().toString()
        check(prefs.edit().putString("installation_id", id).commit())
        return id
    }

    fun session(): Session? {
        val token = readSecret("token") ?: return null
        val deviceId = prefs.getString("device_id", null) ?: return null
        val server = prefs.getString("server", null) ?: return null
        return Session(server, deviceId, token)
    }

    fun saveSession(server: String, deviceId: String, token: String) {
        val encrypted = encrypt(token)
        check(prefs.edit().putString("server", server).putString("device_id", deviceId)
            .putString("token", encrypted).remove("account").remove("auth_pending").commit())
    }

    override fun pendingAuth(): PendingAgentAuth? = readSecret("auth_pending")?.let {
        PendingAgentAuth.fromJson(it)
    }

    override fun savePendingAuth(value: PendingAgentAuth) {
        check(prefs.edit().putString("auth_pending", encrypt(value.toJson())).commit())
    }

    override fun associationPresent(): Boolean = session() != null

    override fun pendingEventsPresent(): Boolean = org.json.JSONArray(read()).length() > 0

    override fun saveAuthenticatedSession(value: AuthenticatedAgentSession) {
        val account = org.json.JSONObject().put("id", value.userId).put("email", value.email)
        check(prefs.edit().putString("server", value.server).putString("device_id", value.deviceId)
            .putString("token", encrypt(value.token)).putString("account", encrypt(account.toString()))
            .remove("auth_pending").commit())
    }

    fun accountEmail(): String = readSecret("account")?.let {
        org.json.JSONObject(it).getString("email")
    } ?: ""

    fun savedServer(): String = prefs.getString("server", "") ?: ""

    fun eraseAssociation() {
        check(prefs.edit().remove("server").remove("device_id").remove("token")
            .remove("outbox").remove("last_status").remove("account").remove("auth_pending").commit())
    }

    fun status(): String = prefs.getString("last_status", "Association requise")!!

    fun saveStatus(message: String) {
        check(prefs.edit().putString("last_status", message).commit())
    }

    override fun read(): String = readSecret("outbox") ?: "[]"

    override fun write(value: String) {
        check(prefs.edit().putString("outbox", encrypt(value)).commit())
    }

    private fun readSecret(name: String): String? {
        val encoded = prefs.getString(name, null) ?: return null
        val pieces = encoded.split(":", limit = 2)
        check(pieces.size == 2)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, decode(pieces[0])))
        return cipher.doFinal(decode(pieces[1])).toString(Charsets.UTF_8)
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        return encode(cipher.iv) + ":" + encode(cipher.doFinal(value.toByteArray(Charsets.UTF_8)))
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val existing = store.getKey(alias, null) as? SecretKey
        if (existing != null) return existing
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }

    private fun encode(bytes: ByteArray): String = Base64.encodeToString(bytes, Base64.NO_WRAP)
    private fun decode(value: String): ByteArray = Base64.decode(value, Base64.NO_WRAP)
}

class Session(val server: String, val deviceId: String, val token: String)
