package com.formafx.storyfx.agent.publication

import android.app.Activity
import android.text.InputType
import android.text.InputFilter
import android.view.View
import android.view.WindowManager
import com.formafx.storyfx.agent.AgentUi
import com.formafx.storyfx.agent.EncryptedStore

class UnlockCard(private val activity: Activity, ui: AgentUi) {
    private val store get() = EncryptedStore(activity)
    private val status = ui.text("Code local non affiché", 13f)
    private val pin = ui.field("Code PIN Android", InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD).apply {
        isSaveEnabled = false
        importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
        filters = arrayOf(InputFilter.LengthFilter(16))
        setOnFocusChangeListener { _, focused ->
            if (focused) activity.window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
            else activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }
    val view = ui.card().apply {
        addView(ui.text("Déverrouillage local", 17f, ui.ink, true))
        addView(ui.label("Facultatif : StoryFX peut saisir votre PIN sur le clavier Android reconnu pour une tâche autorisée. " +
            "Le code reste chiffré sur ce téléphone, lié à son profil. Une seule tentative ; un échec attend votre déverrouillage manuel. " +
            "Le code n’est jamais envoyé au serveur. Après redémarrage, un premier déverrouillage manuel reste requis."))
        addView(ui.label("Code PIN de ce téléphone")); addView(pin)
        addView(ui.button("Enregistrer le code sur ce téléphone", primary = true).apply {
            setOnClickListener {
                val saved = runCatching { store.saveUnlockPin(pin.text.toString()) }.isSuccess
                pin.text.clear(); pin.clearFocus()
                status.text = if (saved) "Code protégé enregistré. Le verrouillage Android reste actif." else "Code ou association invalide. Aucune modification."
            }
        })
        addView(ui.button("Tester le déverrouillage local").apply {
            setOnClickListener {
                val accepted = runCatching { store.requestUnlockTest() }.isSuccess
                status.text = if (accepted) "Test demandé pour une minute : verrouillez maintenant votre écran. Aucun statut ne sera publié par ce test."
                    else "Enregistrez le code, ou déverrouillez manuellement après l’échec précédent."
            }
        })
        addView(ui.button("Supprimer le code local", danger = true).apply {
            setOnClickListener { store.disableUnlock(); status.text = "Code local supprimé." }
        })
        addView(status)
    }
}
