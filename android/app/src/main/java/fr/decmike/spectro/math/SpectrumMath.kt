package fr.decmike.spectro.math

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sqrt

/** Mode de combinaison de plusieurs spectres. */
enum class Combine(val label: String) { SUM("Somme"), MEAN("Moyenne"), MEDIAN("Médiane") }

/** Résultat d'un ajustement polynomial (coefficients en x brut : c0 + c1·x + c2·x² …). */
data class PolyFit(val coeffs: DoubleArray, val residuals: DoubleArray, val rms: Double)

/** Mesure d'une raie entre deux bornes. */
data class LineMeasure(
    val center: Double,      // position du centre (unité de l'axe x)
    val fwhm: Double,        // largeur à mi-hauteur (unité de l'axe x)
    val depth: Double,       // hauteur (émission) ou profondeur (absorption) au-dessus/sous la ligne de base
    val baseline: Double,    // niveau de la ligne de base au centre
    val flux: Double,        // intégrale de (y - ligne de base)
    val ew: Double,          // largeur équivalente (unité de l'axe x) = ∫ (1 - y/base) dx
    val emission: Boolean,
)

/**
 * Calculs de spectroscopie, en Kotlin pur (aucune dépendance Android) :
 * opérations arithmétiques, combinaisons, lissages, pics, raies, étalonnage, continuum.
 */
object SpectrumMath {

    // ------------------------------------------------------------------ arithmétique
    private inline fun zip(a: DoubleArray, b: DoubleArray, f: (Double, Double) -> Double): DoubleArray {
        val n = min(a.size, b.size)
        return DoubleArray(n) { f(a[it], b[it]) }
    }

    fun add(a: DoubleArray, b: DoubleArray) = zip(a, b) { x, y -> x + y }
    fun subtract(a: DoubleArray, b: DoubleArray) = zip(a, b) { x, y -> x - y }
    fun multiply(a: DoubleArray, b: DoubleArray) = zip(a, b) { x, y -> x * y }

    /** a / b ; là où |b| est trop petit, le résultat vaut 0 (évite les divisions par ~0). */
    fun divide(a: DoubleArray, b: DoubleArray, eps: Double = 1e-6): DoubleArray {
        val bmax = b.maxOfOrNull { abs(it) } ?: 0.0
        val lim = max(eps, 1e-4 * bmax)
        return zip(a, b) { x, y -> if (abs(y) < lim) 0.0 else x / y }
    }

    fun scale(a: DoubleArray, k: Double) = DoubleArray(a.size) { a[it] * k }
    fun offset(a: DoubleArray, k: Double) = DoubleArray(a.size) { a[it] + k }

    fun combine(list: List<DoubleArray>, mode: Combine): DoubleArray {
        require(list.isNotEmpty()) { "aucun spectre à combiner" }
        val n = list.minOf { it.size }
        val out = DoubleArray(n)
        val col = DoubleArray(list.size)
        for (i in 0 until n) {
            when (mode) {
                Combine.SUM -> out[i] = list.sumOf { it[i] }
                Combine.MEAN -> out[i] = list.sumOf { it[i] } / list.size
                Combine.MEDIAN -> {
                    for (k in list.indices) col[k] = list[k][i]
                    out[i] = median(col)
                }
            }
        }
        return out
    }

    fun median(v: DoubleArray): Double {
        if (v.isEmpty()) return 0.0
        val s = v.sortedArray()
        val m = s.size / 2
        return if (s.size % 2 == 1) s[m] else 0.5 * (s[m - 1] + s[m])
    }

    // ------------------------------------------------------------------ normalisation
    fun normalizeMax(y: DoubleArray): DoubleArray {
        val m = y.maxOrNull() ?: return y
        return if (m == 0.0) y.copyOf() else scale(y, 1.0 / m)
    }

    /** Divise par la moyenne de la zone [i0, i1] (zone de continuum = 1). */
    fun normalizeRegion(y: DoubleArray, i0: Int, i1: Int): DoubleArray {
        val a = max(0, min(i0, i1)); val b = min(y.size - 1, max(i0, i1))
        if (b < a) return y.copyOf()
        var s = 0.0
        for (i in a..b) s += y[i]
        val m = s / (b - a + 1)
        return if (m == 0.0) y.copyOf() else scale(y, 1.0 / m)
    }

