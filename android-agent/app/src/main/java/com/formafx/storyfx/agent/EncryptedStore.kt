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

class EncryptedStore(context: Context) : QueueStore, AgentAuthStateStore,
    com.formafx.storyfx.agent.publication.PublicationStateStore {
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

    fun phoneName(): String = readSecret("phone_name") ?: AgentController.phoneName()

    fun savePhoneName(value: String) {
        require(value.trim().isNotEmpty())
        check(prefs.edit().putString("phone_name", encrypt(value.trim().take(80))).commit())
    }

    fun savedServer(): String = prefs.getString("server", "") ?: ""

    fun eraseAssociation() {
        check(!org.json.JSONObject(publicationState()).has("pending"))
        check(prefs.edit().remove("server").remove("device_id").remove("token")
            .remove("outbox").remove("last_status").remove("account").remove("auth_pending")
            .remove("publication_profile").remove("unlock_credential").remove("unlock_attempted")
            .remove("unlock_test_until").putBoolean("publication_enabled", false).commit())
        LocalUnlockTest.clear()
    }

    fun status(): String = prefs.getString("last_status", "Association requise")!!

    fun saveStatus(message: String) {
        check(prefs.edit().putString("last_status", message).commit())
    }

    override fun publicationState(): String = readSecret("publications") ?: "{}"
    override fun savePublicationState(value: String) {
        check(prefs.edit().putString("publications", encrypt(value)).commit())
    }
    fun publicationProfile(): String = readSecret("publication_profile") ?: ""
    fun publicationEnabled(): Boolean = prefs.getBoolean("publication_enabled", false)
    fun savePublicationBinding(profile: String, enabled: Boolean) {
        check(prefs.edit().putString("publication_profile", encrypt(profile))
            .putBoolean("publication_enabled", enabled).commit())
    }

    fun saveUnlockPin(pin: String) {
        require(session() != null && publicationEnabled() && publicationProfile().isNotBlank())
        require(pin.matches(Regex("[0-9]{4,16}")))
        val value = org.json.JSONObject().put("profile", publicationProfile())
            .put("installation", installationId()).put("pin", pin)
        check(prefs.edit().putString("unlock_credential", encrypt(value.toString()))
            .remove("unlock_attempted").commit())
    }
    fun unlockPin(): CharArray? = readSecret("unlock_credential")?.let {
        val value = org.json.JSONObject(it)
        if (value.getString("profile") != publicationProfile() || value.getString("installation") != installationId()) null
        else value.getString("pin").takeIf { pin -> pin.matches(Regex("[0-9]{4,16}")) }?.toCharArray()
    }
    fun disableUnlock() { check(prefs.edit().remove("unlock_credential").commit()); LocalUnlockTest.clear() }
    fun unlockAttempted() = prefs.getBoolean("unlock_attempted", false)
    fun markUnlockAttempt() { check(prefs.edit().putBoolean("unlock_attempted", true).commit()) }
    fun unlockSucceeded() { check(prefs.edit().remove("unlock_attempted").commit()); LocalUnlockTest.clear() }
    fun requestUnlockTest() {
        require(unlockPin()?.also { it.fill('\u0000') } != null && !unlockAttempted())
        LocalUnlockTest.request(publicationProfile(), installationId())
    }
    fun unlockTestPending() = LocalUnlockTest.pending(publicationProfile(), installationId())
    fun consumeUnlockTest() { LocalUnlockTest.clear() }

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
