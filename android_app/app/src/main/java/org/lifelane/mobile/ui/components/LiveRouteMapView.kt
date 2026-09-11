package org.lifelane.mobile.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Fullscreen
import androidx.compose.material.icons.outlined.FullscreenExit
import androidx.compose.material.icons.outlined.Layers
import androidx.compose.material.icons.outlined.LocalHospital
import androidx.compose.material.icons.outlined.MyLocation
import androidx.compose.material.icons.outlined.Navigation
import androidx.compose.material.icons.outlined.Remove
import androidx.compose.material.icons.outlined.Traffic
import androidx.compose.material.icons.outlined.ZoomOutMap
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.cos
import kotlin.math.sin
import org.lifelane.mobile.ui.theme.ActiveGreen
import org.lifelane.mobile.ui.theme.EmergencyRed
import org.lifelane.mobile.ui.theme.InformationBlue
import org.lifelane.mobile.ui.theme.WarningAmber
import org.lifelane.mobile.ui.theme.WhatsAppShapes
import org.lifelane.mobile.ui.theme.WhatsAppVibrantGreen

private const val METRES_PER_LAT_DEGREE = 111_320.0
private const val JUNCTION_LAT = 9.451500
private const val JUNCTION_LON = 77.553500

@Composable
fun LiveRouteMapView(
    ambulanceLat: Double?,
    ambulanceLon: Double?,
    headingDegrees: Float,
    speedMps: Float,
    ambulanceId: String,
    destinationHospital: String,
    destinationLat: Double?,
    destinationLon: Double?,
    signalStatus: String,
    detectedApproach: String,
    distanceMetres: Double?,
    isEmergencyActive: Boolean,
    darkTheme: Boolean,
    modifier: Modifier = Modifier,
    isExpandedView: Boolean = false,
    accuracyMetres: Float? = null,
    onToggleExpand: (() -> Unit)? = null,
) {
    // Toggle between real-world OpenStreetMap tile view and tactical radar HUD
    var showRealMap by remember { mutableStateOf(true) }

    // Dynamic corridor junction estimation based on location
    val dynamicJunctionLat = when {
        ambulanceLat != null && destinationLat != null -> (ambulanceLat + destinationLat) / 2.0
        ambulanceLat != null -> ambulanceLat - 0.003
        else -> JUNCTION_LAT
    }
    val dynamicJunctionLon = when {
        ambulanceLon != null && destinationLon != null -> (ambulanceLon + destinationLon) / 2.0
        ambulanceLon != null -> ambulanceLon
        else -> JUNCTION_LON
    }

    if (showRealMap) {
        RealTimeMapView(
            ambulanceLat = ambulanceLat,
            ambulanceLon = ambulanceLon,
            headingDegrees = headingDegrees,
            speedMps = speedMps,
            accuracyMetres = accuracyMetres,
            ambulanceId = ambulanceId,
            destinationHospital = destinationHospital,
            destinationLat = destinationLat,
            destinationLon = destinationLon,
            junctionLat = dynamicJunctionLat,
            junctionLon = dynamicJunctionLon,
            signalStatus = signalStatus,
            detectedApproach = detectedApproach,
            distanceMetres = distanceMetres,
            isEmergencyActive = isEmergencyActive,
            darkTheme = darkTheme,
            modifier = modifier,
            isExpandedView = isExpandedView,
            onToggleExpand = onToggleExpand,
            onSwitchToTactical = { showRealMap = false },
        )
        return
    }

    // Zoom and pan state for tactical radar canvas
    var zoomLevel by remember { mutableFloatStateOf(1.0f) }
    var panOffset by remember { mutableStateOf(Offset.Zero) }
    var followVehicle by remember { mutableStateOf(true) }

    // Text Measurer for canvas labels
    val textMeasurer = rememberTextMeasurer()

    // Animations
    val infiniteTransition = rememberInfiniteTransition(label = "RadarAndSiren")
    val sirenPulse by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "SirenPulse",
    )
    val radarSweep by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(4000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "RadarSweep",
    )
    val pathFlow by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 24f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "PathFlow",
    )

    // Dynamic longitude scaling based on latitude
    val metresPerLonDegree = METRES_PER_LAT_DEGREE * cos(Math.toRadians(dynamicJunctionLat))

    // Fallback coordinates
    val effectiveAmbLat = ambulanceLat ?: (dynamicJunctionLat + 0.0035)
    val effectiveAmbLon = ambulanceLon ?: dynamicJunctionLon
    val effectiveDestLat = destinationLat ?: (dynamicJunctionLat - 0.0045)
    val effectiveDestLon = destinationLon ?: dynamicJunctionLon

    // Theme Colors
    val mapBgColor = if (darkTheme) Color(0xFF101921) else Color(0xFFE8ECEF)
    val roadColor = if (darkTheme) Color(0xFF1F2C39) else Color(0xFFFFFFFF)
    val roadBorderColor = if (darkTheme) Color(0xFF2C3E50) else Color(0xFFCBD5E1)
    val blockColor = if (darkTheme) Color(0xFF16222D) else Color(0xFFDFE5EB)
    val textColor = if (darkTheme) Color(0xFFE2E8F0) else Color(0xFF1E293B)
    val subtextColor = if (darkTheme) Color(0xFF94A3B8) else Color(0xFF64748B)

    Card(
        modifier = modifier
            .fillMaxWidth()
            .then(if (isExpandedView) Modifier.fillMaxSize() else Modifier.height(340.dp)),
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = mapBgColor),
        border = BorderStroke(1.dp, if (darkTheme) Color(0xFF233544) else Color(0xFFCBD5E1)),
    ) {
        Box(Modifier.fillMaxSize()) {
            // Interactive Map Canvas
            Canvas(
                modifier = Modifier
                    .fillMaxSize()
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            zoomLevel = (zoomLevel * zoom).coerceIn(0.6f, 3.0f)
                            panOffset += pan
                            followVehicle = false
                        }
                    },
            ) {
                val canvasW = size.width
                val canvasH = size.height
                val pixelsPerMetre = (canvasW / 750f) * zoomLevel

                // Origin reference: Junction is at (0, 0) in metres
                val centerOffset = if (followVehicle) {
                    val ambNorthM = (effectiveAmbLat - dynamicJunctionLat) * METRES_PER_LAT_DEGREE
                    val ambEastM = (effectiveAmbLon - dynamicJunctionLon) * metresPerLonDegree
                    Offset(
                        canvasW / 2f - (ambEastM.toFloat() * pixelsPerMetre) + panOffset.x,
                        canvasH / 2f + (ambNorthM.toFloat() * pixelsPerMetre) + panOffset.y,
                    )
                } else {
                    Offset(canvasW / 2f + panOffset.x, canvasH / 2f + panOffset.y)
                }

                fun toCanvasPos(lat: Double, lon: Double): Offset {
                    val northM = (lat - dynamicJunctionLat) * METRES_PER_LAT_DEGREE
                    val eastM = (lon - dynamicJunctionLon) * metresPerLonDegree
                    return Offset(
                        centerOffset.x + (eastM.toFloat() * pixelsPerMetre),
                        centerOffset.y - (northM.toFloat() * pixelsPerMetre),
                    )
                }

                val junctionPos = toCanvasPos(dynamicJunctionLat, dynamicJunctionLon)
                val ambulancePos = toCanvasPos(effectiveAmbLat, effectiveAmbLon)
                val destPos = toCanvasPos(effectiveDestLat, effectiveDestLon)

                // 1. Draw Surrounding Urban Blocks
                drawUrbanGrid(canvasW, canvasH, centerOffset, pixelsPerMetre, blockColor, darkTheme)

                // 2. Draw 4-Way Road Network
                drawRoadNetwork(canvasW, canvasH, junctionPos, pixelsPerMetre, roadColor, roadBorderColor, darkTheme)

                // 3. Draw Junction Preemption Perimeter & Radar (300m & 120m)
                drawPreemptionPerimeter(junctionPos, pixelsPerMetre, radarSweep, darkTheme)

                // 4. Draw Animated Route Polyline (Ambulance -> Junction -> Destination)
                drawRoutePolyline(
                    ambulancePos = ambulancePos,
                    junctionPos = junctionPos,
                    destPos = destPos,
                    pathFlow = pathFlow,
                    darkTheme = darkTheme,
                )

                // 5. Draw Junction Signal Head Lights
                drawJunctionTrafficLights(junctionPos, pixelsPerMetre, signalStatus, textMeasurer, textColor, darkTheme)

                // 6. Draw Destination Hospital Marker
                drawHospitalMarker(destPos, destinationHospital, textMeasurer, darkTheme)

                // 7. Draw Live Ambulance Marker with Rotating Direction & Flashing Siren
                drawAmbulanceMarker(
                    pos = ambulancePos,
                    heading = headingDegrees,
                    speedMps = speedMps,
                    ambulanceId = ambulanceId,
                    sirenPulse = sirenPulse,
                    isEmergencyActive = isEmergencyActive,
                    textMeasurer = textMeasurer,
                    darkTheme = darkTheme,
                )
            }

            // Floating Navigation Top Bar
            FloatingNavigationCard(
                destination = destinationHospital,
                distanceMetres = distanceMetres,
                speedMps = speedMps,
                signalStatus = signalStatus,
                detectedApproach = detectedApproach,
                isEmergencyActive = isEmergencyActive,
                darkTheme = darkTheme,
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .fillMaxWidth()
                    .padding(10.dp),
            )

            // Floating Map Controls (Right side)
            Column(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(end = 12.dp, bottom = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                MapControlButton(
                    icon = Icons.Outlined.Layers,
                    contentDescription = "Switch to Real Street Map",
                    darkTheme = darkTheme,
                    onClick = { showRealMap = true },
                )
                if (onToggleExpand != null) {
                    MapControlButton(
                        icon = if (isExpandedView) Icons.Outlined.FullscreenExit else Icons.Outlined.Fullscreen,
                        contentDescription = "Toggle Fullscreen Map",
                        darkTheme = darkTheme,
                        onClick = onToggleExpand,
                    )
                }
                MapControlButton(
                    icon = Icons.Outlined.MyLocation,
                    contentDescription = "Center on Ambulance",
                    highlight = followVehicle,
                    darkTheme = darkTheme,
                    onClick = {
                        followVehicle = true
                        panOffset = Offset.Zero
                        zoomLevel = 1.0f
                    },
                )
                MapControlButton(
                    icon = Icons.Outlined.ZoomOutMap,
                    contentDescription = "View Entire Route",
                    darkTheme = darkTheme,
                    onClick = {
                        followVehicle = false
                        panOffset = Offset.Zero
                        zoomLevel = 0.8f
                    },
                )
                MapControlButton(
                    icon = Icons.Outlined.Add,
                    contentDescription = "Zoom In",
                    darkTheme = darkTheme,
                    onClick = { zoomLevel = (zoomLevel * 1.25f).coerceAtMost(3.0f) },
                )
                MapControlButton(
                    icon = Icons.Outlined.Remove,
                    contentDescription = "Zoom Out",
                    darkTheme = darkTheme,
                    onClick = { zoomLevel = (zoomLevel / 1.25f).coerceAtLeast(0.6f) },
                )
            }

            // Bottom-Left Live Telemetry HUD Tag
            Surface(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 12.dp, bottom = 12.dp),
                shape = RoundedCornerShape(10.dp),
                color = (if (darkTheme) Color(0xFF0F172A) else Color.White).copy(alpha = 0.92f),
                border = BorderStroke(1.dp, (if (darkTheme) Color(0xFF334155) else Color(0xFFCBD5E1))),
                shadowElevation = 4.dp,
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Box(
                        Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(if (isEmergencyActive) EmergencyRed else ActiveGreen),
                    )
                    Text(
                        if (isEmergencyActive) "PREEMPTION LIVE" else "DISPATCH TRACKING",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = if (isEmergencyActive) EmergencyRed else WhatsAppVibrantGreen,
                    )
                    Text(
                        "· %.1f km/h".format(speedMps * 3.6f),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = if (darkTheme) Color.White else Color(0xFF0F172A),
                    )
                }
            }
        }
    }
}

