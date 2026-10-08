package com.formafx.storyfx.agent.publication

import android.content.Context
import android.os.UserManager
import android.provider.Settings
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.formafx.storyfx.agent.EncryptedStore
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Opt-in encrypted PIN only. Sessions, accounts, albums and journals stay in CE storage. */
class BootUnlockStore(private val context: Context) : UnlockState {
    private val prefs = context.createDeviceProtectedStorageContext()
        .getSharedPreferences("storyfx_boot_unlock", Context.MODE_PRIVATE)
    private val alias = "storyfx_boot_pin_v1"
    val bootCount get() = Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT, -1)
    fun userUnlocked() = context.getSystemService(UserManager::class.java).isUserUnlocked
    override fun firstUnlockPending() = !userUnlocked()
    fun enabled() = prefs.getBoolean("consent", false)
    fun enable() {
        check(userUnlocked())
        val ordinary = EncryptedStore(context)
        check(ordinary.session() != null && ordinary.publicationProfile().isNotBlank() && ordinary.publicationEnabled())
        val pin = requireNotNull(ordinary.unlockPin())
        try {
            val payload = JSONObject().put("pin", String(pin)).put("installation", ordinary.installationId())
                .put("profile", ordinary.publicationProfile()).put("consent_version", 1)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
            val value = encode(cipher.iv) + ":" + encode(cipher.doFinal(payload.toString().toByteArray(Charsets.UTF_8)))
            check(prefs.edit().putString("credential", value).putBoolean("consent", true).commit())
        } finally { pin.fill('\u0000') }
    }
    fun disable() {
        check(prefs.edit().remove("credential").putBoolean("consent", false).commit())
    }
    fun setPublicationEnabled(value: Boolean) = synchronized(publicationLock) {
        check(prefs.edit().putBoolean("publication_allowed", value).commit())
    }
    fun restorePublicationPermissionAfterUnlock() = synchronized(publicationLock) {
        // The lock also serializes explicit stops: migration cannot overwrite a newly saved false.
        PublicationActivation.restoreBootPermission(userUnlocked(),
            publicationPermission(),
            { EncryptedStore(context).publicationEnabled() }, ::setPublicationEnabled)
    }
    fun publicationPermission(): Boolean? =
        if (prefs.contains("publication_allowed")) prefs.getBoolean("publication_allowed", false) else null
    private fun publicationAllowed() = prefs.getBoolean("publication_allowed", false)
    fun shouldInvoke() = BootUnlockPolicy.eligible(enabled(), prefs.contains("credential"),
        userUnlocked(), bootCount, prefs.getInt("invoked_boot", -1), publicationAllowed())
    fun reserveInvocation() {
        check(shouldInvoke()); check(prefs.edit().putInt("invoked_boot", bootCount).commit())
    }
    override fun unlockAllowed() = enabled() && publicationAllowed() && !userUnlocked() && bootCount >= 0
    override fun unlockAttempted() = bootCount < 0 || prefs.getInt("attempted_boot", -1) == bootCount
    override fun markUnlockAttempt() {
        check(unlockAllowed() && !unlockAttempted())
        check(prefs.edit().putInt("attempted_boot", bootCount).commit())
    }
    override fun unlockSucceeded() { /* Retain the consumed attempt until a different real boot. */ }
    override fun unlockPin(): CharArray? {
        if (!enabled()) return null
        val pieces = (prefs.getString("credential", null) ?: return null).split(":", limit = 2)
        check(pieces.size == 2)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, decode(pieces[0])))
        }
        val clear = cipher.doFinal(decode(pieces[1]))
        try {
            val data = JSONObject(clear.toString(Charsets.UTF_8))
            check(data.getInt("consent_version") == 1 && data.getString("profile").isNotBlank())
            check(data.getString("installation").isNotBlank())
            return data.getString("pin").takeIf { it.matches(Regex("[0-9]{4,16}")) }?.toCharArray()
        } finally { clear.fill(0) }
    }
    override fun saveUnlockResult(value: KeyguardResult) {
        check(prefs.edit().putString("result", value.name).commit())
    }
    override fun saveUnlockFailure(stage: String, kind: String) {
        check(prefs.edit().putString("failure_stage", stage).putString("failure_kind", kind).commit())
    }
    fun diagnostics() = JSONObject().put("enabled", enabled()).put("user_unlocked", userUnlocked())
        .put("credential_present", prefs.contains("credential")).put("boot_count", bootCount)
        .put("invoked_this_boot", prefs.getInt("invoked_boot", -1) == bootCount)
        .put("pin_attempted_this_boot", unlockAttempted())
        .put("result", KeyguardResult.read(prefs.getString("result", null)).label)
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        check(userUnlocked()) // Provision only after authenticated association and visible opt-in.
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    private fun encode(value: ByteArray) = Base64.encodeToString(value, Base64.NO_WRAP)
    private fun decode(value: String) = Base64.decode(value, Base64.NO_WRAP)
    private companion object { val publicationLock = Any() }
}
