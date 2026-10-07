package com.formafx.storyfx.agent.publication

import android.app.Activity
import android.widget.CheckBox
import com.formafx.storyfx.agent.AgentApi
import com.formafx.storyfx.agent.AgentUi
import com.formafx.storyfx.agent.EncryptedStore
import org.json.JSONObject
import java.util.concurrent.Executors

/** Explicit recovery only. No PIN appears in the view, status, diagnostic or outbox. */
class PinBackupCard(private val activity: Activity, ui: AgentUi) {
    private val executor = Executors.newSingleThreadExecutor()
    private val status = ui.text("Sauvegarde non vérifiée.", 13f)
    private val consent = CheckBox(activity).apply {
        text = "Autoriser la sauvegarde chiffrée dans Supabase Vault"
        setTextColor(ui.ink)
    }
    val view = ui.card().apply {
        addView(ui.text("Sauvegarde sécurisée du PIN", 17f, ui.ink, true))
        addView(ui.label("Facultatif : le code est transmis par HTTPS au coffre chiffré de votre compte FormaFX. " +
            "Seul le compte propriétaire actif et ce profil associé peuvent le restaurer. " +
            "Le premier déverrouillage au démarrage utilise toujours le code local ; Internet ne le remplace pas."))
        addView(consent)
        for ((label, operation) in listOf("Sauvegarder le code local" to "save",
            "Vérifier la sauvegarde" to "status", "Restaurer le code local" to "restore",
            "Supprimer la sauvegarde distante" to "remove")) {
            addView(ui.button(label, danger = operation == "remove").apply {
                setOnClickListener {
                    if (!consent.isChecked) {
                        status.text = "Cochez l’autorisation de sauvegarde avant cette opération."
                    } else perform(operation)
                }
            })
        }
        addView(ui.label("Restaurer n’active ni les publications ni le déverrouillage au démarrage. " +
            "Leurs autorisations restent séparées. Si l’association est perdue, reconnectez d’abord votre compte."))
        addView(status)
    }

    private fun perform(operation: String) {
        status.text = "Vérification sécurisée en cours…"
        executor.execute {
            var message = "Sauvegarde indisponible. Le code local et les publications sont conservés."
            runCatching {
                val store = EncryptedStore(activity)
                val session = requireNotNull(store.session())
                val profile = store.publicationProfile()
                require(profile.isNotBlank())
                val body = JSONObject().put("profile", profile).put("consent", true)
                val pin = if (operation == "save") requireNotNull(store.unlockPin()) else null
                val result = try {
                    pin?.let { body.put("pin", String(it)) }
                    AgentApi(session.server, session.token).post("/v1/control/android/pin-backup/$operation", body)
                } finally {
                    body.remove("pin")
                    pin?.fill('\u0000')
                }
                val available = result.getBoolean("available")
                if (operation == "restore" && available) {
                    try { store.saveUnlockPin(result.getString("pin")) }
                    finally { result.remove("pin") }
                }
                message = when {
                    operation == "restore" && available -> "Code local restauré. Réactivez séparément la reprise au démarrage si souhaitée."
                    operation == "save" && available -> "Sauvegarde Vault enregistrée pour ce profil. Aucun code affiché."
                    operation == "remove" -> "Sauvegarde distante supprimée. Le code local reste conservé."
                    available -> "Sauvegarde Vault disponible pour ce profil."
                    else -> "Aucune sauvegarde disponible pour ce profil."
                }
            }
            activity.runOnUiThread { if (!activity.isDestroyed) status.text = message }
        }
    }
}
