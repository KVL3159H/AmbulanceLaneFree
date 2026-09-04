package org.lifelane.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { LifeLaneApp() }
    }
}

private val LifeLaneColors = androidx.compose.material3.darkColorScheme(
    primary = Color(0xFF38BDF8), secondary = Color(0xFF22C55E),
    background = Color(0xFF0F172A), surface = Color(0xFF1E293B),
    onPrimary = Color(0xFF082F49), onBackground = Color(0xFFE2E8F0),
    onSurface = Color(0xFFF8FAFC), error = Color(0xFFF87171),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LifeLaneApp(vm: TripViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        if (grants[Manifest.permission.ACCESS_FINE_LOCATION] == true || grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true) {
            vm.startTrip()
        }
    }
    val requestAndStart = {
        val fine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (fine || coarse) vm.startTrip()
        else {
            val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            if (Build.VERSION.SDK_INT >= 33) permissions += Manifest.permission.POST_NOTIFICATIONS
            permissionLauncher.launch(permissions.toTypedArray())
        }
    }
    MaterialTheme(colorScheme = LifeLaneColors) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("LifeLane", fontWeight = FontWeight.Bold, fontSize = 22.sp)
                            Text("Ambulance emergency trip", fontSize = 12.sp)
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = Color(0xFF0B1220)),
                )
            },
        ) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
                state.message?.let {
                    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF334155))) {
                        Text(it, Modifier.padding(12.dp), color = Color(0xFFFBBF24))
                    }
                    Spacer(Modifier.height(10.dp))
                }
                when (state.screen) {
                    AppScreen.LOGIN -> LoginScreen(vm)
                    AppScreen.AMBULANCE -> AmbulanceScreen(vm)
                    AppScreen.PICKUP -> ConfirmationScreen(
                        "Patient picked up?", "Confirm only after the patient is in the ambulance.",
                        "Confirm pickup", vm::confirmPickup,
                    )
                    AppScreen.PRIORITY -> PriorityScreen(vm)
                    AppScreen.CONDITION -> ConditionScreen(vm)
                    AppScreen.DESTINATION -> DestinationScreen(state, vm, requestAndStart)
                    AppScreen.EMERGENCY -> EmergencyScreen(state, vm)
                    AppScreen.LIVE_GPS -> LiveGpsScreen(state, vm)
                    AppScreen.DELIVER_CONFIRM -> ConfirmationScreen(
                        "Patient delivered?", "This stops the foreground GPS service and emergency transmission.",
                        "Confirm delivery", { vm.stopTrip(cancelled = false) }, vm::dismissConfirmation,
                    )
                    AppScreen.CANCEL_CONFIRM -> ConfirmationScreen(
                        "Cancel emergency?", "The junction will be notified and GPS transmission will stop.",
                        "Cancel emergency", { vm.stopTrip(cancelled = true) }, vm::dismissConfirmation,
                    )
                }
            }
        }
    }
}

@Composable
private fun ScreenTitle(title: String, subtitle: String) {
    Text(title, fontSize = 25.sp, fontWeight = FontWeight.Bold)
    Text(subtitle, color = Color(0xFF94A3B8))
    Spacer(Modifier.height(20.dp))
}

