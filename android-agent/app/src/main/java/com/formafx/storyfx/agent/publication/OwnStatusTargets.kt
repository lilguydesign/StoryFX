package com.formafx.storyfx.agent.publication

/** Prefer a tile's exact text only when its avatar belongs to the same bounded control.
 * Unrelated avatars and multiple text-labelled targets remain ambiguous. */
object OwnStatusTargets {
    fun <T> resolve(nodes: List<T>, text: (T) -> String, description: (T) -> String,
                    sameControl: (T, T) -> Boolean): List<T> {
        val labels = nodes.filter { PublicationScreenLabels.own(text(it), "") }
        val avatars = nodes.filter { it !in labels && PublicationScreenLabels.own("", description(it)) }
        return labels + avatars.filter { avatar -> labels.none { sameControl(it, avatar) } }
    }
}
