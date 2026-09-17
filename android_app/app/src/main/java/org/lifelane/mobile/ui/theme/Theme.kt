package org.lifelane.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import org.lifelane.mobile.ThemeMode

private val LightScheme = lightColorScheme(
    primary = Color(0xFFF97316), onPrimary = Color.White,
    primaryContainer = Color(0xFFFFF1E8), onPrimaryContainer = Color(0xFFEA580C),
    secondary = Color(0xFF0F9D8A), onSecondary = Color.White,
    secondaryContainer = Color(0xFFCCFBF1), onSecondaryContainer = Color(0xFF115E59),
    background = Color(0xFFF8FAFC), onBackground = Color(0xFF172033),
    surface = Color.White, onSurface = Color(0xFF172033),
    surfaceVariant = Color(0xFFF1F5F9), onSurfaceVariant = Color(0xFF64748B),
    outline = Color(0xFFE7EAF0), outlineVariant = Color(0xFFCBD5E1),
    error = Color(0xFFDC2626), onError = Color.White,
    errorContainer = Color(0xFFFEE2E2), onErrorContainer = Color(0xFF991B1B),
)

object LifeLaneTokens {
    @Composable fun selectedSurface(): Color = MaterialTheme.colorScheme.primaryContainer
    @Composable fun trustSurface(): Color = MaterialTheme.colorScheme.secondaryContainer
    @Composable fun trustText(): Color = MaterialTheme.colorScheme.onSecondaryContainer
}

object WhatsAppTokens {
    fun topBarColor(darkTheme: Boolean) = if (darkTheme) DarkSurface else Color.White
    fun topBarContentColor(darkTheme: Boolean) = if (darkTheme) DarkTextPrimary else TextPrimary
    fun outgoingBubbleColor(darkTheme: Boolean) = if (darkTheme) Color(0xFF173A66) else Color(0xFFFFF1E8)
    fun incomingBubbleColor(darkTheme: Boolean) = if (darkTheme) DarkSurface else Color.White
    fun securityCardBackground(darkTheme: Boolean) = if (darkTheme) Color(0xFF134E4A) else Color(0xFFECFDF5)
    fun securityCardTextColor(darkTheme: Boolean) = if (darkTheme) Color(0xFFCCFBF1) else Color(0xFF115E59)
}

@Composable
fun LifeLaneTheme(themeMode: ThemeMode, content: @Composable () -> Unit) {
    LifeLaneTheme(darkTheme = false, content = content)
}

@Composable
fun LifeLaneTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightScheme,
        typography = LifeLaneTypography,
        shapes = LifeLaneShapes,
        content = content,
    )
}
