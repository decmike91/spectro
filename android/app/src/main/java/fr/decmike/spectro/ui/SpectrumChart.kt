package fr.decmike.spectro.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import java.util.Locale
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToInt

data class ChartSeries(val values: DoubleArray, val color: Color, val label: String = "")
data class ChartMarker(val index: Double, val label: String, val color: Color)

/** Graduations « rondes » entre lo et hi. */
fun niceTicks(lo: Double, hi: Double, target: Int = 6): List<Double> {
    if (!(hi > lo)) return listOf(lo)
    val raw = (hi - lo) / target
    val mag = 10.0.pow(floor(log10(raw)))
    val step = listOf(1.0, 2.0, 2.5, 5.0, 10.0).map { it * mag }.first { it >= raw }
    val out = ArrayList<Double>()
    var v = ceil(lo / step) * step
    while (v <= hi + 1e-9 * step) { out.add(v); v += step }
    return out
}

fun fmt(v: Double, digits: Int = 1): String {
    val r = String.format(Locale.ROOT, "%.${digits}f", v)
    return if (r.startsWith("-") && r.trimStart('-').all { it == '0' || it == '.' }) r.substring(1) else r
}

/**
 * Graphique de spectre : pincer pour zoomer (axe horizontal), glisser pour se déplacer,
 * toucher pour placer le curseur, double-toucher pour tout revoir.
 * [toNm] convertit un indice de pixel en longueur d'onde (axe en nm), sinon axe en pixels.
 */