// -------------------------------------------------------------
// Canvas Drawing Helper Functions
// -------------------------------------------------------------

private fun DrawScope.drawUrbanGrid(
    width: Float,
    height: Float,
    centerOffset: Offset,
    ppm: Float,
    blockColor: Color,
    darkTheme: Boolean,
) {
    val gridSize = 100f * ppm
    var x = centerOffset.x % gridSize - gridSize
    while (x < width + gridSize) {
        var y = centerOffset.y % gridSize - gridSize
        while (y < height + gridSize) {
            drawRoundRect(
                color = blockColor,
                topLeft = Offset(x + 12f, y + 12f),
                size = Size(gridSize - 24f, gridSize - 24f),
                cornerRadius = CornerRadius(8f, 8f),
            )
            y += gridSize
        }
        x += gridSize
    }
}

private fun DrawScope.drawRoadNetwork(
    width: Float,
    height: Float,
    junctionPos: Offset,
    ppm: Float,
    roadColor: Color,
    borderColor: Color,
    darkTheme: Boolean,
) {
    val roadWidth = 54f * ppm // 54 metres wide road

    // North-South Arterial
    drawRect(
        color = roadColor,
        topLeft = Offset(junctionPos.x - roadWidth / 2, 0f),
        size = Size(roadWidth, height),
    )
    drawLine(
        color = borderColor,
        start = Offset(junctionPos.x - roadWidth / 2, 0f),
        end = Offset(junctionPos.x - roadWidth / 2, height),
        strokeWidth = 2f,
    )
    drawLine(
        color = borderColor,
        start = Offset(junctionPos.x + roadWidth / 2, 0f),
        end = Offset(junctionPos.x + roadWidth / 2, height),
        strokeWidth = 2f,
    )

    // East-West Crossroad
    drawRect(
        color = roadColor,
        topLeft = Offset(0f, junctionPos.y - roadWidth / 2),
        size = Size(width, roadWidth),
    )
    drawLine(
        color = borderColor,
        start = Offset(0f, junctionPos.y - roadWidth / 2),
        end = Offset(width, junctionPos.y - roadWidth / 2),
        strokeWidth = 2f,
    )
    drawLine(
        color = borderColor,
        start = Offset(0f, junctionPos.y + roadWidth / 2),
        end = Offset(width, junctionPos.y + roadWidth / 2),
        strokeWidth = 2f,
    )

    // Yellow Dashed Lane Dividers
    val laneDashEffect = PathEffect.dashPathEffect(floatArrayOf(16f, 16f), 0f)
    val dividerColor = if (darkTheme) Color(0xFFF59E0B).copy(alpha = 0.7f) else Color(0xFFEAB308)

    // NS Divider
    drawLine(
        color = dividerColor,
        start = Offset(junctionPos.x, 0f),
        end = Offset(junctionPos.x, junctionPos.y - roadWidth / 2),
        strokeWidth = 2.5f,
        pathEffect = laneDashEffect,
    )
    drawLine(
        color = dividerColor,
        start = Offset(junctionPos.x, junctionPos.y + roadWidth / 2),
        end = Offset(junctionPos.x, height),
        strokeWidth = 2.5f,
        pathEffect = laneDashEffect,
    )

    // EW Divider
    drawLine(
        color = dividerColor,
        start = Offset(0f, junctionPos.y),
        end = Offset(junctionPos.x - roadWidth / 2, junctionPos.y),
        strokeWidth = 2.5f,
        pathEffect = laneDashEffect,
    )
    drawLine(
        color = dividerColor,
        start = Offset(junctionPos.x + roadWidth / 2, junctionPos.y),
        end = Offset(width, junctionPos.y),
        strokeWidth = 2.5f,
        pathEffect = laneDashEffect,
    )

    // Zebra Crossings at approaches
    val zebraColor = if (darkTheme) Color(0xFFFFFFFF).copy(alpha = 0.45f) else Color(0xFF94A3B8)
    val zebraLen = roadWidth - 10f
    for (i in -3..3) {
        val offset = i * 6f
        // North Crosswalk
        drawLine(
            color = zebraColor,
            start = Offset(junctionPos.x - zebraLen / 2, junctionPos.y - roadWidth / 2 - 12f + offset),
            end = Offset(junctionPos.x + zebraLen / 2, junctionPos.y - roadWidth / 2 - 12f + offset),
            strokeWidth = 3f,
        )
        // South Crosswalk
        drawLine(
            color = zebraColor,
            start = Offset(junctionPos.x - zebraLen / 2, junctionPos.y + roadWidth / 2 + 12f + offset),
            end = Offset(junctionPos.x + zebraLen / 2, junctionPos.y + roadWidth / 2 + 12f + offset),
            strokeWidth = 3f,
        )
    }
}

