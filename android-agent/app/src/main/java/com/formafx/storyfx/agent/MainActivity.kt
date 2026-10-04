package com.formafx.storyfx.agent

import android.app.Activity
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var ui: AgentUi
    private lateinit var server: EditText
    private lateinit var code: EditText
    private lateinit var phone: EditText
    private lateinit var enroll: Button
    private lateinit var sync: Button
    private lateinit var erase: Button
    private lateinit var status: TextView
    private var busy = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ui = AgentUi(this)
        val root = ui.column().apply {
            setPadding(ui.dp(20), ui.dp(22), ui.dp(20), ui.dp(24))
        }
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            background = GradientDrawable(GradientDrawable.Orientation.TL_BR,
                intArrayOf(Color.rgb(8, 18, 30), Color.rgb(14, 33, 49)))
            addView(root)
            setOnApplyWindowInsetsListener { view, insets ->
                view.setPadding(0, insets.systemWindowInsetTop, 0, insets.systemWindowInsetBottom)
                insets
            }
        }
        setContentView(scroll)
        val heading = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        heading.addView(ImageView(this).apply { setImageResource(R.drawable.ic_storyfx) },
            LinearLayout.LayoutParams(ui.dp(50), ui.dp(50)))
        heading.addView(ui.column().apply {
            setPadding(ui.dp(12), 0, 0, 0)
            addView(ui.text("STORYFX", 26f, ui.ink, true))
            addView(ui.text("Votre téléphone, connecté au serveur", 12f))
        }, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(heading)
        root.addView(ui.text("AGENT 0.1.0  •  DIAGNOSTIC", 11f, ui.accent, true).apply {
            setPadding(0, ui.dp(16), 0, 0)
        })
        root.addView(ui.card().apply {
            addView(ui.text("Associer ce téléphone", 18f, ui.ink, true))
            addView(ui.label("Serveur HTTPS"))
            server = ui.field("https://votre-serveur", InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_VARIATION_URI).apply {
                setText(EncryptedStore(this@MainActivity).savedServer())
            }
            addView(server)
            addView(ui.label("Code d’association à usage unique"))
            code = ui.field("Code du tableau de bord", InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS)
            addView(code)
            addView(ui.label("Nom du téléphone"))
            phone = ui.field("Nom du téléphone", InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS).apply { setText(AgentController.phoneName()) }
            addView(phone)
            enroll = ui.button("Enrôler", primary = true).apply {
                setOnClickListener {
                    val address = server.text.toString()
                    val pairCode = code.text.toString()
                    val name = phone.text.toString()
                    perform {
                        AgentController.enroll(applicationContext, address, pairCode, name)
                    }
                }
            }
            addView(enroll)
        })
        root.addView(ui.card().apply {
            addView(ui.text("Connexion et diagnostics", 18f, ui.ink, true))
            status = ui.text("Association requise", 14f, ui.ink).apply {
                setPadding(0, ui.dp(12), 0, ui.dp(4))
            }
            addView(status)
            sync = ui.button("Synchroniser maintenant", primary = true).apply {
                setOnClickListener { perform { AgentController.synchronize(applicationContext) } }
            }
            addView(sync)
            addView(ui.label("Synchronisation Android toutes les 15 min environ. La veille, la batterie " +
                "et le réseau peuvent reporter son exécution."))
            erase = ui.button("Supprimer l’association", danger = true).apply {
                setOnClickListener {
                    perform {
                        AgentController.erase(applicationContext)
                        "Association locale supprimée"
                    }
                }
            }
            addView(erase)
            addView(ui.label("Pour révoquer l’accès côté serveur, utilisez le tableau de bord."))
        })
        root.addView(ui.text("Cette première étape vérifie la connexion et la reprise après une coupure. " +
            "Elle ne publie aucun statut et ne lit ni votre écran ni vos albums.", 12f).apply {
            setPadding(ui.dp(2), ui.dp(18), ui.dp(2), 0)
        })
        refresh()
    }

    override fun onResume() { super.onResume(); if (::status.isInitialized) refresh() }

    private fun perform(action: () -> String) {
        if (busy) return
        busy = true; refresh(); status.text = "Connexion au serveur…"
        executor.execute {
            val result = try { action() } catch (failure: Exception) {
                AgentController.recordFailure(applicationContext, failure)
            }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                busy = false
                code.text.clear()
                refresh()
                status.text = result
            }
        }
    }

    private fun refresh() {
        val store = EncryptedStore(this)
        val connected = runCatching { store.session() != null }.getOrDefault(false)
        enroll.isEnabled = !busy && !connected
        sync.isEnabled = !busy && connected
        erase.isEnabled = !busy && (connected || store.savedServer().isNotEmpty())
        server.isEnabled = !busy && !connected
        code.isEnabled = !busy && !connected
        phone.isEnabled = !busy && !connected
        listOf(enroll, sync, erase).forEach { it.alpha = if (it.isEnabled) 1f else 0.45f }
        if (!busy) status.text = store.status()
    }

    override fun onDestroy() { executor.shutdown(); super.onDestroy() }
}
