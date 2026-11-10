package fr.decmike.spectro.math

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale

/** Exports texte (CSV) et FITS 1D, sans dépendance Android. */
object Formats {

    fun csv(name: String, values: DoubleArray, coeffs: DoubleArray?, meta: Map<String, Any?> = emptyMap()): String {
        val sb = StringBuilder()
        sb.append("# ").append(name)
        for ((k, v) in meta) if (v != null) sb.append(' ').append(k).append('=').append(v)
        sb.append('\n')
        if (coeffs != null) {
            sb.append("pixel;lambda_nm;intensite\n")
            for (i in values.indices) {
                sb.append(i).append(';')
                    .append(String.format(Locale.ROOT, "%.4f", SpectrumMath.polyval(coeffs, i.toDouble()))).append(';')
                    .append(String.format(Locale.ROOT, "%.4f", values[i])).append('\n')
            }
        } else {
            sb.append("pixel;intensite\n")
            for (i in values.indices) sb.append(i).append(';')
                .append(String.format(Locale.ROOT, "%.4f", values[i])).append('\n')
        }
        return sb.toString()
    }

    private fun card(key: String, value: Any): String {
        val v = when (value) {
            is Boolean -> String.format(Locale.ROOT, "%20s", if (value) "T" else "F")
            is Int -> String.format(Locale.ROOT, "%20d", value)
            is Long -> String.format(Locale.ROOT, "%20d", value)
            is Double -> String.format(Locale.ROOT, "%20s", String.format(Locale.ROOT, "%.10G", value))
            else -> "'" + value.toString().replace("'", "''").padEnd(8) + "'"
        }
        return String.format(Locale.ROOT, "%-8s= %s", key, v).take(80).padEnd(80)
    }

    /**
     * FITS 1D en réels 32 bits. Si étalonné, le spectre est rééchantillonné sur une grille
     * linéaire en ångströms (CRVAL1 / CDELT1), comme l'attendent ISIS, BASS ou VisualSpec.
     */
    fun fits(name: String, values: DoubleArray, coeffs: DoubleArray?, exptimeS: Double, dateObs: String,
             kind: String): ByteArray {
        var y = values
        val cards = ArrayList<String>()
        cards += card("SIMPLE", true); cards += card("BITPIX", -32); cards += card("NAXIS", 1)
        cards += card("NAXIS1", values.size)
        if (coeffs != null) {
            val lam = DoubleArray(values.size) { 10.0 * SpectrumMath.polyval(coeffs, it.toDouble()) }
            val idx = lam.indices.sortedBy { lam[it] }
            val ls = DoubleArray(lam.size) { lam[idx[it]] }
            val ys = DoubleArray(lam.size) { values[idx[it]] }
            val step = (ls.last() - ls.first()) / (ls.size - 1)
            y = SpectrumMath.resample(ls, ys, ls.first(), step, ls.size)
            cards += card("CRPIX1", 1.0); cards += card("CRVAL1", ls.first()); cards += card("CDELT1", step)
            cards += card("CTYPE1", "WAVE"); cards += card("CUNIT1", "Angstrom")
        } else {
            cards += card("CRPIX1", 1.0); cards += card("CRVAL1", 0.0); cards += card("CDELT1", 1.0)
            cards += card("CTYPE1", "PIXEL")
        }
        cards += card("OBJECT", name.take(60)); cards += card("DATE-OBS", dateObs.take(19))
        cards += card("EXPTIME", exptimeS); cards += card("IMAGETYP", kind)
        cards += card("INSTRUME", "TCD1304DG spectro"); cards += card("ORIGIN", "Spectro Android")
        val hdr = StringBuilder()
        for (c in cards) hdr.append(c)
        hdr.append("END".padEnd(80))
        while (hdr.length % 2880 != 0) hdr.append(' ')
        val data = ByteBuffer.allocate(((y.size * 4 + 2879) / 2880) * 2880).order(ByteOrder.BIG_ENDIAN)
        for (v in y) data.putFloat(v.toFloat())
        return hdr.toString().toByteArray(Charsets.US_ASCII) + data.array()
    }
}