    /** Transmission en % : 100 · échantillon / référence. */
    fun transmission(sample: DoubleArray, reference: DoubleArray) = scale(divide(sample, reference), 100.0)

    /** Absorbance : −log10(T). */
    fun absorbance(sample: DoubleArray, reference: DoubleArray): DoubleArray {
        val t = divide(sample, reference)
        return DoubleArray(t.size) { -log10(max(t[it], 1e-4)) }
    }

    // ------------------------------------------------------------------ lissages
    fun boxcar(y: DoubleArray, width: Int): DoubleArray {
        if (width <= 1 || y.isEmpty()) return y.copyOf()
        val h = width / 2
        val out = DoubleArray(y.size)
        val pre = DoubleArray(y.size + 1)
        for (i in y.indices) pre[i + 1] = pre[i] + y[i]
        for (i in y.indices) {
            val a = max(0, i - h); val b = min(y.size - 1, i + h)
            out[i] = (pre[b + 1] - pre[a]) / (b - a + 1)
        }
        return out
    }

    /** Savitzky-Golay (fenêtre impaire, ordre 2 ou 3) : lisse en préservant la forme des raies. */
    fun savitzkyGolay(y: DoubleArray, window: Int, order: Int = 2): DoubleArray {
        var w = max(3, window)
        if (w % 2 == 0) w += 1
        val h = w / 2
        if (y.size < w) return y.copyOf()
        val o = min(order, w - 1)
        // coefficients du point central : 1re ligne de (AᵀA)⁻¹Aᵀ
        val ata = Array(o + 1) { DoubleArray(o + 1) }
        for (j in 0..o) for (k in 0..o) {
            var s = 0.0
            for (t in -h..h) s += t.toDouble().pow(j + k)
            ata[j][k] = s
        }
        val inv = invert(ata)
        val coef = DoubleArray(w) { idx ->
            val t = (idx - h).toDouble()
            var s = 0.0
            for (k in 0..o) s += inv[0][k] * t.pow(k)
            s
        }
        val out = DoubleArray(y.size)
        for (i in y.indices) {
            if (i < h || i >= y.size - h) { out[i] = y[i]; continue }
            var s = 0.0
            for (k in 0 until w) s += coef[k] * y[i - h + k]
            out[i] = s
        }
        return out
    }

    // ------------------------------------------------------------------ pics
    /**
     * Maxima locaux (ou minima si [absorption]) dépassant [threshold] (fraction de la dynamique),
     * espacés d'au moins [minDist] points, triés par position.
     */
    fun findPeaks(y: DoubleArray, threshold: Double = 0.1, minDist: Int = 8, maxPeaks: Int = 30,
                  absorption: Boolean = false): List<Int> {
        if (y.size < 3) return emptyList()
        val v = if (absorption) DoubleArray(y.size) { -y[it] } else y
        val lo = v.minOrNull()!!; val hi = v.maxOrNull()!!
        val thr = lo + threshold * (hi - lo)
        val cand = ArrayList<Int>()
        for (i in 1 until v.size - 1) if (v[i] > v[i - 1] && v[i] >= v[i + 1] && v[i] > thr) cand.add(i)
        cand.sortByDescending { v[it] }
        val kept = ArrayList<Int>()
        for (i in cand) {
            if (kept.all { abs(it - i) >= minDist }) kept.add(i)
            if (kept.size >= maxPeaks) break
        }
        return kept.sorted()
    }

    /** Position sous-pixel d'un pic : interpolation parabolique sur 3 points. */
    fun refinePeak(y: DoubleArray, i: Int): Double {
        if (i <= 0 || i >= y.size - 1) return i.toDouble()
        val a = y[i - 1]; val b = y[i]; val c = y[i + 1]
        val d = a - 2 * b + c
        if (d == 0.0) return i.toDouble()
        val off = 0.5 * (a - c) / d
        return i + off.coerceIn(-1.0, 1.0)
    }

