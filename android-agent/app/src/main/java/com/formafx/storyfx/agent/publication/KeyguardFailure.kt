package com.formafx.storyfx.agent.publication

/** Export only a fixed exception category, never its message, stack or credentials. */
object KeyguardFailure {
    fun kind(error: Exception): String {
        val failure = if (error is java.util.concurrent.ExecutionException) error.cause ?: error else error
        return when (failure) {
            is java.util.concurrent.TimeoutException -> "UI_TIMEOUT"
            is SecurityException -> "SECURITY"
            is IllegalStateException -> "STATE_GUARD"
            is NoSuchElementException -> "KEY_NOT_UNIQUE"
            is InterruptedException -> "INTERRUPTED"
            else -> "PLATFORM_ERROR"
        }
    }
}
