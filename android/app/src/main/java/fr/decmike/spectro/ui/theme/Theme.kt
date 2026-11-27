package fr.decmike.spectro.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkScheme = darkColorScheme(
    primary = Color(0xFF8AB4F8),
    secondary = Color(0xFFA8C7FA),
    tertiary = Color(0xFFFFB74D),
    background = Color(0xFF101418),
    surface = Color(0xFF161B21),
    surfaceVariant = Color(0xFF232A31),
)

/** Mode nuit : tout en rouge sombre sur noir, pour garder l'adaptation à l'obscurité. */
private val NightScheme = darkColorScheme(
    primary = Color(0xFFD32F2F),
    onPrimary = Color(0xFF000000),
    primaryContainer = Color(0xFF3A0000),
    onPrimaryContainer = Color(0xFFE57373),
    secondary = Color(0xFFB71C1C),
    onSecondary = Color(0xFF000000),
    secondaryContainer = Color(0xFF2A0000),
    onSecondaryContainer = Color(0xFFE57373),
    tertiary = Color(0xFFFF5252),
    background = Color(0xFF000000),
    onBackground = Color(0xFFC62828),
    surface = Color(0xFF050000),
    onSurface = Color(0xFFC62828),
    surfaceVariant = Color(0xFF140000),
    onSurfaceVariant = Color(0xFFB71C1C),
    surfaceContainer = Color(0xFF0A0000),
    surfaceContainerHigh = Color(0xFF120000),
    surfaceContainerLow = Color(0xFF070000),
    outline = Color(0xFF7F0000),
    outlineVariant = Color(0xFF3A0000),
    error = Color(0xFFFF8A80),
)

/** Couleurs des courbes (normal / nuit). */
fun seriesColors(night: Boolean): List<Color> =
    if (night) listOf(Color(0xFFE53935), Color(0xFFFF8A80), Color(0xFF8E0000), Color(0xFFFF5252), Color(0xFFB71C1C))
    else listOf(Color(0xFF4FC3F7), Color(0xFFFFB74D), Color(0xFF81C784), Color(0xFFE57373), Color(0xFFBA68C8), Color(0xFFFFF176))

@Composable
fun SpectroTheme(night: Boolean, content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (night) NightScheme else DarkScheme, content = content)
}
