package com.formafx.storyfx.agent.update

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.widget.LinearLayout
import androidx.core.content.FileProvider
import com.formafx.storyfx.agent.AgentUi
import com.formafx.storyfx.agent.BuildConfig
import java.io.File
import java.util.concurrent.Executors

class UpdateCard(private val activity: Activity, ui: AgentUi) {
    private val executor = Executors.newSingleThreadExecutor()
    private val folder = File(activity.cacheDir, "verified_updates")
    private val state = activity.getSharedPreferences("verified_update", Context.MODE_PRIVATE)
    private val message = ui.text("Version installée : ${BuildConfig.VERSION_NAME}", 13f)
    private val button = ui.button("Rechercher une mise à jour", primary = true)
    private var release: UpdateRelease? = null
    private var pending = false
    private var busy = false
    val view: LinearLayout = ui.card().apply {
        addView(ui.text("Mises à jour StoryFX", 18f, ui.ink, true))
        addView(message)
        addView(button)
        addView(ui.label("Téléchargement officiel, contrôle SHA-256, version et signature. " +
            "Android vous demande de confirmer l’installation. Vos réglages sont conservés."))
    }
    init {
        restore()
        button.setOnClickListener { if (release == null) check() else download() }
    }
    private fun restore() {
        try {
            val saved = state.getString("release", null) ?: return
            val candidate = UpdateRelease.parse(saved)
            require(candidate.code > BuildConfig.VERSION_CODE)
            UpdateVerifier(activity).verify(File(folder, "candidate.apk"), candidate)
            release = candidate
            pending = state.getBoolean("permission_pending", false)
            message.text = "Version ${candidate.version} vérifiée, installation à confirmer."
            button.text = "Télécharger et installer"
        } catch (_: Exception) { state.edit().clear().apply() }
    }
    private fun check() = background {
        val latest = UpdateDownload.latest()
        activity.runOnUiThread {
            if (latest.code <= BuildConfig.VERSION_CODE) message.text = "StoryFX est à jour."
            else {
                release = latest
                message.text = "Version ${latest.version} disponible"
                button.text = "Télécharger et installer"
            }
        }
    }
    private fun download() = background {
        val selected = requireNotNull(release)
        val file = UpdateDownload.download(folder, selected) { progress ->
            activity.runOnUiThread { message.text = "Téléchargement : $progress %" }
        }
        UpdateVerifier(activity).verify(file, selected)
        check(state.edit().putString("release", selected.serialize()).commit())
        activity.runOnUiThread { if (!activity.isDestroyed) launchInstaller() }
    }
    private fun launchInstaller() {
        if (!activity.packageManager.canRequestPackageInstalls()) {
            pending = true
            state.edit().putBoolean("permission_pending", true).apply()
            message.text = "Autorisez StoryFX à installer cette mise à jour, puis revenez ici."
            activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${activity.packageName}")))
            return
        }
        pending = false
        state.edit().putBoolean("permission_pending", false).apply()
        val file = File(folder, "candidate.apk")
        try {
            UpdateVerifier(activity).verify(file, requireNotNull(release))
            val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.updates", file)
            activity.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri,
                "application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION))
            message.text = "Confirmez la mise à jour dans l’installateur Android."
        } catch (_: Exception) { message.text = "Mise à jour refusée. Recherchez la version officielle." }
    }
    fun onResume() { if (pending && activity.packageManager.canRequestPackageInstalls()) launchInstaller() }
    private fun background(work: () -> Unit) {
        if (busy) return
        busy = true; button.isEnabled = false; message.text = "Vérification…"
        executor.execute {
            try { work() } catch (_: Exception) {
                activity.runOnUiThread { message.text = "Mise à jour indisponible ou invalide. Réessayez." }
            } finally {
                activity.runOnUiThread { if (!activity.isDestroyed) { busy = false; button.isEnabled = true } }
            }
        }
    }
    fun close() { executor.shutdown() }
}
