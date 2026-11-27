package fr.decmike.spectro

import fr.decmike.spectro.math.Combine
import fr.decmike.spectro.math.Formats
import fr.decmike.spectro.math.LineCatalog
import fr.decmike.spectro.math.SpectrumMath
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.sqrt

class SpectrumMathTest {
    private val coeffs = doubleArrayOf(350.0, 0.135, -2.0e-6, 1.0e-10)
    private fun lam(p: Double) = SpectrumMath.polyval(coeffs, p)

    /** Spectre synthétique : raies gaussiennes (σ en nm) + fond. */
    private fun lampSpectrum(lines: List<Double>, sigmaNm: Double = 0.6): DoubleArray =
        DoubleArray(3648) { i ->
            val l = lam(i.toDouble())
            20.0 + lines.sumOf { 3000.0 * exp(-0.5 * ((l - it) / sigmaNm) * ((l - it) / sigmaNm)) }
        }

    @Test fun arithmetic() {
        val a = doubleArrayOf(1.0, 2.0, 3.0); val b = doubleArrayOf(1.0, 1.0, 0.0)
        assertEquals(listOf(2.0, 3.0, 3.0), SpectrumMath.add(a, b).toList())
        assertEquals(listOf(0.0, 1.0, 3.0), SpectrumMath.subtract(a, b).toList())
        assertEquals(listOf(1.0, 2.0, 0.0), SpectrumMath.divide(a, b).toList())   // division par ~0 -> 0
    }

    @Test fun combine() {
        val l = listOf(doubleArrayOf(1.0, 10.0), doubleArrayOf(2.0, 20.0), doubleArrayOf(9.0, 30.0))
        assertEquals(listOf(12.0, 60.0), SpectrumMath.combine(l, Combine.SUM).toList())
        assertEquals(listOf(4.0, 20.0), SpectrumMath.combine(l, Combine.MEAN).toList())
        assertEquals(listOf(2.0, 20.0), SpectrumMath.combine(l, Combine.MEDIAN).toList())
    }

    @Test fun polyfitCubicExact() {
        val x = DoubleArray(12) { 100.0 + it * 300.0 }
        val y = DoubleArray(x.size) { lam(x[it]) }
        val f = SpectrumMath.polyfit(x, y, 3)
        for (i in coeffs.indices) assertEquals(coeffs[i], f.coeffs[i], abs(coeffs[i]) * 1e-6 + 1e-12)
        assertTrue(f.rms < 1e-8)
    }

    @Test fun savitzkyGolayKeepsQuadratic() {
        val y = DoubleArray(50) { 3.0 + 2.0 * it - 0.1 * it * it }
        val s = SpectrumMath.savitzkyGolay(y, 7, 2)
        for (i in 3 until 47) assertEquals(y[i], s[i], 1e-9)
    }

    @Test fun calibrationEndToEnd() {
        val hgAr = (LineCatalog.MERCURY + LineCatalog.ARGON).map { it.nm }.filter { it < lam(3647.0) }
        val y = lampSpectrum(hgAr)
        val peaks = SpectrumMath.findPeaks(y, 0.05, 6, 40).map { SpectrumMath.gaussPeak(y, it) }
        // étalonnage de départ grossier (décalé de 1,5 nm)
        val start = coeffs.copyOf().also { it[0] += 1.5 }
        val (assigned, fit) = LineCatalog.robustCalibration(peaks, start, LineCatalog.MERCURY + LineCatalog.ARGON, 3)!!
        assertTrue("au moins 8 raies identifiées : ${assigned.size}", assigned.size >= 8)
        assertTrue("rms < 0,02 nm : ${fit.rms}", fit.rms < 0.02)
        assertEquals(lam(2000.0), SpectrumMath.polyval(fit.coeffs, 2000.0), 0.02)
    }

    @Test fun saturatedLines() {
        // raies écrêtées à 2000 : le centre du plateau doit rester juste
        val hgAr = (LineCatalog.MERCURY + LineCatalog.ARGON).map { it.nm }.filter { it < lam(3647.0) }
        val y = lampSpectrum(hgAr).map { minOf(it, 2000.0) }.toDoubleArray()
        assertTrue(SpectrumMath.saturatedPoints(y) > 0)
        val peaks = SpectrumMath.findPeaks(y, 0.05, 6, 40).map { SpectrumMath.gaussPeak(y, it) }
        val (assigned, fit) = LineCatalog.robustCalibration(peaks, coeffs, LineCatalog.MERCURY + LineCatalog.ARGON, 3)!!
        assertTrue("au moins 8 raies : ${assigned.size}", assigned.size >= 8)
        assertTrue("rms ${fit.rms}", fit.rms < 0.05)
    }

    @Test fun measureGaussianLine() {
        val sigma = 0.6
        val y = lampSpectrum(listOf(546.074), sigma)
        val x = DoubleArray(y.size) { lam(it.toDouble()) }
        val i = x.indices.minByOrNull { abs(x[it] - 546.074) }!!
        val m = SpectrumMath.measureLine(x, y, i - 40, i + 40)
        assertNotNull(m)
        m!!
        assertTrue(m.emission)
        assertEquals(546.074, m.center, 0.01)
        assertEquals(2.3548 * sigma, m.fwhm, 0.03)
        assertEquals(3000.0 * sigma * sqrt(2 * Math.PI), m.flux, 30.0)
    }

    @Test fun equivalentWidthAbsorption() {
        // continuum 1, raie d'absorption gaussienne profondeur 0,5, σ = 0,4 nm  ->  EW = 0,5·σ·√(2π)
        val x = DoubleArray(2001) { 650.0 + it * 0.005 }
        val y = DoubleArray(x.size) { 1.0 - 0.5 * exp(-0.5 * ((x[it] - 655.0) / 0.4) * ((x[it] - 655.0) / 0.4)) }
        val m = SpectrumMath.measureLine(x, y, 0, x.size - 1)!!
        assertTrue(!m.emission)
        assertEquals(0.5 * 0.4 * sqrt(2 * Math.PI), m.ew, 0.005)
        assertEquals(655.0, m.center, 0.01)
    }

    @Test fun continuumIgnoresLines() {
        val x = DoubleArray(1000) { it.toDouble() }
        val cont = DoubleArray(x.size) { 100.0 + 0.05 * it - 2e-5 * it * it }
        val y = DoubleArray(x.size) { cont[it] - 60.0 * exp(-0.5 * ((it - 400.0) / 5.0) * ((it - 400.0) / 5.0)) }
        val c = SpectrumMath.continuum(x, y, 2)
        for (i in listOf(100, 400, 800)) assertEquals(cont[i], c[i], 0.5)
    }

    @Test fun radialVelocity() {
        assertEquals(299.792458, SpectrumMath.radialVelocity(656.281 * 1.001, 656.281), 1e-6)
    }

    @Test fun fitsHeader() {
        val b = Formats.fits("test", DoubleArray(100) { it.toDouble() }, coeffs, 1.0, "2026-11-09T20:00:00", "light")
        assertEquals(0, b.size % 2880)
        val h = String(b, 0, 2880, Charsets.US_ASCII)
        assertTrue(h.startsWith("SIMPLE  =                    T"))
        assertTrue(h.contains("CDELT1"))
    }
}
