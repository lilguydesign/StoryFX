package com.formafx.storyfx.agent.publication

import android.app.Activity
import com.formafx.storyfx.agent.AgentUi

class BootUnlockCard(activity: Activity, ui: AgentUi) {
    private val store = BootUnlockStore(activity)
    private val status = ui.text("Au démarrage : ${if (store.enabled()) "autorisé" else "désactivé"}", 13f)
    val view = ui.card().apply {
        addView(ui.text("Reprise après redémarrage", 17f, ui.ink, true))
        addView(ui.label("Autorisation facultative : le PIN local chiffré devient disponible avant le premier " +
            "déverrouillage. StoryFX saisit ce PIN dans le clavier Android reconnu, une seule fois par démarrage. " +
            "Cela permet au téléphone de se déverrouiller sans votre présence. Le verrouillage et Play Protect restent actifs. " +
            "Le démarrage utilise la copie locale, indépendamment de la sauvegarde Vault facultative. Une erreur attend un déverrouillage manuel."))
        addView(ui.label("L’Accessibilité StoryFX doit déjà être autorisée. Après le déverrouillage, les envois restent " +
            "soumis au compte, aux canaux, au scheduler et aux autorisations du serveur. Cette option n’active aucun canal."))
        addView(ui.button("Autoriser la reprise au démarrage", primary = true).apply {
            setOnClickListener {
                status.text = if (runCatching { store.enable() }.isSuccess) "Reprise autorisée. Vérifiez le résultat après un redémarrage."
                    else "Enregistrez d’abord le PIN local sur un téléphone associé. Aucune modification."
            }
        })
        addView(ui.button("Désactiver la reprise au démarrage", danger = true).apply {
            setOnClickListener { store.disable(); status.text = "Reprise au démarrage désactivée." }
        })
        addView(ui.button("Voir le résultat au démarrage").apply {
            setOnClickListener { status.text = "Dernier démarrage : ${store.diagnostics().getString("result")}." }
        })
        addView(status)
    }
}
