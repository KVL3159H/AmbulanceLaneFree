package org.lifelane.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.DirectionsCar
import androidx.compose.material.icons.outlined.LocalHospital
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import java.time.Duration
import java.time.Instant
import kotlinx.coroutines.delay
import org.lifelane.mobile.ui.components.ConditionChip
import org.lifelane.mobile.ui.components.ConfirmationBottomSheet
import org.lifelane.mobile.ui.components.ConnectionBadge
import org.lifelane.mobile.ui.components.DangerActionButton
import org.lifelane.mobile.ui.components.EmergencyStatusCard
import org.lifelane.mobile.ui.components.EmptyState
import org.lifelane.mobile.ui.components.LifeLaneBrand
import org.lifelane.mobile.ui.components.LifeLaneTopBar
import org.lifelane.mobile.ui.components.LiveMetricCard
import org.lifelane.mobile.ui.components.LoadingState
import org.lifelane.mobile.ui.components.PrimaryActionButton
import org.lifelane.mobile.ui.components.PriorityCard
import org.lifelane.mobile.ui.components.WarningBanner
import org.lifelane.mobile.ui.theme.ActiveGreen
import org.lifelane.mobile.ui.theme.EmergencyRed
import org.lifelane.mobile.ui.theme.InformationBlue
import org.lifelane.mobile.ui.theme.LifeLaneDimens
import org.lifelane.mobile.ui.theme.LifeLaneTheme
import org.lifelane.mobile.ui.theme.PrimaryTeal
import org.lifelane.mobile.ui.theme.WarningAmber

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { LifeLaneApp() }
    }
}