    /**
     * Position sous-pixel d'un pic supposé gaussien : parabole sur le logarithme des 3 points
     * centraux, après soustraction du fond local (minimum sur ±[half] points). Exacte pour une gaussienne.
     */
    fun gaussPeak(y: DoubleArray, i: Int, half: Int = 8): Double {
        if (i <= 0 || i >= y.size - 1) return i.toDouble()
        plateauCenter(y, i)?.let { return it }
        var bg = Double.MAX_VALUE
        for (k in max(0, i - half)..min(y.size - 1, i + half)) bg = min(bg, y[k])
        val a = y[i - 1] - bg; val b = y[i] - bg; val c = y[i + 1] - bg
        if (a <= 0 || b <= 0 || c <= 0) return refinePeak(y, i)
        val la = ln(a); val lb = ln(b); val lc = ln(c)
        val d = la - 2 * lb + lc
        if (d >= 0) return refinePeak(y, i)
        return i + (0.5 * (la - lc) / d).coerceIn(-1.0, 1.0)
    }

    /**
     * Raie saturée (sommet plat) : renvoie le milieu du plateau autour de [i], ou null si le
     * sommet n'est pas plat (moins de 3 points au maximum).
     */
    fun plateauCenter(y: DoubleArray, i: Int, tol: Double = 1e-6): Double? {
        val top = y[i]
        val eps = tol * max(1.0, abs(top))
        var a = i; var b = i
        while (a > 0 && abs(y[a - 1] - top) <= eps) a--
        while (b < y.size - 1 && abs(y[b + 1] - top) <= eps) b++
        return if (b - a >= 2) 0.5 * (a + b) else null
    }

    /** Nombre de points sur des sommets plats (indice de saturation). */
    fun saturatedPoints(y: DoubleArray): Int {
        val top = y.maxOrNull() ?: return 0
        var n = 0
        for (v in y) if (abs(v - top) <= 1e-6 * max(1.0, abs(top))) n++
        return if (n >= 3) n else 0
    }

    /** Barycentre d'un pic au-dessus d'un fond linéaire sur ±[half] points. */
    fun centroid(y: DoubleArray, i: Int, half: Int = 4): Double {
        val a = max(0, i - half); val b = min(y.size - 1, i + half)
        val base0 = y[a]; val base1 = y[b]
        var s = 0.0; var sw = 0.0
        for (k in a..b) {
            val base = base0 + (base1 - base0) * (k - a) / max(1, b - a).toDouble()
            val w = max(0.0, y[k] - base)
            s += w * k; sw += w
        }
        return if (sw > 0) s / sw else i.toDouble()
    }

    // ------------------------------------------------------------------ mesure de raie
    /**
     * Mesure une raie entre les indices [i0] et [i1] : ligne de base linéaire entre les bords,
     * centre, FWHM (interpolée), flux et largeur équivalente. [x] = axe (pixels ou nm).
     */
    fun measureLine(x: DoubleArray, y: DoubleArray, i0: Int, i1: Int): LineMeasure? {
        val a = max(0, min(i0, i1)); val b = min(y.size - 1, max(i0, i1))
        if (b - a < 3) return null
        fun base(k: Int) = y[a] + (y[b] - y[a]) * (x[k] - x[a]) / (x[b] - x[a])
        var imax = a; var imin = a
        for (k in a..b) {
            val r = y[k] - base(k)
            if (r > y[imax] - base(imax)) imax = k
            if (r < y[imin] - base(imin)) imin = k
        }
        val emission = (y[imax] - base(imax)) >= -(y[imin] - base(imin))
        val ip = if (emission) imax else imin
        val depth = y[ip] - base(ip)
        if (depth == 0.0) return null
        val half = depth / 2
        fun r(k: Int) = (y[k] - base(k)) / half      // >1 à l'intérieur de la raie
        var l = ip
        while (l > a && r(l) > 1.0) l--
        var rr = ip
        while (rr < b && r(rr) > 1.0) rr++
        fun cross(k1: Int, k2: Int): Double {         // interpolation du passage à mi-hauteur
            val r1 = r(k1); val r2 = r(k2)
            val t = if (r1 == r2) 0.0 else (1.0 - r1) / (r2 - r1)
            return x[k1] + t * (x[k2] - x[k1])
        }
        val xl = if (l < ip) cross(l, l + 1) else x[ip]
        val xr = if (rr > ip) cross(rr - 1, rr) else x[ip]
        var flux = 0.0; var ew = 0.0; var m = 0.0; var mw = 0.0
        for (k in a until b) {
            val dx = x[k + 1] - x[k]
            val d0 = y[k] - base(k); val d1 = y[k + 1] - base(k + 1)
            flux += 0.5 * (d0 + d1) * dx
            val b0 = base(k); val b1 = base(k + 1)
            if (b0 != 0.0 && b1 != 0.0) ew += 0.5 * ((1 - y[k] / b0) + (1 - y[k + 1] / b1)) * dx
            val w = abs(d0)
            m += w * x[k]; mw += w
        }
        val center = if (mw > 0) m / mw else x[ip]
        return LineMeasure(center = center, fwhm = abs(xr - xl), depth = depth, baseline = base(ip),
                           flux = flux, ew = ew, emission = emission)
    }

