package org.lifelane.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val DarkScheme = darkColorScheme(
    primary = PrimaryTeal,
    onPrimary = BackgroundDark,
    secondary = InformationBlue,
    background = BackgroundDark,
    onBackground = TextPrimaryDark,
    surface = SurfaceDark,
    onSurface = TextPrimaryDark,
    surfaceVariant = ElevatedDark,
    onSurfaceVariant = TextSecondaryDark,
    outline = BorderDark,
    error = EmergencyRed,
)

private val LightScheme = lightColorScheme(
    primary = ColorTokens.lightPrimary,
    onPrimary = SurfaceLight,
    secondary = InformationBlue,
    background = BackgroundLight,
    onBackground = TextPrimaryLight,
    surface = SurfaceLight,
    onSurface = TextPrimaryLight,
    surfaceVariant = ElevatedLight,
    onSurfaceVariant = TextSecondaryLight,
    outline = BorderLight,
    error = EmergencyRed,
)

private object ColorTokens {
    val lightPrimary = androidx.compose.ui.graphics.Color(0xFF087F75)
}

@Composable
fun LifeLaneTheme(darkTheme: Boolean = true, content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkScheme else LightScheme,
        typography = LifeLaneTypography,
        shapes = LifeLaneShapes,
        content = content,
    )
}