@Composable
fun LifeLaneApp(vm: TripViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    var darkTheme by rememberSaveable { mutableStateOf(true) }
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        if (grants[Manifest.permission.ACCESS_FINE_LOCATION] == true || grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true) vm.startTrip()
        else vm.reportPermissionDenied()
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
    LifeLaneTheme(darkTheme) {
        if (state.screen == AppScreen.SPLASH) {
            SplashScreen(vm::finishSplash)
            return@LifeLaneTheme
        }
        val title = when (state.screen) {
            AppScreen.LOGIN -> "Driver sign-in"
            AppScreen.AMBULANCE -> "Select ambulance"
            AppScreen.PRIORITY, AppScreen.CONDITION -> "Patient details"
            AppScreen.DESTINATION -> "Destination"
            AppScreen.CONFIRM -> "Confirm emergency route"
            AppScreen.EMERGENCY, AppScreen.DELIVER_CONFIRM, AppScreen.CANCEL_CONFIRM -> "Emergency route"
            AppScreen.LIVE_GPS -> "Live GPS"
            else -> "LifeLane"
        }
        Scaffold(topBar = { LifeLaneTopBar(title, darkTheme, { darkTheme = !darkTheme }) }) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                when (state.screen) {
                    AppScreen.LOGIN -> LoginScreen(state, vm)
                    AppScreen.AMBULANCE -> AmbulanceScreen(state, vm)
                    AppScreen.PRIORITY -> PriorityScreen(state, vm)
                    AppScreen.CONDITION -> ConditionScreen(state, vm)
                    AppScreen.DESTINATION -> DestinationScreen(state, vm)
                    AppScreen.CONFIRM -> TripConfirmationScreen(state, vm, requestLocationAndStart)
                    AppScreen.EMERGENCY -> ActiveEmergencyScreen(state, vm)
                    AppScreen.LIVE_GPS -> LiveGpsScreen(state, vm)
                    AppScreen.DELIVER_CONFIRM -> {
                        ActiveEmergencyScreen(state, vm)
                        ConfirmationBottomSheet(
                            "Complete emergency trip?",
                            "GPS transmission and the MQTT emergency session will stop. The trip result will remain in junction history.",
                            "Complete Trip", false, { vm.stopTrip(false) }, vm::dismissConfirmation,
                        )
                    }
                    AppScreen.CANCEL_CONFIRM -> {
                        ActiveEmergencyScreen(state, vm)
                        ConfirmationBottomSheet(
                            "Cancel emergency?",
                            "Use this only when the emergency route is no longer required. The junction will safely restore normal operation.",
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
            Modifier.fillMaxWidth().widthIn(max = 820.dp).verticalScroll(rememberScrollState()).padding(LifeLaneDimens.pagePadding),
            verticalArrangement = Arrangement.spacedBy(LifeLaneDimens.large),
        ) { content() }
    }
}

@Composable
private fun ScreenHeading(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(title, style = MaterialTheme.typography.displaySmall)
        Text(subtitle, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MessageBanner(message: String?) {
    message?.let { WarningBanner("Action required", it) }
}

@Composable
private fun SetupProgress(step: Int, label: String) {
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Step $step of 3", style = MaterialTheme.typography.labelMedium, color = PrimaryTeal)
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        LinearProgressIndicator(progress = { step / 3f }, modifier = Modifier.fillMaxWidth().height(6.dp), color = PrimaryTeal)
    }
}

@Composable
private fun SplashScreen(onFinished: () -> Unit) {
    LaunchedEffect(Unit) { delay(650); onFinished() }
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            Modifier.fillMaxSize().semantics { contentDescription = "LifeLane loading" },
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            LifeLaneBrand()
            Spacer(Modifier.height(32.dp))
            CircularProgressIndicator(modifier = Modifier.size(28.dp), color = PrimaryTeal, strokeWidth = 2.dp)
            Text("Preparing secure emergency route", Modifier.padding(top = 12.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun LoginScreen(state: TripUiState, vm: TripViewModel) {
    var driverId by rememberSaveable { mutableStateOf(state.driverId) }
    var pin by rememberSaveable { mutableStateOf("") }
    var rememberAmbulance by rememberSaveable { mutableStateOf(state.ambulanceId.isNotBlank()) }
    ScreenContainer {
        ScreenHeading("Ready for service", "Sign in before selecting an authorized ambulance.")
        MessageBanner(state.message)
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)) {
            Column(Modifier.fillMaxWidth().padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                LifeLaneBrand()
                HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                OutlinedTextField(
                    driverId, { driverId = it }, label = { Text("Driver ID") }, leadingIcon = { Icon(Icons.Outlined.Person, null) },
                    singleLine = true, modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    pin, { pin = it.filter(Char::isDigit).take(8) }, label = { Text("Secure PIN") }, leadingIcon = { Icon(Icons.Outlined.Lock, null) },
                    visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    singleLine = true, modifier = Modifier.fillMaxWidth(),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(rememberAmbulance, { rememberAmbulance = it })
                    Text("Remember authorized ambulance", Modifier.clickable { rememberAmbulance = !rememberAmbulance }.padding(vertical = 12.dp))
                }
                ConnectionBadge("Broker", "Configured ${BuildConfig.MQTT_HOST}:${BuildConfig.MQTT_PORT}")
                PrimaryActionButton("Sign in", { vm.login(driverId, pin, rememberAmbulance) })
                Text("Prototype local authorization. The PIN is validated on-device and is never stored.", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

private data class AmbulanceChoice(val id: String, val registration: String, val unit: String)

@Composable
private fun AmbulanceScreen(state: TripUiState, vm: TripViewModel) {
    val choices = listOf(
        AmbulanceChoice("AMB-001", "Not configured", "Prototype fleet"), AmbulanceChoice("AMB-002", "Not configured", "Prototype fleet"),
        AmbulanceChoice("AMB-003", "Not configured", "Prototype fleet"), AmbulanceChoice("AMB-004", "Not configured", "Prototype fleet"),
    )
    ScreenContainer {
        ScreenHeading("Select ambulance", "Only vehicles authorized by the junction configuration are listed.")
        MessageBanner(state.message)
        choices.forEach { item ->
            Card(
                Modifier.fillMaxWidth().clickable { vm.selectAmbulance(item.id) },
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                border = BorderStroke(if (item.id == state.ambulanceId) 2.dp else 1.dp, if (item.id == state.ambulanceId) PrimaryTeal else MaterialTheme.colorScheme.outline),
            ) {
                Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    Icon(Icons.Outlined.DirectionsCar, contentDescription = null, tint = PrimaryTeal, modifier = Modifier.size(30.dp))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(item.id, style = MaterialTheme.typography.titleMedium)
                        Text("Registration · ${item.registration}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Service unit · ${item.unit}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Last connection · Not available", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    ConnectionBadge("Status", "Authorized")
                }
            }
        }
    }
}

@Composable
private fun PriorityScreen(state: TripUiState, vm: TripViewModel) {
    ScreenContainer {
        SetupProgress(1, "Patient details")
        ScreenHeading("Medical priority", "Select the reported urgency. Critical is never preselected.")
        MessageBanner(state.message)
        PatientPriority.entries.forEach { priority -> PriorityCard(priority, state.priority == priority, { vm.setPriority(priority) }) }
        PrimaryActionButton("Continue to condition", vm::continueFromPriority, enabled = state.priority != null)
        OutlinedButton({ vm.backTo(AppScreen.AMBULANCE) }, Modifier.fillMaxWidth().height(50.dp)) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, null); Text("Choose another ambulance", Modifier.padding(start = 8.dp)) }
    }
}

@Composable
private fun ConditionScreen(state: TripUiState, vm: TripViewModel) {
    ScreenContainer {
        SetupProgress(1, "Patient details")
        ScreenHeading("Reported condition", "Record only the minimum operational category—never the patient’s name.")
        MessageBanner(state.message)
        PatientCondition.entries.forEach { condition -> ConditionChip(condition.label, state.condition == condition, { vm.setCondition(condition) }) }
        PrimaryActionButton("Continue to destination", vm::continueFromCondition, enabled = state.condition != null)
        OutlinedButton({ vm.backTo(AppScreen.PRIORITY) }, Modifier.fillMaxWidth().height(50.dp)) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, null); Text("Back to priority", Modifier.padding(start = 8.dp)) }
    }
}

@Composable
private fun DestinationScreen(state: TripUiState, vm: TripViewModel) {
    ScreenContainer {
        SetupProgress(2, "Destination")
        ScreenHeading("Destination hospital", "Enter the receiving hospital. External map services are not required.")
        MessageBanner(state.message)
        OutlinedTextField(
            state.destination, vm::setDestination, label = { Text("Hospital name") }, leadingIcon = { Icon(Icons.Outlined.LocalHospital, null) },
            supportingText = { Text("Route distance becomes available after GPS starts.") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        Text("Recently used hospitals", style = MaterialTheme.typography.titleMedium)
        if (state.recentHospitals.isEmpty()) EmptyState("No recent hospitals", "Hospitals confirmed on this device will appear here.")
        else state.recentHospitals.forEach { hospital ->
            OutlinedButton({ vm.useRecentHospital(hospital) }, Modifier.fillMaxWidth().height(50.dp)) { Text(hospital) }
        }
        PrimaryActionButton("Review emergency route", vm::reviewTrip, enabled = state.destination.isNotBlank())
        OutlinedButton({ vm.backTo(AppScreen.CONDITION) }, Modifier.fillMaxWidth().height(50.dp)) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, null); Text("Back to patient details", Modifier.padding(start = 8.dp)) }
    }
}

@Composable
private fun TripConfirmationScreen(state: TripUiState, vm: TripViewModel, start: () -> Unit) {
    ScreenContainer {
        SetupProgress(3, "Confirmation")
        ScreenHeading("Confirm emergency route", "Review every detail before starting continuous GPS transmission.")
        MessageBanner(state.message)
        DetailCard("Route summary", listOf(
            "Ambulance" to state.ambulanceId,
            "Medical priority" to priorityLabel(state.priority),
            "Condition" to (state.condition?.label ?: "Not selected"),
            "Destination" to state.destination,
            "GPS" to "Permission checked on start",
            "MQTT" to "Connects on start",
        ))
        WarningBanner("Driver confirmation required", "Starting this route enables a foreground GPS service and transmits operational data every 1–2 seconds.")
        PrimaryActionButton("START EMERGENCY ROUTE", start)
        OutlinedButton({ vm.backTo(AppScreen.DESTINATION) }, Modifier.fillMaxWidth().height(50.dp)) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, null); Text("Edit destination", Modifier.padding(start = 8.dp)) }
    }
}

@Composable
private fun ActiveEmergencyScreen(state: TripUiState, vm: TripViewModel) {
    val elapsed by produceState(initialValue = 0L, state.startTime) {
        while (true) { value = state.startTime?.let { Duration.between(it, Instant.now()).seconds.coerceAtLeast(0) } ?: 0; delay(1000) }
    }
    val stage = emergencyStage(state)
    val statusMessage = if (stage < 0) "Waiting for precise GPS" else listOf(
        "GPS transmission active", "Approaching ${state.detectedApproach.lowercase().replaceFirstChar(Char::uppercase)} side", "Priority request submitted",
        "Request validated — wait for signal confirmation", "${state.detectedApproach.lowercase().replaceFirstChar(Char::uppercase)} approach priority granted", "Junction cleared",
    ).getOrElse(stage) { "Junction status updating" }
    ScreenContainer {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("Emergency Active", style = MaterialTheme.typography.displaySmall)
                Text(statusMessage, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Surface(shape = MaterialTheme.shapes.small, color = priorityColour(state.priority).copy(alpha = .14f), border = BorderStroke(1.dp, priorityColour(state.priority))) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 9.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    Icon(Icons.Outlined.LocalHospital, null, tint = priorityColour(state.priority), modifier = Modifier.size(19.dp))
                    Text(priorityLabel(state.priority), fontWeight = FontWeight.SemiBold, color = priorityColour(state.priority))
                }
            }
        }
        val mqttLost = state.mqttStatus.contains("error", true) || state.mqttStatus.contains("disconnected", true) || state.mqttStatus.contains("reconnecting", true)
        val gpsLost = listOf("denied", "unavailable", "inaccurate", "lost").any { state.gpsStatus.contains(it, true) }
        if (mqttLost || gpsLost) WarningBanner(
            if (mqttLost) "MQTT connection interrupted" else "GPS requires attention",
            if (mqttLost) "Last known signal status is retained. No priority confirmation will be inferred while offline." else "${state.gpsStatus}. Move to an open area and confirm precise-location permission.",
            onRetry = vm::retryConnections,
        )
        if (state.gpsStatus.contains("acquiring", true)) LoadingState("Acquiring a precise GPS fix. MQTT remains connected independently.")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            LiveMetricCard("Distance to junction", state.distanceMetres?.let { "%.0f m".format(it) } ?: "—", Modifier.weight(1f), state.nextJunction)
            LiveMetricCard("Estimated arrival", state.distanceMetres?.let { distance -> if (state.speedMps > 0.5f) "%.0f s".format(distance / state.speedMps) else "—" } ?: "—", Modifier.weight(1f), "Live estimate")
            LiveMetricCard("Trip elapsed", "%02d:%02d".format(elapsed / 60, elapsed % 60), Modifier.weight(1f), "mm:ss")
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ConnectionBadge("GPS", state.gpsStatus, Modifier.weight(1f))
            ConnectionBadge("MQTT", state.mqttStatus, Modifier.weight(1f))
        }
        BoxWithConstraints {
            if (maxWidth > 680.dp) {
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.Top) {
                    EmergencyStatusCard(EMERGENCY_STAGES, stage, Modifier.weight(1f))
                    DetailCard("Live route status", activeDetails(state), Modifier.weight(1f))
                }
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    EmergencyStatusCard(EMERGENCY_STAGES, stage)
                    DetailCard("Live route status", activeDetails(state))
                }
            }
        }
        PrimaryActionButton("View live GPS and connection", vm::showLiveGps)
        OutlinedButton(vm::requestDelivery, Modifier.fillMaxWidth().height(52.dp)) { Icon(Icons.Outlined.CheckCircle, null); Text("Complete Trip", Modifier.padding(start = 8.dp)) }
        DangerActionButton("Cancel Emergency", vm::requestCancel)
    }
}