    // ------------------------------------------------------------------ polynômes
    fun polyval(c: DoubleArray, x: Double): Double {
        var s = 0.0
        for (k in c.indices.reversed()) s = s * x + c[k]
        return s
    }

    fun polyval(c: DoubleArray, x: DoubleArray) = DoubleArray(x.size) { polyval(c, x[it]) }

    /**
     * Moindres carrés polynomiaux, bien conditionnés (x centré-réduit), puis coefficients
     * ramenés en x brut : y = c0 + c1·x + c2·x² + …
     */
    fun polyfit(x: DoubleArray, y: DoubleArray, order: Int, w: DoubleArray? = null): PolyFit {
        require(x.size == y.size) { "tailles différentes" }
        val o = min(order, x.size - 1)
        require(o >= 0) { "aucun point" }
        val xm = x.average()
        val xs = max(1e-12, x.maxOf { abs(it - xm) })
        val n = o + 1
        val ata = Array(n) { DoubleArray(n) }
        val aty = DoubleArray(n)
        for (i in x.indices) {
            val t = (x[i] - xm) / xs
            val wi = w?.get(i) ?: 1.0
            val pw = DoubleArray(n)
            var p = 1.0
            for (k in 0 until n) { pw[k] = p; p *= t }
            for (j in 0 until n) {
                aty[j] += wi * pw[j] * y[i]
                for (k in 0 until n) ata[j][k] += wi * pw[j] * pw[k]
            }
        }
        val d = solve(ata, aty)
        // développement : Σ d_k ((x - xm)/xs)^k  →  Σ c_j x^j
        val c = DoubleArray(n)
        for (k in 0 until n) {
            val dk = d[k] / xs.pow(k)
            for (j in 0..k) c[j] += dk * binom(k, j) * (-xm).pow(k - j)
        }
        val res = DoubleArray(x.size) { y[it] - polyval(c, x[it]) }
        val rms = if (res.isEmpty()) 0.0 else sqrt(res.sumOf { it * it } / res.size)
        return PolyFit(c, res, rms)
    }

    private fun binom(n: Int, k: Int): Double {
        var r = 1.0
        for (i in 1..k) r = r * (n - k + i) / i
        return r
    }

    /** Résolution de A·x = b (pivot de Gauss partiel). */
    fun solve(a0: Array<DoubleArray>, b0: DoubleArray): DoubleArray {
        val n = b0.size
        val a = Array(n) { a0[it].copyOf() }
        val b = b0.copyOf()
        for (col in 0 until n) {
            var p = col
            for (r in col + 1 until n) if (abs(a[r][col]) > abs(a[p][col])) p = r
            require(abs(a[p][col]) > 1e-300) { "système singulier" }
            val tr = a[p]; a[p] = a[col]; a[col] = tr
            val tb = b[p]; b[p] = b[col]; b[col] = tb
            for (r in col + 1 until n) {
                val f = a[r][col] / a[col][col]
                for (k in col until n) a[r][k] -= f * a[col][k]
                b[r] -= f * b[col]
            }
        }
        val x = DoubleArray(n)
        for (r in n - 1 downTo 0) {
            var s = b[r]
            for (k in r + 1 until n) s -= a[r][k] * x[k]
            x[r] = s / a[r][r]
        }
        return x
    }

