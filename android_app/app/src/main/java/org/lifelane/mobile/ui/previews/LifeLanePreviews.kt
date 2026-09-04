package org.lifelane.mobile.ui.previews

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import org.lifelane.mobile.ui.components.ConnectionBadge
import org.lifelane.mobile.ui.components.EmergencyStatusCard
import org.lifelane.mobile.ui.components.LifeLaneBrand
import org.lifelane.mobile.ui.components.LiveMetricCard
import org.lifelane.mobile.ui.components.PrimaryActionButton
import org.lifelane.mobile.ui.components.WarningBanner
import org.lifelane.mobile.ui.theme.LifeLaneTheme

private val previewStages = listOf(
    "GPS ACTIVE", "JUNCTION DETECTED", "REQUEST SENT",
    "REQUEST VALIDATED", "PRIORITY GRANTED", "JUNCTION CLEARED",
)

@Composable
private fun ActiveRoutePreview(darkTheme: Boolean, landscape: Boolean = false) {
    LifeLaneTheme(darkTheme = darkTheme) {
        Surface(Modifier.fillMaxSize()) {
            if (landscape) {
                Row(Modifier.fillMaxSize().padding(20.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    PreviewSummary(Modifier.weight(1f))
                    EmergencyStatusCard(previewStages, 3, Modifier.weight(1f))
                }
            } else {
                Column(
                    Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    PreviewSummary()
                    EmergencyStatusCard(previewStages, 3)
                    PrimaryActionButton("View live GPS and connection", {})
                }
            }
        }
    }
}

@Composable
private fun PreviewSummary(modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        LifeLaneBrand()
        WarningBanner("SIMULATED PREVIEW", "Developer preview data is not a live ambulance or signal confirmation.")
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ConnectionBadge("GPS", "Live", Modifier.weight(1f))
            ConnectionBadge("MQTT", "Connected", Modifier.weight(1f))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            LiveMetricCard("Distance", "186 m", Modifier.weight(1f), "Demo junction")
            LiveMetricCard("ETA", "00:16", Modifier.weight(1f), "Live estimate")
        }
    }
}

@Preview(name = "Active route — dark portrait", widthDp = 412, heightDp = 915, uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun DarkPortraitPreview() = ActiveRoutePreview(darkTheme = true)

@Preview(name = "Active route — light portrait", widthDp = 412, heightDp = 915, uiMode = Configuration.UI_MODE_NIGHT_NO, showBackground = true)
@Composable
private fun LightPortraitPreview() = ActiveRoutePreview(darkTheme = false)

@Preview(name = "Active route — landscape", widthDp = 915, heightDp = 412, uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun LandscapePreview() = ActiveRoutePreview(darkTheme = true, landscape = true)

@Preview(name = "Active route — 150% font", widthDp = 412, heightDp = 915, fontScale = 1.5f, uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun LargeFontPreview() = ActiveRoutePreview(darkTheme = true)
