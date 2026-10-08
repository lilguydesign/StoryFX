package com.formafx.storyfx.agent.publication

import android.app.Activity
import android.content.Intent
import android.provider.Settings
import android.widget.ArrayAdapter
import android.widget.CheckBox
import android.widget.Spinner
import android.widget.TextView
import com.formafx.storyfx.agent.AgentApi
import com.formafx.storyfx.agent.AgentUi
import com.formafx.storyfx.agent.EncryptedStore
import org.json.JSONObject
import java.util.concurrent.Executors

class PublicationCard(private val activity: Activity, ui: AgentUi) {
    private val worker = Executors.newSingleThreadExecutor()
    private val status: TextView = ui.text("Connexion FormaFX requise", 13f)
    private val authorized: TextView = ui.text("Profils autorisés : connexion requise", 13f)
    private val profiles = Spinner(activity)
    private val enabled = CheckBox(activity).apply {
        text = "Activer le pilotage Android de ce téléphone"; setTextColor(ui.ink)
    }
    private val whatsApp = CheckBox(activity).apply {
        text = "Autoriser les tâches WhatsApp du profil principal"; setTextColor(ui.ink)
    }
    private var names = listOf<String>()
    private var bindingGeneration = 0
    val view = ui.card().apply {
        addView(ui.text("Publication Android · pilote WhatsApp", 17f, ui.ink, true))
        addView(ui.label("Sélectionnez le profil principal WhatsApp déjà enregistré pour ce téléphone. Le serveur garde vos horaires et albums."))
        addView(profiles)
        addView(enabled)
        addView(whatsApp)
        addView(ui.label("L’arrêt du pilotage bloque tous les gestes. Désactiver WhatsApp ne change pas cet arrêt global. " +
            "Facebook reste indisponible ; cette option ne l’active pas."))
        addView(ui.button("Enregistrer le profil Android", primary = true).apply { setOnClickListener { bind() } })
        addView(ui.button("Autoriser les photos et vidéos des albums").apply {
            setOnClickListener { activity.requestPermissions(AlbumMedia.permissions(), 410) }
        })
        addView(ui.button("Configurer l’Accessibilité StoryFX").apply {
            setOnClickListener { activity.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })
        addView(ui.label("L’Accessibilité permet à StoryFX de lire les commandes visibles de WhatsApp Business " +
            "et d’agir pour publier uniquement dans Mon statut. Aucune lecture de vos discussions n’est envoyée au serveur. " +
            "Les photos et vidéos sont lues localement dans les albums demandés. Introduction : une vidéo. " +
            "Multi : le nombre prévu. Intro + multi : une vidéo suivie du lot, sans doublon, au maximum 30 médias. " +
            "Activez le service vous-même dans les paramètres Android."))
        addView(ui.label("Après redémarrage, la reprise facultative ci-dessous peut saisir votre PIN local. Sans cette autorisation, " +
            "déverrouillez Android une première fois. Le service reprend ensuite sans ouvrir cette page. Une tâche attend si Internet ou une autorisation manque. " +
            "Les gestes d’une tâche interrompue ne sont jamais rejoués automatiquement."))
        addView(status)
        addView(authorized)
        addView(ui.label("Les profils supplémentaires sont associés explicitement par le propriétaire. " +
            "Facebook reste indisponible dans cet agent. Une association ne valide ni la destination, ni une publication, ni l’autonomie."))
    }
    fun refresh() {
        val store = EncryptedStore(activity)
        val session = runCatching { store.session() }.getOrNull()
        authorized.text = "Profils autorisés : vérification en cours"
        if (session == null) {
            names = emptyList(); profiles.adapter = ArrayAdapter(activity, android.R.layout.simple_spinner_dropdown_item, names)
            enabled.isChecked = false; whatsApp.isChecked = false; status.text = "Connexion FormaFX requise"
            authorized.text = "Profils autorisés : connexion requise"; return
        }
        worker.execute {
            val response = runCatching {
                val data = AgentApi(session.server, session.token).post("/v1/control/android/settings", JSONObject())
                data to PublicationProfiles.read(data)
            }
            activity.runOnUiThread {
                if (activity.isDestroyed) return@runOnUiThread
                val current = runCatching { store.session() }.getOrNull()
                if (current?.server != session.server || current.deviceId != session.deviceId || current.token != session.token)
                    return@runOnUiThread
                response.onSuccess { (data, grants) ->
                    val list = data.getJSONArray("profiles")
                    val secondary = grants.authorized.filter { !it.primary }.map { it.profile }.toSet()
                    names = (0 until list.length()).map { list.getJSONObject(it) }
                        .filter { it.optBoolean("enabled", true) }.map { it.getString("name") }.filterNot { it in secondary }
                    profiles.adapter = ArrayAdapter(activity, android.R.layout.simple_spinner_dropdown_item, names)
                    val binding = data.optJSONObject("binding")
                    val profile = binding?.optString("profile").orEmpty()
                    whatsApp.isChecked = binding?.optInt("enabled", 0) == 1
                    if (profile in names) profiles.setSelection(names.indexOf(profile))
                    if (profile.isNotBlank()) store.savePublicationBinding(profile, whatsApp.isChecked)
                    enabled.isChecked = store.publicationEnabled()
                    authorized.text = if (grants.authorized.isEmpty()) "Aucun profil associé à cet appareil."
                        else grants.authorized.joinToString("\n") { "${it.profile} : ${PublicationProviders.description(it)}" }
                    status.text = "Service : ${if (PublicationService.active) "actif" else "à autoriser"} · Photos : " +
                        "${if (AlbumMedia.allowed(activity)) "autorisées" else "à autoriser"} · " +
                        PublicationLabels.reason(binding?.optString("reason") ?: "WAITING_PERMISSIONS")
                }.onFailure {
                    status.text = "Pilotage Android indisponible. Association et tâches conservées."
                    authorized.text = "Profils autorisés indisponibles ; aucune capacité supplémentaire activée."
                }
            }
        }
    }
    private fun bind() {
        val store = EncryptedStore(activity)
        val session = store.session() ?: return
        val profile = profiles.selectedItem?.toString() ?: return
        if (profile !in names) return
        val requested = enabled.isChecked
        val requestedWhatsApp = whatsApp.isChecked
        val generation = ++bindingGeneration
        if (!requested) store.setPublicationEnabled(false) // Stop locally even if the subsequent server update fails.
        worker.execute {
            val response = runCatching { AgentApi(session.server, session.token).post("/v1/control/android/bind",
                JSONObject().put("profile", profile).put("enabled", requestedWhatsApp)) }
            activity.runOnUiThread {
                val current = runCatching { store.session() }.getOrNull()
                if (generation != bindingGeneration || activity.isDestroyed || current?.server != session.server || current.deviceId != session.deviceId ||
                    current.token != session.token) return@runOnUiThread
                if (response.isSuccess) {
                    store.savePublicationBinding(profile, requestedWhatsApp)
                    store.setPublicationEnabled(requested)
                }
                status.text = if (response.isSuccess) "Profil enregistré." else "Association du profil refusée."; refresh()
            }
        }
    }
    fun close() { worker.shutdown() }
}
