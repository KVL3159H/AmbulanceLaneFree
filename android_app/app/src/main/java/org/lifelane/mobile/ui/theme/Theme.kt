package org.lifelane.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkScheme = darkColorScheme(
    primary = WhatsAppAccentGreenDark,
    onPrimary = Color(0xFF00382E),
    primaryContainer = WhatsAppBubbleOutgoingDark,
    onPrimaryContainer = WhatsAppTextPrimaryDark,
    secondary = WhatsAppVibrantGreen,
    onSecondary = Color(0xFF003915),
    tertiary = WhatsAppBlueTick,
    background = WhatsAppBackgroundDark,
    onBackground = WhatsAppTextPrimaryDark,
    surface = WhatsAppSurfaceDark,
    onSurface = WhatsAppTextPrimaryDark,
    surfaceVariant = WhatsAppElevatedDark,
    onSurfaceVariant = WhatsAppTextSecondaryDark,
    outline = WhatsAppBorderDark,
    outlineVariant = Color(0xFF1F2C34),
    error = EmergencyRed,
)

private val LightScheme = lightColorScheme(
    primary = WhatsAppTealGreen,
    onPrimary = Color.White,
    primaryContainer = WhatsAppBubbleOutgoingLight,
    onPrimaryContainer = WhatsAppTextPrimaryLight,
    secondary = WhatsAppVibrantGreen,
    onSecondary = Color.White,
    tertiary = WhatsAppBlueTick,
    background = WhatsAppBackgroundLight,
    onBackground = WhatsAppTextPrimaryLight,
    surface = WhatsAppSurfaceLight,
    onSurface = WhatsAppTextPrimaryLight,
    surfaceVariant = WhatsAppElevatedLight,
    onSurfaceVariant = WhatsAppTextSecondaryLight,
    outline = WhatsAppBorderLight,
    outlineVariant = Color(0xFFD1D7DB),
    error = EmergencyRed,
)

object WhatsAppTokens {
    fun topBarColor(darkTheme: Boolean): Color =
        if (darkTheme) WhatsAppElevatedDark else WhatsAppTealGreen

    fun topBarContentColor(darkTheme: Boolean): Color =
        if (darkTheme) WhatsAppTextPrimaryDark else Color.White

    fun outgoingBubbleColor(darkTheme: Boolean): Color =
        if (darkTheme) WhatsAppBubbleOutgoingDark else WhatsAppBubbleOutgoingLight

    fun incomingBubbleColor(darkTheme: Boolean): Color =
        if (darkTheme) WhatsAppBubbleIncomingDark else WhatsAppBubbleIncomingLight

    fun securityCardBackground(darkTheme: Boolean): Color =
        if (darkTheme) Color(0xFF182229) else WhatsAppSecurityGold

    fun securityCardTextColor(darkTheme: Boolean): Color =
        if (darkTheme) Color(0xFFFFD279) else WhatsAppSecurityText
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