@Composable
fun SpectrumChart(
    series: List<ChartSeries>,
    modifier: Modifier = Modifier,
    height: Dp = 260.dp,
    toNm: ((Double) -> Double)? = null,
    markers: List<ChartMarker> = emptyList(),
    cursor: Int? = null,
    onCursor: ((Int) -> Unit)? = null,
    region: Pair<Int, Int>? = null,
) {
    val n = series.maxOfOrNull { it.values.size } ?: 0
    var x0 by remember(n) { mutableDoubleStateOf(0.0) }
    var x1 by remember(n) { mutableDoubleStateOf(max(1.0, n - 1.0)) }
    val fg = MaterialTheme.colorScheme.onSurface
    val grid = MaterialTheme.colorScheme.outlineVariant
    val accent = MaterialTheme.colorScheme.tertiary
    val padL = 110f; val padR = 16f; val padT = 34f; val padB = 56f

    Canvas(
        modifier
            .fillMaxWidth()
            .height(height)
            .pointerInput(n) {
                detectTransformGestures { centroid, pan, zoom, _ ->
                    if (n < 2) return@detectTransformGestures
                    val w = size.width - padL - padR
                    val span = x1 - x0
                    val cx = x0 + ((centroid.x - padL) / w).coerceIn(0f, 1f) * span
                    val ns = (span / zoom).coerceIn(8.0, n - 1.0)
                    var nx0 = cx - (cx - x0) * ns / span - pan.x / w * ns
                    nx0 = nx0.coerceIn(0.0, n - 1.0 - ns)
                    x0 = nx0; x1 = nx0 + ns
                }
            }
            .pointerInput(n, onCursor) {
                detectTapGestures(
                    onDoubleTap = { x0 = 0.0; x1 = max(1.0, n - 1.0) },
                    onTap = { off ->
                        if (n > 1 && onCursor != null) {
                            val w = size.width - padL - padR
                            val idx = x0 + ((off.x - padL) / w).coerceIn(0f, 1f) * (x1 - x0)
                            onCursor(idx.roundToInt().coerceIn(0, n - 1))
                        }
                    },
                )
            },
    ) {
        val w = size.width - padL - padR
        val h = size.height - padT - padB
        val paint = android.graphics.Paint().apply {
            color = fg.toArgb(); textSize = 26f; isAntiAlias = true
        }
        if (n < 2) {
            drawContext.canvas.nativeCanvas.drawText("Aucun spectre", padL + 20f, padT + h / 2, paint)
            return@Canvas
        }
        val i0 = max(0, floor(x0).toInt()); val i1 = min(n - 1, ceil(x1).toInt())
        var lo = Double.MAX_VALUE; var hi = -Double.MAX_VALUE
        for (s in series) for (i in i0..min(i1, s.values.size - 1)) {
            val v = s.values[i]
            if (v.isFinite()) { lo = min(lo, v); hi = max(hi, v) }
        }
        if (lo == Double.MAX_VALUE) { lo = 0.0; hi = 1.0 }
        if (hi - lo < 1e-9) { lo -= 1.0; hi += 1.0 }
        val m = 0.06 * (hi - lo); lo -= m; hi += m
        fun px(i: Double) = (padL + (i - x0) / (x1 - x0) * w).toFloat()
        fun py(v: Double) = (padT + h - (v - lo) / (hi - lo) * h).toFloat()

        // zone sélectionnée
        region?.let { (a, b) ->
            val xa = px(min(a, b).toDouble()).coerceIn(padL, padL + w)
            val xb = px(max(a, b).toDouble()).coerceIn(padL, padL + w)
            drawRect(accent.copy(alpha = 0.15f), Offset(xa, padT), Size(xb - xa, h))
        }
        // grille et graduations Y
        val nc = drawContext.canvas.nativeCanvas
        for (t in niceTicks(lo, hi, 5)) {
            val y = py(t)
            drawLine(grid, Offset(padL, y), Offset(padL + w, y), 1f)
            val lab = if (abs(hi - lo) < 10) fmt(t, 2) else if (abs(hi - lo) < 100) fmt(t, 1) else fmt(t, 0)
            nc.drawText(lab, 4f, y + 9f, paint)
        }
        // graduations X (pixels ou nm)
        val f = toNm
        if (f != null) {
            val l0 = f(x0); val l1 = f(x1)
            for (t in niceTicks(min(l0, l1), max(l0, l1), 6)) {
                val idx = invert(f, t, x0, x1)
                val x = px(idx)
                drawLine(grid, Offset(x, padT), Offset(x, padT + h), 1f)
                nc.drawText(fmt(t, if (abs(l1 - l0) < 5) 1 else 0), x - 26f, padT + h + 34f, paint)
            }
            nc.drawText("nm", padL + w - 40f, padT + h + 54f, paint)
        } else {
            for (t in niceTicks(x0, x1, 6)) {
                val x = px(t)
                drawLine(grid, Offset(x, padT), Offset(x, padT + h), 1f)
                nc.drawText(fmt(t, 0), x - 24f, padT + h + 34f, paint)
            }
            nc.drawText("px", padL + w - 40f, padT + h + 54f, paint)
        }
        drawRect(grid, Offset(padL, padT), Size(w, h), style = Stroke(1.5f))

        // courbes (décimation min/max par colonne de pixels)
        clipRectSafe(padL, padT, w, h) {
            for (s in series) {
                val path = Path()
                val last = min(i1, s.values.size - 1)
                if (last <= i0) continue
                val count = last - i0 + 1
                val cols = max(1, w.toInt())
                var first = true
                if (count > 2 * cols) {
                    for (c in 0 until cols) {
                        val a = i0 + (c.toLong() * count / cols).toInt()
                        val b = min(last, i0 + ((c + 1).toLong() * count / cols).toInt())
                        var mn = Double.MAX_VALUE; var mx = -Double.MAX_VALUE
                        for (k in a..b) { val v = s.values[k]; if (v < mn) mn = v; if (v > mx) mx = v }
                        val x = padL + c.toFloat()
                        if (first) { path.moveTo(x, py(mn)); first = false } else path.lineTo(x, py(mn))
                        path.lineTo(x, py(mx))
                    }
                } else {
                    for (k in i0..last) {
                        val x = px(k.toDouble()); val y = py(s.values[k])
                        if (first) { path.moveTo(x, y); first = false } else path.lineTo(x, y)
                    }
                }
                drawPath(path, s.color, style = Stroke(2.2f))
            }
            // repères (raies)
            val mp = android.graphics.Paint(paint).apply { textSize = 22f }
            for (mk in markers) {
                if (mk.index < x0 || mk.index > x1) continue
                val x = px(mk.index)
                drawLine(mk.color, Offset(x, padT), Offset(x, padT + h), 1.5f,
                         pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 8f)))
                mp.color = mk.color.toArgb()
                nc.save(); nc.rotate(-90f, x - 4f, padT + 8f)
                nc.drawText(mk.label, x - 4f - mp.measureText(mk.label), padT + 8f, mp)
                nc.restore()
            }
        }
        // curseur
        cursor?.let { c ->
            if (c >= x0 && c <= x1) {
                val x = px(c.toDouble())
                drawLine(accent, Offset(x, padT), Offset(x, padT + h), 2f)
                val v = series.firstOrNull()?.values?.getOrNull(c)
                val pos = if (f != null) "λ " + fmt(f(c.toDouble()), 2) + " nm" else "px $c"
                val txt = pos + (if (v != null) "   I " + fmt(v, 1) else "")
                val p2 = android.graphics.Paint(paint).apply { color = accent.toArgb() }
                val tw = p2.measureText(txt)
                nc.drawText(txt, (x + 8f).coerceAtMost(padL + w - tw), padT - 8f, p2)
            }
        }
        // légende
        var lx = padL + 8f
        for (s in series) if (s.label.isNotEmpty()) {
            val p3 = android.graphics.Paint(paint).apply { color = s.color.toArgb(); textSize = 22f }
            nc.drawText(s.label, lx, padT + h + 54f, p3)
            lx += p3.measureText(s.label) + 24f
            if (lx > padL + w - 120f) break
        }
    }
}

private inline fun androidx.compose.ui.graphics.drawscope.DrawScope.clipRectSafe(
    l: Float, t: Float, w: Float, h: Float, block: androidx.compose.ui.graphics.drawscope.DrawScope.() -> Unit,
) {
    drawContext.canvas.save()
    drawContext.canvas.clipRect(l, t, l + w, t + h)
    block()
    drawContext.canvas.restore()
}

/** Indice (fractionnaire) où la fonction monotone f vaut target, cherché entre a et b. */
fun invert(f: (Double) -> Double, target: Double, a: Double, b: Double): Double {
    var lo = a; var hi = b
    val inc = f(b) >= f(a)
    repeat(50) {
        val mid = 0.5 * (lo + hi)
        if ((f(mid) < target) == inc) lo = mid else hi = mid
    }
    return 0.5 * (lo + hi)
}