private fun DrawScope.drawPreemptionPerimeter(
    junctionPos: Offset,
    ppm: Float,
    radarSweep: Float,
    darkTheme: Boolean,
) {
    val radius300m = 300f * ppm
    val radius120m = 120f * ppm

    // 300m Activation Zone
    drawCircle(
        color = WhatsAppVibrantGreen.copy(alpha = 0.05f),
        radius = radius300m,
        center = junctionPos,
    )
    drawCircle(
        color = WhatsAppVibrantGreen.copy(alpha = 0.45f),
        radius = radius300m,
        center = junctionPos,
        style = Stroke(width = 1.5f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 8f), 0f)),
    )

    // 120m Immediate Priority Zone
    drawCircle(
        color = WarningAmber.copy(alpha = 0.08f),
        radius = radius120m,
        center = junctionPos,
    )
    drawCircle(
        color = WarningAmber.copy(alpha = 0.6f),
        radius = radius120m,
        center = junctionPos,
        style = Stroke(width = 2f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 6f), 0f)),
    )

    // Rotating Radar Sweep line
    rotate(radarSweep, pivot = junctionPos) {
        val sweepEnd = Offset(
            junctionPos.x + radius300m * cos(0.0).toFloat(),
            junctionPos.y + radius300m * sin(0.0).toFloat(),
        )
        drawLine(
            brush = Brush.linearGradient(
                colors = listOf(WhatsAppVibrantGreen.copy(alpha = 0.7f), WhatsAppVibrantGreen.copy(alpha = 0.0f)),
                start = junctionPos,
                end = sweepEnd,
            ),
            start = junctionPos,
            end = sweepEnd,
            strokeWidth = 2f,
        )
    }
}

