package org.lifelane.mobile.ui.components

import android.annotation.SuppressLint
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Fullscreen
import androidx.compose.material.icons.outlined.FullscreenExit
import androidx.compose.material.icons.outlined.Layers
import androidx.compose.material.icons.outlined.MyLocation
import androidx.compose.material.icons.outlined.Remove
import androidx.compose.material.icons.outlined.ZoomOutMap
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import org.json.JSONObject
import org.lifelane.mobile.ui.theme.ActiveGreen
import org.lifelane.mobile.ui.theme.EmergencyRed
import org.lifelane.mobile.ui.theme.WhatsAppShapes
import org.lifelane.mobile.ui.theme.WhatsAppVibrantGreen

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun RealTimeMapView(
    ambulanceLat: Double?,
    ambulanceLon: Double?,
    headingDegrees: Float,
    speedMps: Float,
    accuracyMetres: Float?,
    ambulanceId: String,
    destinationHospital: String,
    destinationLat: Double?,
    destinationLon: Double?,
    junctionLat: Double?,
    junctionLon: Double?,
    signalStatus: String,
    detectedApproach: String,
    distanceMetres: Double?,
    isEmergencyActive: Boolean,
    darkTheme: Boolean,
    modifier: Modifier = Modifier,
    isExpandedView: Boolean = false,
    onToggleExpand: (() -> Unit)? = null,
    onSwitchToTactical: (() -> Unit)? = null,
) {
    var webViewRef by remember { mutableStateOf<WebView?>(null) }
    var isMapLoaded by remember { mutableStateOf(false) }
    var followVehicle by remember { mutableStateOf(true) }

    val effectiveLat = ambulanceLat ?: 9.451500
    val effectiveLon = ambulanceLon ?: 77.553500

    // Send real-time updates to Leaflet JS whenever coordinates, heading, or speed change
    LaunchedEffect(
        ambulanceLat,
        ambulanceLon,
        headingDegrees,
        speedMps,
        accuracyMetres,
        isEmergencyActive,
        isMapLoaded,
    ) {
        if (!isMapLoaded) return@LaunchedEffect
        val webView = webViewRef ?: return@LaunchedEffect
        val lat = ambulanceLat ?: return@LaunchedEffect
        val lon = ambulanceLon ?: return@LaunchedEffect
        val acc = accuracyMetres ?: 10f
        val script = """
            if (window.updateAmbulance) {
                window.updateAmbulance($lat, $lon, $headingDegrees, $speedMps, $acc, $isEmergencyActive, $followVehicle);
            }
        """.trimIndent()
        webView.evaluateJavascript(script, null)
    }

    // Send destination updates
    LaunchedEffect(destinationLat, destinationLon, destinationHospital, isMapLoaded) {
        if (!isMapLoaded) return@LaunchedEffect
        val webView = webViewRef ?: return@LaunchedEffect
        if (destinationLat != null && destinationLon != null) {
            val safeName = JSONObject.quote(destinationHospital)
            val script = "if (window.updateDestination) { window.updateDestination($destinationLat, $destinationLon, $safeName); }"
            webView.evaluateJavascript(script, null)
        }
    }

    // Send theme change
    LaunchedEffect(darkTheme, isMapLoaded) {
        if (!isMapLoaded) return@LaunchedEffect
        val webView = webViewRef ?: return@LaunchedEffect
        val script = "if (window.setTheme) { window.setTheme($darkTheme); }"
        webView.evaluateJavascript(script, null)
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .then(if (isExpandedView) Modifier.fillMaxSize() else Modifier.height(340.dp)),
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = if (darkTheme) Color(0xFF101921) else Color(0xFFE8ECEF)),
        border = BorderStroke(1.dp, if (darkTheme) Color(0xFF233544) else Color(0xFFCBD5E1)),
    ) {
        Box(Modifier.fillMaxSize()) {
            AndroidView(
                factory = { context ->
                    WebView(context).apply {
                        layoutParams = ViewGroup.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT,
                        )
                        settings.apply {
                            javaScriptEnabled = true
                            domStorageEnabled = true
                            cacheMode = WebSettings.LOAD_DEFAULT
                            loadWithOverviewMode = true
                            useWideViewPort = true
                            setSupportZoom(true)
                            builtInZoomControls = false
                            displayZoomControls = false
                        }
                        webChromeClient = WebChromeClient()
                        webViewClient = object : WebViewClient() {
                            override fun onPageFinished(view: WebView?, url: String?) {
                                super.onPageFinished(view, url)
                                isMapLoaded = true
                                // Initial sync after load
                                val initScript = """
                                    if (window.initMapData) {
                                        window.initMapData(
                                            $effectiveLat,
                                            $effectiveLon,
                                            ${destinationLat ?: "null"},
                                            ${destinationLon ?: "null"},
                                            ${JSONObject.quote(destinationHospital)},
                                            ${junctionLat ?: "null"},
                                            ${junctionLon ?: "null"},
                                            $darkTheme,
                                            $headingDegrees,
                                            $speedMps,
                                            $isEmergencyActive
                                        );
                                    }
                                """.trimIndent()
                                view?.evaluateJavascript(initScript, null)
                            }
                        }
                        loadDataWithBaseURL(
                            "https://lifelane.map.local/",
                            generateLeafletHtml(
                                startLat = effectiveLat,
                                startLon = effectiveLon,
                                destLat = destinationLat,
                                destLon = destinationLon,
                                destName = destinationHospital,
                                junctionLat = junctionLat,
                                junctionLon = junctionLon,
                                ambulanceId = ambulanceId,
                                isDark = darkTheme,
                            ),
                            "text/html",
                            "UTF-8",
                            null,
                        )
                        webViewRef = this
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )

            // Top Floating HUD
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
                // Toggle Tactical Radar vs Real Map
                if (onSwitchToTactical != null) {
                    MapControlButton(
                        icon = Icons.Outlined.Layers,
                        contentDescription = "Switch to Tactical Radar",
                        darkTheme = darkTheme,
                        onClick = onSwitchToTactical,
                    )
                }

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
                    contentDescription = "Center on My Location",
                    highlight = followVehicle,
                    darkTheme = darkTheme,
                    onClick = {
                        followVehicle = true
                        webViewRef?.evaluateJavascript("if (window.recenterAmbulance) window.recenterAmbulance();", null)
                    },
                )

                MapControlButton(
                    icon = Icons.Outlined.ZoomOutMap,
                    contentDescription = "Fit Entire Route",
                    darkTheme = darkTheme,
                    onClick = {
                        followVehicle = false
                        webViewRef?.evaluateJavascript("if (window.fitRoute) window.fitRoute();", null)
                    },
                )

                MapControlButton(
                    icon = Icons.Outlined.Add,
                    contentDescription = "Zoom In",
                    darkTheme = darkTheme,
                    onClick = {
                        webViewRef?.evaluateJavascript("if (window.map) window.map.zoomIn();", null)
                    },
                )

                MapControlButton(
                    icon = Icons.Outlined.Remove,
                    contentDescription = "Zoom Out",
                    darkTheme = darkTheme,
                    onClick = {
                        webViewRef?.evaluateJavascript("if (window.map) window.map.zoomOut();", null)
                    },
                )
            }

            // Bottom-Left Live Telemetry HUD Tag
            Surface(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 12.dp, bottom = 12.dp),
                shape = RoundedCornerShape(10.dp),
                color = (if (darkTheme) Color(0xFF0F172A) else Color.White).copy(alpha = 0.92f),
                border = BorderStroke(1.dp, if (darkTheme) Color(0xFF334155) else Color(0xFFCBD5E1)),
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
                        if (isEmergencyActive) "LIVE GPS · REAL MAP" else "GPS STANDBY · REAL MAP",
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

            // Loading overlay until map initializes
            if (!isMapLoaded) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background((if (darkTheme) Color(0xFF101921) else Color(0xFFE8ECEF)).copy(alpha = 0.8f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        CircularProgressIndicator(
                            color = WhatsAppVibrantGreen,
                            modifier = Modifier.size(28.dp),
                            strokeWidth = 3.dp,
                        )
                        Text(
                            "Loading Real-Time Map...",
                            style = MaterialTheme.typography.labelMedium,
                            color = if (darkTheme) Color.White else Color.Black,
                        )
                    }
                }
            }
        }
    }
}