    private fun invert(m: Array<DoubleArray>): Array<DoubleArray> {
        val n = m.size
        return Array(n) { i ->
            val e = DoubleArray(n); e[i] = 1.0
            solve(m, e)
        }.let { cols -> Array(n) { r -> DoubleArray(n) { c -> cols[c][r] } } }
    }

    // ------------------------------------------------------------------ continuum
    /**
     * Continuum par polynôme avec rejet itératif : les points sous −[kLow]σ (raies d'absorption)
     * et au-dessus de +[kHigh]σ (raies d'émission) sont écartés à chaque passe.
     */
    fun continuum(x: DoubleArray, y: DoubleArray, order: Int = 3, iterations: Int = 6,
                  kLow: Double = 1.5, kHigh: Double = 3.0): DoubleArray {
        var keep = BooleanArray(y.size) { true }
        var c = DoubleArray(1)
        repeat(iterations) {
            val xs = x.filterIndexed { i, _ -> keep[i] }.toDoubleArray()
            val ys = y.filterIndexed { i, _ -> keep[i] }.toDoubleArray()
            if (xs.size <= order + 1) return@repeat
            c = polyfit(xs, ys, order).coeffs
            val r = DoubleArray(y.size) { y[it] - polyval(c, x[it]) }
            val kr = r.filterIndexed { i, _ -> keep[i] }
            val sd = sqrt(kr.sumOf { it * it } / max(1, kr.size))
            val nk = BooleanArray(y.size) { r[it] > -kLow * sd && r[it] < kHigh * sd }
            if (nk.contentEquals(keep)) return polyval(c, x)
            keep = nk
        }
        return polyval(c, x)
    }

    // ------------------------------------------------------------------ divers
    /** Vitesse radiale (km/s) d'après le décalage d'une raie. */
    fun radialVelocity(observed: Double, rest: Double) = 299_792.458 * (observed - rest) / rest

    /** Loi de Planck (relative), λ en nm. */
    fun planck(lambdaNm: Double, tempK: Double): Double {
        val l = lambdaNm * 1e-9
        val c2 = 1.438776877e-2
        return 1.0 / (l.pow(5) * (exp(c2 / (l * tempK)) - 1.0))
    }

    /** Rééchantillonnage linéaire sur une grille régulière. x doit être croissant. */
    fun resample(x: DoubleArray, y: DoubleArray, x0: Double, step: Double, n: Int): DoubleArray {
        val out = DoubleArray(n)
        var j = 0
        for (i in 0 until n) {
            val xi = x0 + i * step
            while (j < x.size - 2 && x[j + 1] < xi) j++
            val t = if (x[j + 1] == x[j]) 0.0 else (xi - x[j]) / (x[j + 1] - x[j])
            out[i] = y[j] + t.coerceIn(0.0, 1.0) * (y[j + 1] - y[j])
        }
        return out
    }

    /** Rapport signal/bruit d'une zone de continuum : moyenne / écart-type. */
    fun snr(y: DoubleArray, i0: Int, i1: Int): Double {
        val a = max(0, min(i0, i1)); val b = min(y.size - 1, max(i0, i1))
        if (b - a < 2) return 0.0
        val seg = y.sliceArray(a..b)
        val m = seg.average()
        val sd = sqrt(seg.sumOf { (it - m) * (it - m) } / (seg.size - 1))
        return if (sd > 0) m / sd else 0.0
    }

    /** ln utilitaire évitant les valeurs ≤ 0. */
    fun safeLn(v: Double) = ln(max(v, 1e-300))
}
