package org.lifelane.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import com.google.android.gms.location.LocationServices
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.DirectionsCar
import androidx.compose.material.icons.outlined.LocalHospital
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.NearMe
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import java.time.Duration
import java.time.Instant
import kotlinx.coroutines.delay
import org.lifelane.mobile.ui.components.CheckMarkState
import org.lifelane.mobile.ui.components.ConditionChip
import org.lifelane.mobile.ui.components.ConfirmationBottomSheet
import org.lifelane.mobile.ui.components.ConnectionBadge
import org.lifelane.mobile.ui.components.DangerActionButton
import org.lifelane.mobile.ui.components.EmergencyStatusCard
import org.lifelane.mobile.ui.components.EmptyState
import org.lifelane.mobile.ui.components.LifeLaneBrand
import org.lifelane.mobile.ui.components.LifeLaneTopBar
import org.lifelane.mobile.ui.components.LiveLocationRadarBanner
import org.lifelane.mobile.ui.components.LiveMetricCard
import org.lifelane.mobile.ui.components.LiveRouteMapView
import org.lifelane.mobile.ui.components.LoadingState
import org.lifelane.mobile.ui.components.PrimaryActionButton
import org.lifelane.mobile.ui.components.PriorityCard
import org.lifelane.mobile.ui.components.WarningBanner
import org.lifelane.mobile.ui.components.WhatsAppCheckMarks
import org.lifelane.mobile.ui.components.WhatsAppSecurityBanner
import org.lifelane.mobile.ui.theme.ActiveGreen
import org.lifelane.mobile.ui.theme.EmergencyRed
import org.lifelane.mobile.ui.theme.InformationBlue
import org.lifelane.mobile.ui.theme.LifeLaneDimens
import org.lifelane.mobile.ui.theme.LifeLaneTheme
import org.lifelane.mobile.ui.theme.PrimaryTeal
import org.lifelane.mobile.ui.theme.WarningAmber
import org.lifelane.mobile.ui.theme.WhatsAppBlueTick
import org.lifelane.mobile.ui.theme.WhatsAppShapes
import org.lifelane.mobile.ui.theme.WhatsAppTokens
import org.lifelane.mobile.ui.theme.WhatsAppVibrantGreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { LifeLaneApp() }
    }
}