private fun DrawScope.drawRoutePolyline(
    ambulancePos: Offset,
    junctionPos: Offset,
    destPos: Offset,
    pathFlow: Float,
    darkTheme: Boolean,
) {
    val routePath = Path().apply {
        moveTo(ambulancePos.x, ambulancePos.y)
        lineTo(junctionPos.x, junctionPos.y)
        lineTo(destPos.x, destPos.y)
    }

    // Outer Glow / Casing
    drawPath(
        path = routePath,
        color = WhatsAppVibrantGreen.copy(alpha = 0.28f),
        style = Stroke(width = 16f, cap = StrokeCap.Round, join = StrokeJoin.Round),
    )

    // Solid Route Body
    drawPath(
        path = routePath,
        color = WhatsAppVibrantGreen,
        style = Stroke(width = 7f, cap = StrokeCap.Round, join = StrokeJoin.Round),
    )

    // Animated Traveling Chevrons / Dashes
    val dashEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 12f), pathFlow)
    drawPath(
        path = routePath,
        color = Color.White,
        style = Stroke(width = 3.5f, cap = StrokeCap.Round, join = StrokeJoin.Round, pathEffect = dashEffect),
    )
}

private fun DrawScope.drawJunctionTrafficLights(
    junctionPos: Offset,
    ppm: Float,
    signalStatus: String,
    textMeasurer: TextMeasurer,
    textColor: Color,
    darkTheme: Boolean,
) {
    val junctionBoxSize = 38f
    drawRoundRect(
        color = if (darkTheme) Color(0xFF0F172A) else Color(0xFF1E293B),
        topLeft = Offset(junctionPos.x - junctionBoxSize / 2, junctionPos.y - junctionBoxSize / 2),
        size = Size(junctionBoxSize, junctionBoxSize),
        cornerRadius = CornerRadius(6f, 6f),
        style = Fill,
    )
    drawRoundRect(
        color = WhatsAppVibrantGreen,
        topLeft = Offset(junctionPos.x - junctionBoxSize / 2, junctionPos.y - junctionBoxSize / 2),
        size = Size(junctionBoxSize, junctionBoxSize),
        cornerRadius = CornerRadius(6f, 6f),
        style = Stroke(width = 2f),
    )

    // Center traffic light icon
    val isNsGreen = signalStatus.contains("NS:GREEN", true) || signalStatus.contains("NORTH:GREEN", true) || signalStatus.contains("SOUTH:GREEN", true)
    val isEwGreen = signalStatus.contains("EW:GREEN", true) || signalStatus.contains("EAST:GREEN", true) || signalStatus.contains("WEST:GREEN", true)

    // 4 Signal lamps (North, South, East, West)
    val lampRadius = 4.5f
    val d = 12f
    // North Light
    drawCircle(color = if (isNsGreen) ActiveGreen else EmergencyRed, radius = lampRadius, center = Offset(junctionPos.x, junctionPos.y - d))
    // South Light
    drawCircle(color = if (isNsGreen) ActiveGreen else EmergencyRed, radius = lampRadius, center = Offset(junctionPos.x, junctionPos.y + d))
    // East Light
    drawCircle(color = if (isEwGreen) ActiveGreen else EmergencyRed, radius = lampRadius, center = Offset(junctionPos.x + d, junctionPos.y))
    // West Light
    drawCircle(color = if (isEwGreen) ActiveGreen else EmergencyRed, radius = lampRadius, center = Offset(junctionPos.x - d, junctionPos.y))

    // Label
    val result = textMeasurer.measure("LifeLane Hub", TextStyle(color = textColor, fontSize = 10.sp, fontWeight = FontWeight.Bold))
    drawText(
        textMeasurer = textMeasurer,
        text = "LifeLane Hub",
        topLeft = Offset(junctionPos.x - result.size.width / 2, junctionPos.y + junctionBoxSize / 2 + 4f),
        style = TextStyle(color = textColor, fontSize = 10.sp, fontWeight = FontWeight.Bold),
    )
}

