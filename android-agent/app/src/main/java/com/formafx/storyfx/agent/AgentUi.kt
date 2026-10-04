package com.formafx.storyfx.agent

import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.text.InputFilter
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class AgentUi(private val context: Context) {
    val ink = Color.rgb(233, 243, 250)
    val muted = Color.rgb(157, 177, 193)
    val accent = Color.rgb(73, 224, 223)

    fun dp(value: Int): Int = (value * context.resources.displayMetrics.density).toInt()

    fun column(): LinearLayout = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }

    fun text(value: String, size: Float = 14f, color: Int = muted, bold: Boolean = false): TextView =
        TextView(context).apply {
            text = value; textSize = size; setTextColor(color)
            if (bold) setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL))
            setLineSpacing(dp(3).toFloat(), 1f)
        }

    fun card(): LinearLayout = column().apply {
        background = surface(Color.rgb(15, 31, 47), Color.rgb(37, 62, 80), 20)
        setPadding(dp(18), dp(17), dp(18), dp(18))
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(16) }
    }

    fun field(hint: String, input: Int): EditText = EditText(context).apply {
        this.hint = hint; inputType = input; isSingleLine = true
        textSize = 15f; setTextColor(ink); setHintTextColor(muted)
        background = surface(Color.rgb(9, 23, 36), Color.rgb(47, 74, 94), 12)
        setPadding(dp(14), dp(12), dp(14), dp(12))
        filters = arrayOf(InputFilter.LengthFilter(240))
        importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS
        layoutParams = LinearLayout.LayoutParams(-1, dp(50)).apply { topMargin = dp(7) }
    }

    fun button(value: String, primary: Boolean = false, danger: Boolean = false): Button =
        Button(context).apply {
            text = value; isAllCaps = false; textSize = 15f; gravity = Gravity.CENTER
            val color = if (danger) Color.rgb(246, 156, 150) else accent
            setTextColor(if (primary) Color.rgb(8, 28, 38) else color)
            background = surface(if (primary) accent else Color.rgb(17, 37, 53), color, 13)
            minHeight = dp(48); minimumHeight = dp(48)
            setPadding(dp(8), dp(8), dp(8), dp(8))
            layoutParams = LinearLayout.LayoutParams(-1, dp(48)).apply { topMargin = dp(12) }
        }

    fun label(value: String): TextView = text(value, 12f, muted).apply {
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) }
    }

    private fun surface(fill: Int, edge: Int, radius: Int): GradientDrawable = GradientDrawable().apply {
        setColor(fill); cornerRadius = dp(radius).toFloat(); setStroke(dp(1), edge)
    }
}