@Composable
fun LifeLaneApp(vm: TripViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    var darkTheme by rememberSaveable { mutableStateOf(false) }
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        val granted = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true || grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (granted) {
            try {
                LocationServices.getFusedLocationProviderClient(context).lastLocation.addOnSuccessListener { loc ->
                    if (loc != null) vm.updatePreTripLocation(loc.latitude, loc.longitude, loc.accuracy)
                }
            } catch (e: SecurityException) { /* no-op */ }
            if (state.screen == AppScreen.CONFIRM) vm.startTrip()
        } else {
            if (state.screen == AppScreen.CONFIRM) vm.reportPermissionDenied()
        }
    }
    val requestLocationAndStart = {
        val fine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (fine || coarse) vm.startTrip()
        else {
            val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            if (Build.VERSION.SDK_INT >= 33) permissions += Manifest.permission.POST_NOTIFICATIONS
            permissionLauncher.launch(permissions.toTypedArray())
        }
    }

    // Automatically check and acquire location fix early so real-time map and nearby hospitals load immediately
    LaunchedEffect(state.screen) {
        val fine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (fine || coarse) {
            try {
                LocationServices.getFusedLocationProviderClient(context).lastLocation.addOnSuccessListener { loc ->
                    if (loc != null) vm.updatePreTripLocation(loc.latitude, loc.longitude, loc.accuracy)
                }
            } catch (e: SecurityException) { /* no-op */ }
        } else if (state.screen == AppScreen.AMBULANCE || state.screen == AppScreen.DESTINATION) {
            val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            if (Build.VERSION.SDK_INT >= 33) permissions += Manifest.permission.POST_NOTIFICATIONS
            permissionLauncher.launch(permissions.toTypedArray())
        }
    }

    LifeLaneTheme(darkTheme) {
        if (state.screen == AppScreen.SPLASH) {
            SplashScreen(vm::finishSplash)
            return@LifeLaneTheme
        }
        val title = when (state.screen) {
            AppScreen.LOGIN -> "Driver Sign-In"
            AppScreen.AMBULANCE -> "Select Ambulance"
            AppScreen.PRIORITY, AppScreen.CONDITION -> "Patient Urgency"
            AppScreen.DESTINATION -> "Destination Hospital"
            AppScreen.CONFIRM -> "Confirm Emergency Route"
            AppScreen.EMERGENCY, AppScreen.DELIVER_CONFIRM, AppScreen.CANCEL_CONFIRM -> "Emergency Dispatch"
            AppScreen.LIVE_GPS -> "Live Telemetry"
            else -> "LifeLane"
        }
        Scaffold(
            topBar = { LifeLaneTopBar(title, darkTheme, { darkTheme = !darkTheme }) },
            containerColor = MaterialTheme.colorScheme.background,
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                when (state.screen) {
                    AppScreen.LOGIN -> LoginScreen(state, vm, darkTheme)
                    AppScreen.AMBULANCE -> AmbulanceScreen(state, vm, darkTheme)
                    AppScreen.PRIORITY -> PriorityScreen(state, vm, darkTheme)
                    AppScreen.CONDITION -> ConditionScreen(state, vm, darkTheme)
                    AppScreen.DESTINATION -> DestinationScreen(state, vm, darkTheme)
                    AppScreen.CONFIRM -> TripConfirmationScreen(state, vm, darkTheme, requestLocationAndStart)
                    AppScreen.EMERGENCY -> ActiveEmergencyScreen(state, vm, darkTheme)
                    AppScreen.LIVE_GPS -> LiveGpsScreen(state, vm, darkTheme)
                    AppScreen.DELIVER_CONFIRM -> {
                        ActiveEmergencyScreen(state, vm, darkTheme)
                        ConfirmationBottomSheet(
                            "Complete emergency trip?",
                            "GPS transmission and the MQTT emergency preemption session will complete. The result remains in junction history.",
                            "Complete Trip", false, { vm.stopTrip(false) }, vm::dismissConfirmation,
                        )
                    }
                    AppScreen.CANCEL_CONFIRM -> {
                        ActiveEmergencyScreen(state, vm, darkTheme)
                        ConfirmationBottomSheet(
                            "Cancel emergency preemption?",
                            "Use this only if emergency transport is no longer needed. The junction will restore standard signal cycles.",
                            "Cancel Emergency", true, { vm.stopTrip(true) }, vm::dismissConfirmation,
                        )
                    }
                    AppScreen.SPLASH -> Unit
                }
            }
        }
    }
}

@Composable
private fun ScreenContainer(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        Column(
            Modifier
                .fillMaxWidth()
                .widthIn(max = 820.dp)
                .verticalScroll(rememberScrollState())
                .padding(LifeLaneDimens.pagePadding),
            verticalArrangement = Arrangement.spacedBy(LifeLaneDimens.large),
        ) { content() }
    }
}

@Composable
private fun ScreenHeading(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MessageBanner(message: String?) {
    message?.let { WarningBanner("Attention required", it) }
}

@Composable
private fun SetupProgress(step: Int, label: String) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text("Step $step of 3", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold, color = WhatsAppVibrantGreen)
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        LinearProgressIndicator(
            progress = { step / 3f },
            modifier = Modifier.fillMaxWidth().height(6.dp).clip(CircleShape),
            color = WhatsAppVibrantGreen,
            trackColor = WhatsAppVibrantGreen.copy(alpha = 0.18f),
        )
    }
}