private fun DrawScope.drawHospitalMarker(
    destPos: Offset,
    hospitalName: String,
    textMeasurer: TextMeasurer,
    darkTheme: Boolean,
) {
    val pinRadius = 16f

    // Outer Glow Ring
    drawCircle(
        color = EmergencyRed.copy(alpha = 0.22f),
        radius = pinRadius + 8f,
        center = destPos,
    )

    // Destination Pin Base
    drawCircle(
        color = EmergencyRed,
        radius = pinRadius,
        center = destPos,
    )
    drawCircle(
        color = Color.White,
        radius = pinRadius,
        center = destPos,
        style = Stroke(width = 2.5f),
    )

    // White Cross in Pin
    val crossLen = 8f
    val crossThick = 3.5f
    drawRect(
        color = Color.White,
        topLeft = Offset(destPos.x - crossThick / 2, destPos.y - crossLen),
        size = Size(crossThick, crossLen * 2),
    )
    drawRect(
        color = Color.White,
        topLeft = Offset(destPos.x - crossLen, destPos.y - crossThick / 2),
        size = Size(crossLen * 2, crossThick),
    )

    // Label Badge
    val labelText = if (hospitalName.length > 20) hospitalName.take(18) + "..." else hospitalName
    val measured = textMeasurer.measure(labelText, TextStyle(color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold))
    val badgeW = measured.size.width + 16f
    val badgeH = 20f
    val badgeTopLeft = Offset(destPos.x - badgeW / 2, destPos.y + pinRadius + 6f)

    drawRoundRect(
        color = Color(0xFFDC2626),
        topLeft = badgeTopLeft,
        size = Size(badgeW, badgeH),
        cornerRadius = CornerRadius(5f, 5f),
    )
    drawText(
        textMeasurer = textMeasurer,
        text = labelText,
        topLeft = Offset(badgeTopLeft.x + 8f, badgeTopLeft.y + 2f),
        style = TextStyle(color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold),
    )
}

