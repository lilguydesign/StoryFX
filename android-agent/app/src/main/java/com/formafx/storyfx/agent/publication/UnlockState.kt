package com.formafx.storyfx.agent.publication

/** Both stores reserve a single ordinary PIN entry before any keypad action. */
interface UnlockState {
    fun unlockAllowed(): Boolean
    fun unlockPin(): CharArray?
    fun unlockAttempted(): Boolean
    fun markUnlockAttempt()
    fun unlockSucceeded()
    fun saveUnlockResult(value: KeyguardResult)
    fun saveUnlockFailure(stage: String, kind: String)
}
