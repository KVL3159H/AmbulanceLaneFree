package org.lifelane.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import org.lifelane.mobile.ThemeMode

private val LightScheme = lightColorScheme(
    primary = SwiggyOrange,
    onPrimary = Color.White,
    primaryContainer = SwiggyOrangeSoft,
    onPrimaryContainer = SwiggyOrangeDark,
    secondary = SwiggyGreen,
    onSecondary = Color.White,
    secondaryContainer = SwiggyGreenSoft,
    onSecondaryContainer = SwiggyGreenDark,
    background = SwiggyCanvas,
    onBackground = SwiggyTextHeading,
    surface = SwiggySurface,
    onSurface = SwiggyTextHeading,
    surfaceVariant = SwiggyOrangeSoft,
    onSurfaceVariant = SwiggyTextBody,
    outline = SwiggyBorder,
    outlineVariant = SwiggyBorderSoft,
    error = EmergencyRed,
    onError = Color.White,
    errorContainer = Color(0xFFFFEBEE),
    onErrorContainer = Color(0xFFC62828),
)

private val DarkScheme = darkColorScheme(
    primary = SwiggyOrange,
    onPrimary = Color.White,
    primaryContainer = Color(0xFF332014),
    onPrimaryContainer = SwiggyOrange,
    secondary = SwiggyGreen,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFF142E18),
    onSecondaryContainer = Color(0xFF8CE36B),
    background = SwiggyDarkCanvas,
    onBackground = SwiggyDarkTextHeading,
    surface = SwiggyDarkSurface,
    onSurface = SwiggyDarkTextHeading,
    surfaceVariant = SwiggyDarkRaised,
    onSurfaceVariant = SwiggyDarkTextBody,
    outline = SwiggyDarkBorder,
    outlineVariant = SwiggyDarkBorder,
    error = EmergencyRed,
    onError = Color.White,
    errorContainer = Color(0xFF4C1D1D),
    onErrorContainer = Color(0xFFFCA5A5),
)

object SwiggyTokens {
    val brandGradient = Brush.horizontalGradient(listOf(SwiggyOrange, SwiggyOrangeGlow))
    val darkBrandGradient = Brush.horizontalGradient(listOf(SwiggyOrangeDark, SwiggyOrange))

    @Composable fun topBarBackground(darkTheme: Boolean): Color = if (darkTheme) SwiggyDarkSurface else SwiggySurface
    @Composable fun topBarText(darkTheme: Boolean): Color = if (darkTheme) SwiggyDarkTextHeading else SwiggyTextHeading
    @Composable fun pillContainer(darkTheme: Boolean): Color = if (darkTheme) Color(0xFF332014) else SwiggyOrangeSoft
    @Composable fun pillText(darkTheme: Boolean): Color = if (darkTheme) SwiggyOrange else SwiggyOrangeDark
    @Composable fun successContainer(darkTheme: Boolean): Color = if (darkTheme) Color(0xFF142E18) else SwiggyGreenSoft
    @Composable fun successText(darkTheme: Boolean): Color = if (darkTheme) Color(0xFF8CE36B) else SwiggyGreenDark
    @Composable fun etaBadgeBackground(darkTheme: Boolean): Color = if (darkTheme) SwiggyDarkRaised else SwiggyTextHeading
}

object LifeLaneTokens {
    @Composable fun selectedSurface(): Color = MaterialTheme.colorScheme.primaryContainer
    @Composable fun trustSurface(): Color = MaterialTheme.colorScheme.secondaryContainer
    @Composable fun trustText(): Color = MaterialTheme.colorScheme.onSecondaryContainer
}

object WhatsAppTokens {
    fun topBarColor(darkTheme: Boolean) = if (darkTheme) SwiggyDarkSurface else SwiggySurface
    fun topBarContentColor(darkTheme: Boolean) = if (darkTheme) SwiggyDarkTextHeading else SwiggyTextHeading
    fun outgoingBubbleColor(darkTheme: Boolean) = if (darkTheme) Color(0xFF332014) else SwiggyOrangeSoft
    fun incomingBubbleColor(darkTheme: Boolean) = if (darkTheme) SwiggyDarkSurface else SwiggySurface
    fun securityCardBackground(darkTheme: Boolean) = if (darkTheme) Color(0xFF142E18) else SwiggyGreenSoft
    fun securityCardTextColor(darkTheme: Boolean) = if (darkTheme) Color(0xFF8CE36B) else SwiggyGreenDark
}

@Composable
fun LifeLaneTheme(themeMode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (themeMode) {
        ThemeMode.DARK -> true
        ThemeMode.LIGHT -> false
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
    }
    LifeLaneTheme(darkTheme = dark, content = content)
}

@Composable
fun LifeLaneTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkScheme else LightScheme,
        typography = LifeLaneTypography,
        shapes = LifeLaneShapes,
        content = content,
    )
}