private fun DrawScope.drawAmbulanceMarker(
    pos: Offset,
    heading: Float,
    speedMps: Float,
    ambulanceId: String,
    sirenPulse: Float,
    isEmergencyActive: Boolean,
    textMeasurer: TextMeasurer,
    darkTheme: Boolean,
) {
    if (isEmergencyActive) {
        // Red & Blue Siren Waves
        val maxWaveRadius = 55f
        drawCircle(
            color = EmergencyRed.copy(alpha = (1f - sirenPulse) * 0.5f),
            radius = sirenPulse * maxWaveRadius,
            center = pos,
            style = Stroke(width = 3f),
        )
        drawCircle(
            color = InformationBlue.copy(alpha = (1f - sirenPulse) * 0.4f),
            radius = (sirenPulse * maxWaveRadius * 0.7f),
            center = pos,
            style = Stroke(width = 2.5f),
        )
    }

    // Vehicle Body (Rotated according to headingDegrees)
    rotate(heading, pivot = pos) {
        // Headlight Beams
        val beamPath = Path().apply {
            moveTo(pos.x - 7f, pos.y - 12f)
            lineTo(pos.x - 22f, pos.y - 48f)
            lineTo(pos.x + 22f, pos.y - 48f)
            lineTo(pos.x + 7f, pos.y - 12f)
            close()
        }
        drawPath(
            path = beamPath,
            brush = Brush.verticalGradient(
                colors = listOf(Color(0xFFFEF08A).copy(alpha = 0.45f), Color(0xFFFEF08A).copy(alpha = 0.0f)),
                startY = pos.y - 12f,
                endY = pos.y - 48f,
            ),
        )

        // Vehicle Chassis
        val vehicleW = 18f
        val vehicleH = 34f
        drawRoundRect(
            color = Color.White,
            topLeft = Offset(pos.x - vehicleW / 2, pos.y - vehicleH / 2),
            size = Size(vehicleW, vehicleH),
            cornerRadius = CornerRadius(5f, 5f),
        )
        drawRoundRect(
            color = EmergencyRed,
            topLeft = Offset(pos.x - vehicleW / 2, pos.y - vehicleH / 2),
            size = Size(vehicleW, vehicleH),
            cornerRadius = CornerRadius(5f, 5f),
            style = Stroke(width = 2.5f),
        )

        // Windshield
        drawRoundRect(
            color = Color(0xFF0284C7),
            topLeft = Offset(pos.x - vehicleW / 2 + 2.5f, pos.y - vehicleH / 2 + 5f),
            size = Size(vehicleW - 5f, 7f),
            cornerRadius = CornerRadius(2f, 2f),
        )

        // Roof Siren Light Bar
        drawCircle(
            color = if (sirenPulse < 0.5f) EmergencyRed else InformationBlue,
            radius = 3.5f,
            center = Offset(pos.x, pos.y),
        )
    }

    // Vehicle Label Callout
    val idLabel = ambulanceId.ifBlank { "AMB" }
    val measured = textMeasurer.measure(idLabel, TextStyle(color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold))
    val badgeW = measured.size.width + 12f
    val badgeH = 18f
    val badgeTopLeft = Offset(pos.x - badgeW / 2, pos.y + 20f)

    drawRoundRect(
        color = Color(0xFF0F172A),
        topLeft = badgeTopLeft,
        size = Size(badgeW, badgeH),
        cornerRadius = CornerRadius(4f, 4f),
    )
    drawRoundRect(
        color = WhatsAppVibrantGreen,
        topLeft = badgeTopLeft,
        size = Size(badgeW, badgeH),
        cornerRadius = CornerRadius(4f, 4f),
        style = Stroke(width = 1.5f),
    )
    drawText(
        textMeasurer = textMeasurer,
        text = idLabel,
        topLeft = Offset(badgeTopLeft.x + 6f, badgeTopLeft.y + 2f),
        style = TextStyle(color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold),
    )
}

