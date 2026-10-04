package com.formafx.storyfx.agent

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequest
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

object AgentSchedule {
    private const val name = "storyfx_diagnostic_sync"

    fun enable(context: Context) {
        val request = PeriodicWorkRequest.Builder(DiagnosticWorker::class.java, 15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            name, ExistingPeriodicWorkPolicy.UPDATE, request
        )
    }

    fun disable(context: Context) { WorkManager.getInstance(context).cancelUniqueWork(name) }
}

class DiagnosticWorker(context: Context, parameters: WorkerParameters) : Worker(context, parameters) {
    override fun doWork(): Result {
        return try {
            if (EncryptedStore(applicationContext).session() == null) return Result.success()
            AgentController.synchronize(applicationContext)
            Result.success()
        } catch (failure: Exception) {
            AgentController.recordFailure(applicationContext, failure)
            if (failure is AgentRequestException && failure.status in listOf(401, 403)) {
                Result.failure()
            } else Result.retry()
        }
    }
}
