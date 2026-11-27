package fr.decmike.spectro.math

import kotlin.math.abs

/** Raie de référence (longueur d'onde dans l'air, nm). */
data class RefLine(val nm: Double, val label: String)

/** Catalogue de raies : lampes d'étalonnage et raies astrophysiques usuelles. */
object LineCatalog {

    val NEON = listOf(
        540.056, 585.249, 588.190, 594.483, 597.553, 603.000, 607.434, 609.616, 614.306,
        616.359, 621.728, 626.650, 630.479, 633.443, 638.299, 640.225, 650.653, 653.288,
        659.895, 667.828, 671.704, 692.947, 703.241, 717.394, 724.517, 743.890, 748.887,
        753.577, 754.404,
    ).map { RefLine(it, "Ne") }

    val MERCURY = listOf(404.656, 407.783, 435.833, 546.074, 576.960, 579.066).map { RefLine(it, "Hg") }

    /** Lampe fluocompacte : mercure + luminophores europium / terbium. */
    val CFL = MERCURY + listOf(
        RefLine(487.7, "Tb"), RefLine(542.4, "Tb"), RefLine(611.6, "Eu"), RefLine(631.1, "Eu"),
        RefLine(707.0, "Eu"), RefLine(709.2, "Eu"),
    )

    val ARGON = listOf(
        696.543, 706.722, 714.704, 727.294, 738.398, 750.387, 751.465, 763.511, 772.376,
        794.818, 800.616, 801.479, 810.369, 811.531, 826.452, 842.465, 852.144, 866.794,
        912.297, 922.450,
    ).map { RefLine(it, "Ar") }

    /** Raies astrophysiques (étoiles, nébuleuses, atmosphère terrestre). */
    val ASTRO = listOf(
        RefLine(656.281, "Hα"), RefLine(486.135, "Hβ"), RefLine(434.047, "Hγ"), RefLine(410.174, "Hδ"),
        RefLine(397.007, "Hε"), RefLine(393.366, "Ca II K"), RefLine(396.847, "Ca II H"),
        RefLine(587.562, "He I"), RefLine(667.815, "He I"), RefLine(447.148, "He I"), RefLine(468.6, "He II"),
        RefLine(588.995, "Na D2"), RefLine(589.592, "Na D1"),
        RefLine(516.733, "Mg b"), RefLine(517.268, "Mg b"), RefLine(518.362, "Mg b"),
        RefLine(527.0, "Fe I"), RefLine(430.8, "G (CH)"), RefLine(777.4, "O I"),
        RefLine(849.8, "Ca II"), RefLine(854.2, "Ca II"), RefLine(866.2, "Ca II"),
        RefLine(495.891, "[O III]"), RefLine(500.684, "[O III]"),
        RefLine(654.80, "[N II]"), RefLine(658.34, "[N II]"),
        RefLine(671.63, "[S II]"), RefLine(673.08, "[S II]"),
        RefLine(686.7, "O₂ B (tellurique)"), RefLine(759.4, "O₂ A (tellurique)"), RefLine(718.0, "H₂O (tellurique)"),
    )

    /** Lampes proposées pour l'étalonnage. */
    val LAMPS: Map<String, List<RefLine>> = linkedMapOf(
        "Néon" to NEON,
        "Mercure" to MERCURY,
        "Fluocompacte (Hg+Eu+Tb)" to CFL,
        "Argon" to ARGON,
        "Néon + Argon" to (NEON + ARGON).sortedBy { it.nm },
        "Mercure + Argon" to (MERCURY + ARGON).sortedBy { it.nm },
        "Raies stellaires" to ASTRO.sortedBy { it.nm },
    )

    /** Raie la plus proche de [nm] à moins de [tol] nm, ou null. */
    fun nearest(nm: Double, lines: List<RefLine>, tol: Double): RefLine? =
        lines.minByOrNull { abs(it.nm - nm) }?.takeIf { abs(it.nm - nm) <= tol }

    /**
     * Associe chaque pic (pixel) à une raie du catalogue d'après l'étalonnage courant [coeffs].
     * Chaque raie n'est attribuée qu'une fois (au pic le plus proche).
     */
    fun autoAssign(peaksPx: List<Double>, coeffs: DoubleArray, lines: List<RefLine>, tol: Double,
                   minSeparation: Double = 1.5): Map<Double, RefLine> {
        // les raies trop proches d'une voisine se mélangent sur le capteur : on les ignore
        val usable = lines.filter { l -> lines.none { o -> o !== l && abs(o.nm - l.nm) < minSeparation } }
        val cand = ArrayList<Triple<Double, RefLine, Double>>()
        for (p in peaksPx) {
            val l = SpectrumMath.polyval(coeffs, p)
            nearest(l, usable, tol)?.let { cand.add(Triple(p, it, abs(it.nm - l))) }
        }
        val out = LinkedHashMap<Double, RefLine>()
        val used = HashSet<Double>()
        for ((p, line, _) in cand.sortedBy { it.third }) {
            if (line.nm in used || p in out) continue
            out[p] = line; used.add(line.nm)
        }
        return out.toSortedMap()
    }

    /**
     * Étalonnage automatique robuste : attribution, ajustement, rejet du point le plus aberrant
     * tant que son écart dépasse [maxResid] nm, puis seconde passe avec une tolérance serrée.
     */
    fun robustCalibration(peaksPx: List<Double>, start: DoubleArray, lines: List<RefLine>, order: Int,
                          tol: Double = 3.0, maxResid: Double = 0.15): Pair<Map<Double, RefLine>, PolyFit>? {
        var coeffs = start
        var assigned: Map<Double, RefLine> = emptyMap()
        var fit: PolyFit? = null
        for (pass in 0 until 2) {
            val m = LinkedHashMap(autoAssign(peaksPx, coeffs, lines, if (pass == 0) tol else 0.6))
            while (m.size > order + 1) {
                val px = m.keys.toDoubleArray(); val nm = m.values.map { it.nm }.toDoubleArray()
                val f = SpectrumMath.polyfit(px, nm, order)
                val worst = f.residuals.indices.maxByOrNull { abs(f.residuals[it]) }!!
                if (abs(f.residuals[worst]) <= maxResid) { fit = f; break }
                m.remove(px[worst])
            }
            if (m.size <= order + 1) return null
            assigned = m
            coeffs = fit!!.coeffs
        }
        return Pair(assigned, fit!!)
    }
}