// -------------------------------------------------------------
// Floating Navigation HUD & Controls
// -------------------------------------------------------------

@Composable
internal fun FloatingNavigationCard(
    destination: String,
    distanceMetres: Double?,
    speedMps: Float,
    signalStatus: String,
    detectedApproach: String,
    isEmergencyActive: Boolean,
    darkTheme: Boolean,
    modifier: Modifier = Modifier,
) {
    val cardBg = (if (darkTheme) Color(0xFF0F172A) else Color.White).copy(alpha = 0.94f)
    val isGreenPreemption = signalStatus.contains("GREEN", true) && detectedApproach != "Not detected"

    Surface(
        modifier = modifier.shadow(8.dp, RoundedCornerShape(14.dp)),
        shape = RoundedCornerShape(14.dp),
        color = cardBg,
        border = BorderStroke(1.dp, if (darkTheme) Color(0xFF334155) else Color(0xFFE2E8F0)),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Maneuver / Direction Icon
            Box(
                modifier = Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(if (isGreenPreemption) ActiveGreen.copy(alpha = 0.18f) else WhatsAppVibrantGreen.copy(alpha = 0.15f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Outlined.Navigation,
                    contentDescription = null,
                    tint = if (isGreenPreemption) ActiveGreen else WhatsAppVibrantGreen,
                    modifier = Modifier.size(24.dp),
                )
            }

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = if (isGreenPreemption) "Green Wave Active · Cross Junction" else "En Route to ${destination.ifBlank { "Destination" }}",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = if (darkTheme) Color.White else Color(0xFF0F172A),
                    maxLines = 1,
                )
                Text(
                    text = when {
                        distanceMetres != null && distanceMetres <= 300 -> "Preemption Area (${"%.0f m".format(distanceMetres)}) · Approach: $detectedApproach"
                        distanceMetres != null -> "Distance to Junction: ${"%.0f m".format(distanceMetres)}"
                        else -> "Calibrating GPS route trajectory..."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (darkTheme) Color(0xFF94A3B8) else Color(0xFF64748B),
                    maxLines = 1,
                )
            }

            // ETA Tag
            Column(horizontalAlignment = Alignment.End) {
                val etaSec = if (distanceMetres != null && speedMps > 0.8f) (distanceMetres / speedMps).toInt() else 0
                Text(
                    text = if (etaSec > 0) "%d s".format(etaSec) else "—",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = WhatsAppVibrantGreen,
                )
                Text(
                    text = "ETA",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (darkTheme) Color(0xFF94A3B8) else Color(0xFF64748B),
                )
            }
        }
    }
}

@Composable
internal fun MapControlButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    contentDescription: String,
    darkTheme: Boolean,
    highlight: Boolean = false,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .size(38.dp)
            .shadow(4.dp, CircleShape)
            .clickable(onClick = onClick),
        shape = CircleShape,
        color = when {
            highlight -> WhatsAppVibrantGreen
            darkTheme -> Color(0xFF1E293B)
            else -> Color.White
        },
        border = BorderStroke(
            1.dp,
            if (highlight) WhatsAppVibrantGreen else (if (darkTheme) Color(0xFF334155) else Color(0xFFCBD5E1)),
        ),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(
                imageVector = icon,
                contentDescription = contentDescription,
                tint = when {
                    highlight -> Color.White
                    darkTheme -> Color(0xFFE2E8F0)
                    else -> Color(0xFF1E293B)
                },
                modifier = Modifier.size(20.dp),
            )
        }
    }
}
