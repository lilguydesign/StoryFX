package com.formafx.storyfx.agent

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors

/** Debug-only account validation bridge. It never launches an external browser. */
class QaAuthActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = applicationContext
        val resultFile = File(app.filesDir, "qa_auth_connection.json")
        resultFile.writeText(JSONObject().put("status", "starting").toString())
        val executor = Executors.newSingleThreadExecutor()
        executor.execute {
            try {
                val url = AgentController.startLogin(
                    app, AgentAuthRoutes.publicServer, "Validation technique")
                val requestId = Uri.parse(url).getQueryParameter("request_id")
                    ?: throw AgentAuthException("invalid_connection")
                resultFile.writeText(JSONObject().put("status", "ready")
                    .put("connect_url", url).put("request_id", requestId).toString())
            } catch (failure: Exception) {
                AgentController.recordFailure(app, failure)
                resultFile.writeText(JSONObject().put("status", "failed").toString())
            }
        }
        executor.shutdown()
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }
}