private val EMERGENCY_STAGES = listOf("GPS ACTIVE", "JUNCTION DETECTED", "REQUEST SENT", "REQUEST VALIDATED", "PRIORITY GRANTED", "JUNCTION CLEARED")

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
        !state.mqttStatus.equals("Connected", true) -> "Confirmation unavailable offline"
        emergencyStage(state) >= 4 -> "Confirmed by junction"
        else -> "Not yet confirmed"
    },
    "Current speed" to "%.1f m/s".format(state.speedMps),
    "GPS accuracy" to (state.accuracyMetres?.let { "%.1f m".format(it) } ?: "—"),
    "Destination" to state.destination,
)

@Composable
private fun LiveGpsScreen(state: TripUiState, vm: TripViewModel) {
    ScreenContainer {
        ScreenHeading("Live GPS & connection", "Operational values for the active emergency trip.")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ConnectionBadge("GPS", state.gpsStatus, Modifier.weight(1f))
            ConnectionBadge("MQTT", state.mqttStatus, Modifier.weight(1f))
        }
        if (!state.gpsStatus.equals("Live", true)) WarningBanner("Waiting for reliable positioning", "${state.gpsStatus}. The last known values remain visible and no false priority status is shown.", onRetry = vm::retryConnections)
        DetailCard("GPS telemetry", listOf(
            "Trip ID" to state.tripId,
            "Latitude" to (state.latitude?.let { "%.6f".format(it) } ?: "—"),
            "Longitude" to (state.longitude?.let { "%.6f".format(it) } ?: "—"),
            "Accuracy" to (state.accuracyMetres?.let { "%.1f m".format(it) } ?: "—"),
            "Speed" to "%.1f m/s".format(state.speedMps),
            "Heading" to "%.0f°".format(state.headingDegrees),
            "Broker" to "${BuildConfig.MQTT_HOST}:${BuildConfig.MQTT_PORT}",
        ))
        PrimaryActionButton("Back to emergency route", vm::showEmergency)
    }
}

@Composable
private fun DetailCard(title: String, rows: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    Card(modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)) {
        Column(Modifier.fillMaxWidth().padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(11.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            rows.forEachIndexed { index, (label, value) ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
                    Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.End, modifier = Modifier.weight(1.25f))
                }
                if (index < rows.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = .5f))
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
