package com.formafx.storyfx.agent.publication

/** Persist stable ASCII states; translate at the UI boundary and preserve old stored labels. */
enum class KeyguardResult(val label: String) {
    UNTESTED("NON_TESTÉ"), UNCONFIGURED("NON_CONFIGURÉ"), AUTHORIZATION("AUTORISATION"),
    WAKE_REQUESTED("RÉVEIL_DEMANDÉ"), KEYPAD_UNRECOGNIZED("CLAVIER_NON_RECONNU"),
    ENTERING_PIN("SAISIE_EN_COURS"), LEGACY_CONFIRMED("CONFIRMÉ"), NOT_CONFIRMED("NON_CONFIRMÉ"),
    ERROR("ERREUR"), AUTHORIZATION_REFUSED("AUTORISATION_REFUSÉE"),
    WAKE_CONFIRMED("RÉVEIL_CONFIRMÉ"), PIN_CONFIRMED("PIN_CONFIRMÉ");
    companion object {
        fun read(value: String?): KeyguardResult = entries.firstOrNull { it.name == value || it.label == value } ?: UNTESTED
    }
}