@Composable
private fun SplashScreen(onFinished: () -> Unit) {
    LaunchedEffect(Unit) { delay(700); onFinished() }
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            Modifier.fillMaxSize().semantics { contentDescription = "LifeLane loading" },
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            LifeLaneBrand()
            Spacer(Modifier.height(36.dp))
            CircularProgressIndicator(modifier = Modifier.size(32.dp), color = WhatsAppVibrantGreen, strokeWidth = 3.dp)
            Text(
                "Establishing secure junction channel",
                Modifier.padding(top = 16.dp),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(48.dp))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Icon(Icons.Outlined.Lock, contentDescription = null, tint = WhatsAppVibrantGreen, modifier = Modifier.size(15.dp))
                Text("End-to-end encrypted emergency preemption", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun LoginScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean) {
    var driverId by rememberSaveable { mutableStateOf(state.driverId) }
    var pin by rememberSaveable { mutableStateOf("") }
    var rememberAmbulance by rememberSaveable { mutableStateOf(state.ambulanceId.isNotBlank()) }

    ScreenContainer {
        ScreenHeading("Responder Sign-In", "Sign in before operating an emergency preemption session.")
        MessageBanner(state.message)
        WhatsAppSecurityBanner(darkTheme = darkTheme)
        Card(
            shape = WhatsAppShapes.card,
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        ) {
            Column(Modifier.fillMaxWidth().padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                LifeLaneBrand()
                HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f))
                OutlinedTextField(
                    value = driverId,
                    onValueChange = { driverId = it },
                    label = { Text("Driver ID") },
                    leadingIcon = { Icon(Icons.Outlined.Person, null, tint = WhatsAppVibrantGreen) },
                    singleLine = true,
                    shape = WhatsAppShapes.card,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = WhatsAppVibrantGreen,
                        focusedLabelColor = WhatsAppVibrantGreen,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = pin,
                    onValueChange = { pin = it.filter(Char::isDigit).take(8) },
                    label = { Text("Access PIN") },
                    leadingIcon = { Icon(Icons.Outlined.Lock, null, tint = WhatsAppVibrantGreen) },
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    singleLine = true,
                    shape = WhatsAppShapes.card,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = WhatsAppVibrantGreen,
                        focusedLabelColor = WhatsAppVibrantGreen,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(
                        checked = rememberAmbulance,
                        onCheckedChange = { rememberAmbulance = it },
                        colors = CheckboxDefaults.colors(checkedColor = WhatsAppVibrantGreen),
                    )
                    Text(
                        "Remember authorized vehicle on this device",
                        Modifier.clickable { rememberAmbulance = !rememberAmbulance }.padding(vertical = 8.dp),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                ConnectionBadge("Broker", "Configured ${BuildConfig.MQTT_HOST}:${BuildConfig.MQTT_PORT}")
                PrimaryActionButton("Sign In", { vm.login(driverId, pin, rememberAmbulance) })
                Text(
                    "Local authorization. Driver credentials are authenticated on-device.",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private data class AmbulanceChoice(val id: String, val registration: String, val unit: String)

@Composable
private fun AmbulanceScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean) {
    val choices = listOf(
        AmbulanceChoice("AMB-001", "MH-12-RN-1001", "City General Emergency Unit 1"),
        AmbulanceChoice("AMB-002", "MH-12-RN-1002", "Metro Trauma Care Unit 2"),
        AmbulanceChoice("AMB-003", "MH-12-RN-1003", "St. Jude Rapid Response"),
        AmbulanceChoice("AMB-004", "MH-12-RN-1004", "Pediatric Critical Care"),
    )
    ScreenContainer {
        ScreenHeading("Select Ambulance", "Choose an authorized vehicle from your connected fleet.")
        MessageBanner(state.message)
        WhatsAppSecurityBanner(
            text = "Fleet authentication active. Selected vehicle receives encrypted traffic-light preemption authorization.",
            darkTheme = darkTheme,
        )
        Text("Active Vehicles", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        choices.forEach { item ->
            val isSelected = item.id == state.ambulanceId
            val cardBg = if (isSelected) WhatsAppTokens.outgoingBubbleColor(darkTheme) else MaterialTheme.colorScheme.surface
            val borderStroke = if (isSelected) BorderStroke(2.dp, WhatsAppVibrantGreen) else BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f))

            Card(
                modifier = Modifier.fillMaxWidth().clickable { vm.selectAmbulance(item.id) },
                shape = WhatsAppShapes.card,
                colors = CardDefaults.cardColors(containerColor = cardBg),
                border = borderStroke,
            ) {
                Row(
                    Modifier.fillMaxWidth().padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Box(
                        Modifier
                            .size(48.dp)
                            .clip(CircleShape)
                            .background(WhatsAppVibrantGreen.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            Icons.Outlined.DirectionsCar,
                            contentDescription = null,
                            tint = WhatsAppVibrantGreen,
                            modifier = Modifier.size(26.dp),
                        )
                    }
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(item.id, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            WhatsAppCheckMarks(CheckMarkState.DOUBLE_BLUE)
                        }
                        Text(item.unit, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Reg: ${item.registration}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Surface(
                        shape = WhatsAppShapes.pillBadge,
                        color = WhatsAppVibrantGreen.copy(alpha = 0.12f),
                    ) {
                        Text(
                            "Authorized",
                            Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = WhatsAppVibrantGreen,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PriorityScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean) {
    ScreenContainer {
        SetupProgress(1, "Medical Urgency")
        ScreenHeading("Reported Urgency", "Select patient severity to determine priority queue position.")
        MessageBanner(state.message)
        PatientPriority.entries.forEach { priority ->
            PriorityCard(
                priority = priority,
                selected = state.priority == priority,
                onSelect = { vm.setPriority(priority) },
                darkTheme = darkTheme,
            )
        }
        PrimaryActionButton("Continue to Condition", vm::continueFromPriority, enabled = state.priority != null)
        OutlinedButton(
            onClick = { vm.backTo(AppScreen.AMBULANCE) },
            modifier = Modifier.fillMaxWidth().height(50.dp),
            shape = WhatsAppShapes.actionButton,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Icon(Icons.AutoMirrored.Outlined.ArrowBack, null, tint = MaterialTheme.colorScheme.onSurface)
            Text("Choose another ambulance", Modifier.padding(start = 8.dp), color = MaterialTheme.colorScheme.onSurface)
        }
    }
}

@Composable
private fun ConditionScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean) {
    ScreenContainer {
        SetupProgress(1, "Medical Condition")
        ScreenHeading("Patient Condition", "Record the minimum clinical category for the emergency signal log.")
        MessageBanner(state.message)
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            PatientCondition.entries.forEach { condition ->
                ConditionChip(
                    label = condition.label,
                    selected = state.condition == condition,
                    onSelect = { vm.setCondition(condition) },
                    darkTheme = darkTheme,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        PrimaryActionButton("Continue to Destination", vm::continueFromCondition, enabled = state.condition != null)
        OutlinedButton(
            onClick = { vm.backTo(AppScreen.PRIORITY) },
            modifier = Modifier.fillMaxWidth().height(50.dp),
            shape = WhatsAppShapes.actionButton,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Icon(Icons.AutoMirrored.Outlined.ArrowBack, null, tint = MaterialTheme.colorScheme.onSurface)
            Text("Back to urgency selection", Modifier.padding(start = 8.dp), color = MaterialTheme.colorScheme.onSurface)
        }
    }
}

@Composable
private fun DestinationScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean) {
    val selected = state.selectedHospital ?: DEFAULT_HOSPITALS.find { it.name.equals(state.destination, ignoreCase = true) }

    ScreenContainer {
        SetupProgress(2, "Destination")
        ScreenHeading("Destination Medical Center", "Select receiving hospital facility to calculate route & corridor preemption.")
        MessageBanner(state.message)

        Text("Select Hospital Facility", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)

        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            DEFAULT_HOSPITALS.forEach { hospital ->
                val isSelected = selected?.id == hospital.id || state.destination.equals(hospital.name, ignoreCase = true)
                val cardBg = if (isSelected) WhatsAppTokens.outgoingBubbleColor(darkTheme) else MaterialTheme.colorScheme.surface
                val borderStroke = if (isSelected) BorderStroke(2.dp, WhatsAppVibrantGreen) else BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f))

                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { vm.selectHospital(hospital) },
                    shape = WhatsAppShapes.card,
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    border = borderStroke,
                ) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Box(
                            Modifier
                                .size(44.dp)
                                .clip(CircleShape)
                                .background(if (isSelected) WhatsAppVibrantGreen.copy(alpha = 0.20f) else MaterialTheme.colorScheme.surfaceVariant),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(
                                Icons.Outlined.LocalHospital,
                                contentDescription = null,
                                tint = if (isSelected) WhatsAppVibrantGreen else EmergencyRed,
                                modifier = Modifier.size(24.dp),
                            )
                        }

                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(hospital.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                                if (isSelected) WhatsAppCheckMarks(CheckMarkState.DOUBLE_BLUE)
                            }
                            Text(hospital.specialty, style = MaterialTheme.typography.bodySmall, color = WhatsAppVibrantGreen, fontWeight = FontWeight.Medium)
                            Text("${hospital.address} · ${hospital.corridorApproach} Corridor", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }

                        Surface(
                            shape = WhatsAppShapes.pillBadge,
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Text(
                                "%.2f km".format(hospital.distanceKm),
                                Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }

        // Custom Destination Input
        Text("Or Enter Custom Destination", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = state.destination,
            onValueChange = vm::setDestination,
            label = { Text("Custom Hospital or Clinic Name") },
            leadingIcon = { Icon(Icons.Outlined.Place, null, tint = WhatsAppVibrantGreen) },
            supportingText = { Text("Junction distance & approach calculation will initialize upon route activation.") },
            singleLine = true,
            shape = WhatsAppShapes.card,
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = WhatsAppVibrantGreen,
                focusedLabelColor = WhatsAppVibrantGreen,
            ),
            modifier = Modifier.fillMaxWidth(),
        )

        // Route Map Preview
        if (state.destination.isNotBlank()) {
            Text("Route Corridor Preview", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            LiveRouteMapView(
                ambulanceLat = state.latitude,
                ambulanceLon = state.longitude,
                headingDegrees = state.headingDegrees,
                speedMps = state.speedMps,
                ambulanceId = state.ambulanceId,
                destinationHospital = state.destination,
                destinationLat = state.destinationLat ?: selected?.latitude,
                destinationLon = state.destinationLon ?: selected?.longitude,
                signalStatus = "PREVIEW",
                detectedApproach = selected?.corridorApproach ?: "North",
                distanceMetres = 550.0,
                isEmergencyActive = false,
                darkTheme = darkTheme,
                accuracyMetres = state.accuracyMetres,
                modifier = Modifier.height(200.dp),
            )
        }

        PrimaryActionButton("Review Route & Preemption", vm::reviewTrip, enabled = state.destination.isNotBlank())
        OutlinedButton(
            onClick = { vm.backTo(AppScreen.CONDITION) },
            modifier = Modifier.fillMaxWidth().height(50.dp),
            shape = WhatsAppShapes.actionButton,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Icon(Icons.AutoMirrored.Outlined.ArrowBack, null, tint = MaterialTheme.colorScheme.onSurface)
            Text("Back to patient condition", Modifier.padding(start = 8.dp), color = MaterialTheme.colorScheme.onSurface)
        }
    }
}

@Composable
private fun TripConfirmationScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean, start: () -> Unit) {
    ScreenContainer {
        SetupProgress(3, "Confirmation")
        ScreenHeading("Confirm Emergency Route", "Verify preemption parameters & planned route before activating live telemetry.")
        MessageBanner(state.message)

        // Live Route Preview
        LiveRouteMapView(
            ambulanceLat = state.latitude,
            ambulanceLon = state.longitude,
            headingDegrees = state.headingDegrees,
            speedMps = state.speedMps,
            ambulanceId = state.ambulanceId,
            destinationHospital = state.destination,
            destinationLat = state.destinationLat,
            destinationLon = state.destinationLon,
            signalStatus = state.signalStatus,
            detectedApproach = state.detectedApproach,
            distanceMetres = state.distanceMetres,
            isEmergencyActive = false,
            darkTheme = darkTheme,
            accuracyMetres = state.accuracyMetres,
            modifier = Modifier.height(240.dp),
        )

        DetailCard(
            "Route & Preemption Overview",
            listOf(
                "Ambulance" to state.ambulanceId,
                "Medical urgency" to priorityLabel(state.priority),
                "Condition" to (state.condition?.label ?: "Not selected"),
                "Destination" to state.destination,
                "Preemption Zone" to "300m Radar Boundary Active",
                "GPS Service" to "High Precision (1.5s refresh)",
                "MQTT Telemetry" to "Auto-broadcast to Junction",
            ),
        )

        WhatsAppSecurityBanner(
            text = "Driver confirmation required: Starting this route engages live GPS tracking and broadcasts authenticated traffic signal preemption requests.",
            darkTheme = darkTheme,
        )

        PrimaryActionButton("START EMERGENCY ROUTE", start)
        OutlinedButton(
            onClick = { vm.backTo(AppScreen.DESTINATION) },
            modifier = Modifier.fillMaxWidth().height(50.dp),
            shape = WhatsAppShapes.actionButton,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Icon(Icons.AutoMirrored.Outlined.ArrowBack, null, tint = MaterialTheme.colorScheme.onSurface)
            Text("Edit destination hospital", Modifier.padding(start = 8.dp), color = MaterialTheme.colorScheme.onSurface)
        }
    }
}

@Composable
private fun ActiveEmergencyScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean) {
    val elapsed by produceState(initialValue = 0L, state.startTime) {
        while (true) {
            value = state.startTime?.let { Duration.between(it, Instant.now()).seconds.coerceAtLeast(0) } ?: 0
            delay(1000)
        }
    }
    val stage = emergencyStage(state)
    val statusMessage = if (stage < 0) "Acquiring precision GPS fix" else listOf(
        "GPS transmission active",
        "Approaching ${state.detectedApproach.lowercase().replaceFirstChar(Char::uppercase)} approach",
        "Preemption request transmitted",
        "Request validated · Awaiting green light",
        "${state.detectedApproach.lowercase().replaceFirstChar(Char::uppercase)} green priority confirmed ✓✓",
        "Junction cleared safely",
    ).getOrElse(stage) { "Junction state updating" }

    ScreenContainer {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Emergency Active", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    WhatsAppCheckMarks(if (stage >= 4) CheckMarkState.DOUBLE_BLUE else CheckMarkState.DOUBLE_GREY)
                }
                Text(statusMessage, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Surface(
                shape = WhatsAppShapes.pillBadge,
                color = priorityColour(state.priority).copy(alpha = 0.14f),
                border = BorderStroke(1.dp, priorityColour(state.priority)),
            ) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(Icons.Outlined.LocalHospital, null, tint = priorityColour(state.priority), modifier = Modifier.size(17.dp))
                    Text(priorityLabel(state.priority), fontWeight = FontWeight.Bold, color = priorityColour(state.priority), style = MaterialTheme.typography.labelMedium)
                }
            }
        }

        // Live Route Navigation Map Canvas
        LiveRouteMapView(
            ambulanceLat = state.latitude,
            ambulanceLon = state.longitude,
            headingDegrees = state.headingDegrees,
            speedMps = state.speedMps,
            ambulanceId = state.ambulanceId,
            destinationHospital = state.destination,
            destinationLat = state.destinationLat,
            destinationLon = state.destinationLon,
            signalStatus = state.signalStatus,
            detectedApproach = state.detectedApproach,
            distanceMetres = state.distanceMetres,
            isEmergencyActive = state.emergencyActive,
            darkTheme = darkTheme,
            accuracyMetres = state.accuracyMetres,
            modifier = Modifier.height(320.dp),
            isExpandedView = false,
            onToggleExpand = vm::showLiveGps,
        )

        val mqttLost = state.mqttStatus.contains("error", true) || state.mqttStatus.contains("disconnected", true) || state.mqttStatus.contains("reconnecting", true)
        val gpsLost = listOf("denied", "unavailable", "inaccurate", "lost").any { state.gpsStatus.contains(it, true) }
        if (mqttLost || gpsLost) {
            WarningBanner(
                title = if (mqttLost) "MQTT Link Interrupted" else "GPS Requires Calibration",
                detail = if (mqttLost) "Retaining last known state. No preemption is assumed while offline." else "${state.gpsStatus}. Move to open sky.",
                onRetry = vm::retryConnections,
            )
        }
        if (state.gpsStatus.contains("acquiring", true)) {
            LoadingState("Acquiring GPS fix. MQTT session remains online.")
        }

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            LiveMetricCard("Distance", state.distanceMetres?.let { "%.0f m".format(it) } ?: "—", Modifier.weight(1f), state.nextJunction, isHighlight = true, darkTheme = darkTheme)
            LiveMetricCard("ETA", state.distanceMetres?.let { distance -> if (state.speedMps > 0.5f) "%.0f s".format(distance / state.speedMps) else "—" } ?: "—", Modifier.weight(1f), "Live estimate", darkTheme = darkTheme)
            LiveMetricCard("Duration", "%02d:%02d".format(elapsed / 60, elapsed % 60), Modifier.weight(1f), "In transit", darkTheme = darkTheme)
        }

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ConnectionBadge("GPS", state.gpsStatus, Modifier.weight(1f))
            ConnectionBadge("MQTT", state.mqttStatus, Modifier.weight(1f))
        }

        BoxWithConstraints {
            if (maxWidth > 680.dp) {
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.Top) {
                    EmergencyStatusCard(EMERGENCY_STAGES, stage, Modifier.weight(1f))
                    DetailCard("Live Telemetry", activeDetails(state), Modifier.weight(1f))
                }
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    EmergencyStatusCard(EMERGENCY_STAGES, stage)
                    DetailCard("Live Telemetry", activeDetails(state))
                }
            }
        }

        PrimaryActionButton("Full-Screen Live GPS Route Navigation", vm::showLiveGps)
        OutlinedButton(
            onClick = vm::requestDelivery,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = WhatsAppShapes.actionButton,
            border = BorderStroke(1.dp, WhatsAppVibrantGreen),
        ) {
            Icon(Icons.Outlined.CheckCircle, null, tint = WhatsAppVibrantGreen)
            Text("Complete Trip (Patient Delivered)", Modifier.padding(start = 8.dp), fontWeight = FontWeight.Bold, color = WhatsAppVibrantGreen)
        }
        DangerActionButton("Cancel Emergency Preemption", vm::requestCancel)
    }
}

private val EMERGENCY_STAGES = listOf(
    "GPS ACTIVE",
    "JUNCTION DETECTED",
    "REQUEST SENT",
    "REQUEST VALIDATED",
    "PRIORITY GRANTED",
    "JUNCTION CLEARED",
)

private fun emergencyStage(state: TripUiState): Int {
    var stage = -1
    if (state.gpsStatus.equals("Live", true)) stage = 0
    if (state.distanceMetres != null && state.detectedApproach != "Not detected") stage = 1
    if (state.requestStatus.contains("sent", true) || state.requestStatus.contains("waiting", true) || state.requestStatus.contains("selected", true) || state.requestStatus.contains("active", true)) stage = 2
    if (state.requestStatus.contains("waiting", true) || state.requestStatus.contains("selected", true) || state.requestStatus.contains("active", true)) stage = 3
    val approachGreen = state.detectedApproach != "Not detected" && state.signalStatus.contains("${state.detectedApproach.uppercase()}:GREEN", true)
    val liveJunctionConnection = state.mqttStatus.equals("Connected", true)
    if ((state.requestStatus.contains("selected", true) || state.requestStatus.contains("active", true)) && approachGreen && liveJunctionConnection) stage = 4
    return stage
}

private fun activeDetails(state: TripUiState) = listOf(
    "Ambulance" to state.ambulanceId,
    "Detected approach" to state.detectedApproach,
    "Request status" to state.requestStatus,
    "Signal priority" to when {
        !state.mqttStatus.equals("Connected", true) -> "Offline"
        emergencyStage(state) >= 4 -> "Confirmed Green ✓✓"
        else -> "Pending validation"
    },
    "Current speed" to "%.1f m/s (%.0f km/h)".format(state.speedMps, state.speedMps * 3.6f),
    "GPS accuracy" to (state.accuracyMetres?.let { "%.1f m".format(it) } ?: "—"),
    "Destination" to state.destination,
)

@Composable
private fun LiveGpsScreen(state: TripUiState, vm: TripViewModel, darkTheme: Boolean) {
    ScreenContainer {
        ScreenHeading("Full Navigation Route Map", "Live vehicle telemetry & preemption corridor.")

        // Full Screen Live Navigation Map
        LiveRouteMapView(
            ambulanceLat = state.latitude,
            ambulanceLon = state.longitude,
            headingDegrees = state.headingDegrees,
            speedMps = state.speedMps,
            ambulanceId = state.ambulanceId,
            destinationHospital = state.destination,
            destinationLat = state.destinationLat,
            destinationLon = state.destinationLon,
            signalStatus = state.signalStatus,
            detectedApproach = state.detectedApproach,
            distanceMetres = state.distanceMetres,
            isEmergencyActive = state.emergencyActive,
            darkTheme = darkTheme,
            accuracyMetres = state.accuracyMetres,
            modifier = Modifier.height(420.dp),
            isExpandedView = true,
            onToggleExpand = vm::showEmergency,
        )

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ConnectionBadge("GPS", state.gpsStatus, Modifier.weight(1f))
            ConnectionBadge("MQTT", state.mqttStatus, Modifier.weight(1f))
        }

        if (!state.gpsStatus.equals("Live", true)) {
            WarningBanner(
                title = "Waiting for reliable positioning",
                detail = "${state.gpsStatus}. The last verified coordinates remain available.",
                onRetry = vm::retryConnections,
            )
        }

        DetailCard(
            "Live GPS Telemetry",
            listOf(
                "Trip ID" to state.tripId,
                "Ambulance" to state.ambulanceId,
                "Latitude" to (state.latitude?.let { "%.6f".format(it) } ?: "—"),
                "Longitude" to (state.longitude?.let { "%.6f".format(it) } ?: "—"),
                "Heading" to "%.0f°".format(state.headingDegrees),
                "Speed" to "%.1f m/s (%.0f km/h)".format(state.speedMps, state.speedMps * 3.6f),
                "Accuracy" to (state.accuracyMetres?.let { "%.1f m".format(it) } ?: "—"),
                "Destination" to state.destination,
                "Junction Radar" to "${state.nextJunction} (300m Zone)",
                "MQTT Broker" to "${BuildConfig.MQTT_HOST}:${BuildConfig.MQTT_PORT}",
            ),
        )

        PrimaryActionButton("Back to Emergency Session", vm::showEmergency)
    }
}

@Composable
private fun DetailCard(title: String, rows: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
    ) {
        Column(Modifier.fillMaxWidth().padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(11.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            rows.forEachIndexed { index, (label, value) ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
                    Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.End, modifier = Modifier.weight(1.3f))
                }
                if (index < rows.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f))
            }
        }
    }
}

private fun priorityLabel(priority: PatientPriority?): String = when (priority) {
    PatientPriority.RED -> "Critical"
    PatientPriority.YELLOW -> "Serious"
    PatientPriority.GREEN -> "Stable"
    null -> "Not selected"
}

private fun priorityColour(priority: PatientPriority?) = when (priority) {
    PatientPriority.RED -> EmergencyRed
    PatientPriority.YELLOW -> WarningAmber
    PatientPriority.GREEN -> ActiveGreen
    null -> InformationBlue
}