/**
 * Generates an optimized, self-contained HTML page using Leaflet and CartoDB OpenStreetMap tiles.
 */
private fun generateLeafletHtml(
    startLat: Double,
    startLon: Double,
    destLat: Double?,
    destLon: Double?,
    destName: String,
    junctionLat: Double?,
    junctionLon: Double?,
    ambulanceId: String,
    isDark: Boolean,
): String {
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            html, body, #map {
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 0;
                background-color: ${if (isDark) "#101921" else "#E8ECEF"};
                overflow: hidden;
            }
            .leaflet-control-attribution {
                font-size: 8px !important;
                background: rgba(0,0,0,0.3) !important;
                color: #aaa !important;
            }
            .leaflet-control-zoom {
                display: none !important;
            }
            /* Siren Pulse Animation */
            @keyframes pulse-siren {
                0% {
                    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7), 0 0 0 0 rgba(59, 130, 246, 0.7);
                    transform: scale(0.95);
                }
                50% {
                    box-shadow: 0 0 0 16px rgba(239, 68, 68, 0.1), 0 0 0 24px rgba(59, 130, 246, 0);
                    transform: scale(1.05);
                }
                100% {
                    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0), 0 0 0 0 rgba(59, 130, 246, 0);
                    transform: scale(0.95);
                }
            }
            .ambulance-pin-container {
                position: relative;
                width: 44px;
                height: 44px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .ambulance-pin-body {
                width: 38px;
                height: 38px;
                border-radius: 50%;
                background: linear-gradient(135deg, #EF4444, #DC2626);
                border: 2.5px solid #FFFFFF;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 10px rgba(0,0,0,0.35);
                animation: pulse-siren 1.2s infinite ease-in-out;
                transition: transform 0.2s ease-out;
            }
            .ambulance-pin-body.standby {
                background: linear-gradient(135deg, #00A884, #059669);
                animation: none;
            }
            .heading-arrow {
                position: absolute;
                top: -8px;
                width: 0;
                height: 0;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-bottom: 10px solid #FFFFFF;
                filter: drop-shadow(0 1px 2px rgba(0,0,0,0.5));
            }
            .hospital-pin {
                width: 36px;
                height: 36px;
                border-radius: 8px;
                background: #FFFFFF;
                border: 2.5px solid #EF4444;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
            }
            .junction-pin {
                width: 28px;
                height: 28px;
                border-radius: 50%;
                background: #F59E0B;
                border: 2px solid #FFFFFF;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            }
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = null;
            var tileLayer = null;
            var ambulanceMarker = null;
            var accuracyCircle = null;
            var destinationMarker = null;
            var junctionMarker = null;
            var preemptionCircle = null;
            var routePolyline = null;
            var currentHeading = 0;
            var isDarkMode = ${isDark};

            var lightTileUrl = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
            var darkTileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

            function getTileUrl(dark) {
                return dark ? darkTileUrl : lightTileUrl;
            }

            function initMapData(ambLat, ambLon, destLat, destLon, destName, jLat, jLon, dark, heading, speed, emergency) {
                isDarkMode = dark;
                map = L.map('map', {
                    center: [ambLat, ambLon],
                    zoom: 16,
                    zoomControl: false,
                    attributionControl: false
                });

                tileLayer = L.tileLayer(getTileUrl(dark), {
                    maxZoom: 19,
                    subdomains: 'abcd'
                }).addTo(map);

                // Ambulance marker
                var ambIcon = createAmbulanceIcon(heading, emergency);
                ambulanceMarker = L.marker([ambLat, ambLon], { icon: ambIcon, zIndexOffset: 1000 }).addTo(map);

                // Accuracy circle
                accuracyCircle = L.circle([ambLat, ambLon], {
                    radius: 12,
                    color: '#3B82F6',
                    fillColor: '#3B82F6',
                    fillOpacity: 0.12,
                    weight: 1.5
                }).addTo(map);

                // Destination marker
                if (destLat && destLon) {
                    var hospIcon = L.divIcon({
                        className: 'custom-hosp-icon',
                        html: '<div class="hospital-pin"><svg width="20" height="20" viewBox="0 0 24 24" fill="#EF4444"><path d="M19 10.5h-5.5V5c0-.55-.45-1-1-1h-1c-.55 0-1 .45-1 1v5.5H5c-.55 0-1 .45-1 1v1c0 .55.45 1 1 1h5.5V19c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-5.5H19c.55 0 1-.45 1-1v-1c0-.55-.45-1-1-1z"/></svg></div>',
                        iconSize: [36, 36],
                        iconAnchor: [18, 18]
                    });
                    destinationMarker = L.marker([destLat, destLon], { icon: hospIcon }).addTo(map);
                    destinationMarker.bindTooltip(destName || 'Hospital Destination', { permanent: true, direction: 'top', offset: [0, -20] });
                }

                // Junction marker & 300m preemption circle
                if (jLat && jLon) {
                    preemptionCircle = L.circle([jLat, jLon], {
                        radius: 300,
                        color: emergency ? '#EF4444' : '#10B981',
                        dashArray: '6, 8',
                        fillColor: emergency ? '#EF4444' : '#10B981',
                        fillOpacity: 0.08,
                        weight: 2
                    }).addTo(map);

                    var juncIcon = L.divIcon({
                        className: 'custom-junc-icon',
                        html: '<div class="junction-pin"><svg width="16" height="16" viewBox="0 0 24 24" fill="#FFFFFF"><circle cx="12" cy="12" r="5"/></svg></div>',
                        iconSize: [28, 28],
                        iconAnchor: [14, 14]
                    });
                    junctionMarker = L.marker([jLat, jLon], { icon: juncIcon }).addTo(map);
                    junctionMarker.bindTooltip('Preemption Junction', { direction: 'bottom', offset: [0, 16] });
                }

                // Draw route line connecting points
                updateRouteLine(ambLat, ambLon, jLat, jLon, destLat, destLon);
            }

            function createAmbulanceIcon(heading, emergency) {
                var bodyClass = emergency ? 'ambulance-pin-body' : 'ambulance-pin-body standby';
                return L.divIcon({
                    className: 'custom-amb-icon',
                    html: '<div class="ambulance-pin-container" style="transform: rotate(' + heading + 'deg);">' +
                          '  <div class="heading-arrow"></div>' +
                          '  <div class="' + bodyClass + '">' +
                          '    <svg width="22" height="22" viewBox="0 0 24 24" fill="#FFFFFF">' +
                          '      <path d="M19.5 9.5l-2-4H6.5l-2 4H2v8h2.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5h5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5H22v-8h-2.5zM7 18.5c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm10 0c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zM11 14H9v-2h2v-2h2v2h2v2h-2v2h-2v-2zM6 8.5l1.25-2.5h9.5l1.25 2.5H6z"/>' +
                          '    </svg>' +
                          '  </div>' +
                          '</div>',
                    iconSize: [44, 44],
                    iconAnchor: [22, 22]
                });
            }

            function updateAmbulance(lat, lon, heading, speed, accuracy, emergency, follow) {
                if (!map || !ambulanceMarker) return;
                var newPos = [lat, lon];
                ambulanceMarker.setLatLng(newPos);
                ambulanceMarker.setIcon(createAmbulanceIcon(heading, emergency));

                if (accuracyCircle) {
                    accuracyCircle.setLatLng(newPos);
                    accuracyCircle.setRadius(Math.max(8, accuracy));
                }

                if (routePolyline) {
                    var latlngs = routePolyline.getLatLngs();
                    if (latlngs.length > 0) {
                        latlngs[0] = newPos;
                        routePolyline.setLatLngs(latlngs);
                    }
                }

                if (follow) {
                    map.panTo(newPos, { animate: true, duration: 0.8 });
                }
            }

            function updateDestination(lat, lon, name) {
                if (!map) return;
                var hospPos = [lat, lon];
                if (destinationMarker) {
                    destinationMarker.setLatLng(hospPos);
                    destinationMarker.setTooltipContent(name);
                } else {
                    var hospIcon = L.divIcon({
                        className: 'custom-hosp-icon',
                        html: '<div class="hospital-pin"><svg width="20" height="20" viewBox="0 0 24 24" fill="#EF4444"><path d="M19 10.5h-5.5V5c0-.55-.45-1-1-1h-1c-.55 0-1 .45-1 1v5.5H5c-.55 0-1 .45-1 1v1c0 .55.45 1 1 1h5.5V19c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-5.5H19c.55 0 1-.45 1-1v-1c0-.55-.45-1-1-1z"/></svg></div>',
                        iconSize: [36, 36],
                        iconAnchor: [18, 18]
                    });
                    destinationMarker = L.marker(hospPos, { icon: hospIcon }).addTo(map);
                    destinationMarker.bindTooltip(name, { permanent: true, direction: 'top', offset: [0, -20] });
                }
                var ambPos = ambulanceMarker ? ambulanceMarker.getLatLng() : null;
                var jPos = junctionMarker ? junctionMarker.getLatLng() : null;
                updateRouteLine(ambPos ? ambPos.lat : null, ambPos ? ambPos.lng : null, jPos ? jPos.lat : null, jPos ? jPos.lng : null, lat, lon);
            }

            function updateRouteLine(ambLat, ambLon, jLat, jLon, destLat, destLon) {
                if (!map) return;
                var points = [];
                if (ambLat && ambLon) points.push([ambLat, ambLon]);
                if (jLat && jLon) points.push([jLat, jLon]);
                if (destLat && destLon) points.push([destLat, destLon]);

                if (points.length < 2) return;

                if (routePolyline) {
                    routePolyline.setLatLngs(points);
                } else {
                    routePolyline = L.polyline(points, {
                        color: '#00A884',
                        weight: 5,
                        opacity: 0.85,
                        lineCap: 'round',
                        lineJoin: 'round',
                        dashArray: '8, 8'
                    }).addTo(map);
                }
            }

            function recenterAmbulance() {
                if (map && ambulanceMarker) {
                    map.setView(ambulanceMarker.getLatLng(), 17, { animate: true });
                }
            }

            function fitRoute() {
                if (!map) return;
                var group = new L.featureGroup();
                if (ambulanceMarker) group.addLayer(ambulanceMarker);
                if (destinationMarker) group.addLayer(destinationMarker);
                if (junctionMarker) group.addLayer(junctionMarker);
                if (group.getLayers().length > 0) {
                    map.fitBounds(group.getBounds().pad(0.25), { animate: true });
                }
            }

            function setTheme(dark) {
                isDarkMode = dark;
                document.body.style.backgroundColor = dark ? "#101921" : "#E8ECEF";
                if (tileLayer) {
                    tileLayer.setUrl(getTileUrl(dark));
                }
            }
        </script>
    </body>
    </html>
    """.trimIndent()
}