@Composable
private fun LoginScreen(vm: TripViewModel) {
    var driverId by remember { mutableStateOf("") }
    Column {
        ScreenTitle("Driver login", "Prototype local sign-in; no password is stored on this device.")
        OutlinedTextField(driverId, { driverId = it }, label = { Text("Driver ID") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        Button({ vm.login(driverId) }, Modifier.fillMaxWidth()) { Text("Continue") }
    }
}

@Composable
private fun AmbulanceScreen(vm: TripViewModel) {
    Column {
        ScreenTitle("Select ambulance", "Choose the authorized vehicle for this shift.")
        listOf("AMB-001", "AMB-002", "AMB-003", "AMB-004").forEach { id ->
            OutlinedButton({ vm.selectAmbulance(id) }, Modifier.fillMaxWidth().padding(vertical = 5.dp)) { Text(id) }
        }
    }
}

@Composable
private fun PriorityScreen(vm: TripViewModel) {
    Column {
        ScreenTitle("Patient priority", "Select the reported urgency level; this is not a diagnosis.")
        listOf(
            Triple(PatientPriority.RED, "RED — Critical", Color(0xFFDC2626)),
            Triple(PatientPriority.YELLOW, "YELLOW — Serious", Color(0xFFF59E0B)),
            Triple(PatientPriority.GREEN, "GREEN — Stable", Color(0xFF16A34A)),
        ).forEach { (value, label, colour) ->
            Button(
                { vm.setPriority(value) }, Modifier.fillMaxWidth().padding(vertical = 6.dp),
                colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = colour),
            ) { Text(label, color = Color.White) }
        }
    }
}

@Composable
private fun ConditionScreen(vm: TripViewModel) {
    Column(Modifier.fillMaxSize()) {
        ScreenTitle("Reported condition", "Store only a category—never the patient's name.")
        LazyColumn(contentPadding = PaddingValues(bottom = 16.dp)) {
            items(PatientCondition.entries) { condition ->
                OutlinedButton({ vm.setCondition(condition) }, Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                    Text(condition.label)
                }
            }
        }
    }
}

@Composable
private fun DestinationScreen(state: TripUiState, vm: TripViewModel, start: () -> Unit) {
    var destination by remember(state.destination) { mutableStateOf(state.destination) }
    Column {
        ScreenTitle("Destination hospital", "The Raspberry Pi uses only this trip/case information.")
        OutlinedTextField(
            destination, { destination = it; vm.setDestination(it) },
            label = { Text("Hospital name") }, modifier = Modifier.fillMaxWidth(), singleLine = true,
        )
        Spacer(Modifier.height(16.dp))
        Button(start, Modifier.fillMaxWidth(), enabled = destination.isNotBlank()) { Text("Start emergency trip") }
        Text("Starting enables a foreground location service and a permanent notification.", Modifier.padding(top = 12.dp), color = Color(0xFF94A3B8))
    }
}

@Composable
private fun EmergencyScreen(state: TripUiState, vm: TripViewModel) {
    Column(Modifier.verticalScroll(rememberScrollState())) {
        ScreenTitle("Emergency trip active", "GPS packets are transmitted every 1–2 seconds via MQTT.")
        StatusCard(state)
        Spacer(Modifier.height(12.dp))
        Button(vm::showLiveGps, Modifier.fillMaxWidth()) { Text("Live GPS and connection details") }
        OutlinedButton(vm::requestDelivery, Modifier.fillMaxWidth().padding(top = 8.dp)) { Text("Stop trip — patient delivered") }
        OutlinedButton(vm::requestCancel, Modifier.fillMaxWidth().padding(top = 8.dp)) { Text("Cancel emergency") }
    }
}

@Composable
private fun StatusCard(state: TripUiState) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            InfoRow("Ambulance", state.ambulanceId)
            InfoRow("Patient priority", state.priority.name)
            InfoRow("Reported condition", state.condition.label)
            InfoRow("Destination", state.destination)
            InfoRow("GPS status", state.gpsStatus)
            InfoRow("MQTT status", state.mqttStatus)
            InfoRow("Current speed", "%.1f m/s".format(state.speedMps))
            InfoRow("Next junction", state.nextJunction)
            InfoRow("Distance", state.distanceMetres?.let { "%.1f m".format(it) } ?: "—")
            InfoRow("Detected approach", state.detectedApproach)
            InfoRow("Priority request", state.requestStatus)
            InfoRow("Signal status", state.signalStatus)
            InfoRow("Start time", state.startTime?.atZone(ZoneId.systemDefault())?.format(DateTimeFormatter.ofPattern("HH:mm:ss")) ?: "—")
        }
    }
}

@Composable
private fun LiveGpsScreen(state: TripUiState, vm: TripViewModel) {
    Column {
        ScreenTitle("Live GPS & connection", "Raw operational values for the active trip.")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                InfoRow("Trip ID", state.tripId)
                InfoRow("Latitude", state.latitude?.let { "%.6f".format(it) } ?: "—")
                InfoRow("Longitude", state.longitude?.let { "%.6f".format(it) } ?: "—")
                InfoRow("Accuracy", state.accuracyMetres?.let { "%.1f m".format(it) } ?: "—")
                InfoRow("Speed", "%.1f m/s".format(state.speedMps))
                InfoRow("Heading", "%.0f°".format(state.headingDegrees))
                InfoRow("GPS", state.gpsStatus)
                InfoRow("MQTT", state.mqttStatus)
                InfoRow("Broker", "${BuildConfig.MQTT_HOST}:${BuildConfig.MQTT_PORT}")
            }
        }
        Spacer(Modifier.height(16.dp))
        Button(vm::showEmergency, Modifier.fillMaxWidth()) { Text("Back to emergency trip") }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
        Text(label, color = Color(0xFF94A3B8), modifier = Modifier.weight(1f))
        Text(value, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1.25f))
    }
}

@Composable
private fun ConfirmationScreen(title: String, detail: String, actionLabel: String, confirm: () -> Unit, cancel: (() -> Unit)? = null) {
    Column {
        ScreenTitle(title, detail)
        Button(confirm, Modifier.fillMaxWidth()) { Text(actionLabel) }
        cancel?.let { OutlinedButton(it, Modifier.fillMaxWidth().padding(top = 10.dp)) { Text("Go back") } }
    }
}
