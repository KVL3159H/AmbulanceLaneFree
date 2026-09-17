package org.lifelane.mobile

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.DirectionsCar
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.outlined.LocalHospital
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Map
import androidx.compose.material.icons.outlined.NearMe
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.CurrentLocationRequest
import com.google.android.gms.location.Priority
import java.time.Duration
import java.time.Instant
import org.lifelane.mobile.ui.components.LiveRouteMapView
import org.lifelane.mobile.ui.theme.LifeLaneTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { LifeLaneApp() }
    }
}

@Composable
fun LifeLaneApp(vm: TripViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        val granted = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true || grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (granted) {
            requestFreshLocation(context, vm)
            if (state.screen == AppScreen.CONFIRM) vm.startTrip()
        } else vm.reportPermissionDenied()
    }
    val requestLocation: () -> Unit = {
        val hasPermission = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (hasPermission) {
            requestFreshLocation(context, vm)
        } else permissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        Unit
    }
    val startTrip: () -> Unit = {
        val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) permissions += Manifest.permission.POST_NOTIFICATIONS
        val hasPermission = permissions.take(2).any { ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED }
        if (hasPermission) vm.startTrip() else permissionLauncher.launch(permissions.toTypedArray())
    }

    LaunchedEffect(state.screen) {
        val alreadyGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (state.screen != AppScreen.SPLASH && alreadyGranted) requestLocation()
    }

    LifeLaneTheme(state.themeMode) {
        if (state.screen == AppScreen.SPLASH) {
            LaunchScreen(vm::finishSplash)
        } else {
            val shell = state.screen in setOf(AppScreen.HOME, AppScreen.MAP, AppScreen.TRIPS, AppScreen.SETTINGS)
            Scaffold(
                topBar = { CommandHeader(screenTitle(state.screen), state) },
                bottomBar = { if (shell) CommandNavigation(state.screen, vm) },
                containerColor = MaterialTheme.colorScheme.background,
            ) { insets ->
                Box(Modifier.fillMaxSize().padding(insets)) {
                    when (state.screen) {
                        AppScreen.LOGIN -> SignInScreen(state, vm)
                        AppScreen.AMBULANCE -> AmbulanceScreen(state, vm)
                        AppScreen.HOME -> HomeScreen(state, vm)
                        AppScreen.MAP -> MapScreen(state, vm, requestLocation)
                        AppScreen.TRIPS -> TripsScreen(state)
                        AppScreen.SETTINGS -> SettingsScreen(state, vm)
                        AppScreen.PATIENT, AppScreen.PRIORITY, AppScreen.CONDITION -> PatientScreen(state, vm)
                        AppScreen.DESTINATION -> HospitalScreen(state, vm, requestLocation)
                        AppScreen.CONFIRM -> ReviewScreen(state, vm, startTrip)
                        AppScreen.EMERGENCY, AppScreen.LIVE_GPS -> ActiveTripScreen(state, vm)
                        AppScreen.DELIVER_CONFIRM -> CompletionScreen(state, vm)
                        AppScreen.CANCEL_CONFIRM -> CancellationScreen(state, vm)
                        AppScreen.TRIP_SUMMARY -> SummaryScreen(state, vm)
                        AppScreen.SPLASH -> Unit
                    }
                }
            }
        }
    }
}

@SuppressLint("MissingPermission")
private fun requestFreshLocation(context: Context, vm: TripViewModel) {
    val manager = context.getSystemService(LocationManager::class.java)
    val locationEnabled = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) manager.isLocationEnabled
    else manager.isProviderEnabled(LocationManager.GPS_PROVIDER) || manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
    if (!locationEnabled) {
        vm.reportLocationUnavailable("Turn on your phone's Location service, then tap Retry.")
        return
    }
    vm.beginLocationLookup()
    val client = LocationServices.getFusedLocationProviderClient(context)
    val request = CurrentLocationRequest.Builder()
        .setPriority(Priority.PRIORITY_HIGH_ACCURACY)
        .setMaxUpdateAgeMillis(5_000L)
        .setDurationMillis(15_000L)
        .build()
    client.getCurrentLocation(request, null)
        .addOnSuccessListener { location ->
            if (location != null) {
                vm.updatePreTripLocation(location.latitude, location.longitude, location.accuracy, location.time)
            } else {
                client.lastLocation
                    .addOnSuccessListener { last ->
                        if (last != null) vm.updatePreTripLocation(last.latitude, last.longitude, last.accuracy, last.time)
                        else vm.reportLocationUnavailable("No location fix was received. Move outdoors and tap Retry.")
                    }
                    .addOnFailureListener { vm.reportLocationUnavailable("Location could not be read. Check Google Play Services and try again.") }
            }
        }
        .addOnFailureListener { error ->
            vm.reportLocationUnavailable(error.message ?: "Location request failed. Check Location services and try again.")
        }
}

@Composable
private fun LaunchScreen(onDone: () -> Unit) {
    LaunchedEffect(Unit) { kotlinx.coroutines.delay(550); onDone() }
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            BrandMark(72)
            Text("LifeLane", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            Text("Emergency mobility research prototype", color = MaterialTheme.colorScheme.onSurfaceVariant)
            CircularProgressIndicator(Modifier.size(28.dp), strokeWidth = 3.dp)
        }
    }
}

@Composable
private fun CommandHeader(title: String, state: TripUiState) {
    Surface(color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Row(
            Modifier.fillMaxWidth().statusBarsPadding().height(64.dp).padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            BrandMark(40)
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, maxLines = 1)
                Text("LifeLane · Laboratory network", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (state.emergencyActive) StatusTag("Trip active", MaterialTheme.colorScheme.error, Icons.Outlined.NearMe)
        }
    }
}

@Composable
private fun BrandMark(size: Int) {
    Box(
        Modifier.size(size.dp).background(MaterialTheme.colorScheme.primary, RoundedCornerShape(13.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(Icons.Outlined.NearMe, "LifeLane", tint = Color.White, modifier = Modifier.size((size * .55f).dp))
    }
}

@Composable
private fun CommandNavigation(current: AppScreen, vm: TripViewModel) {
    val items = listOf(
        Triple(AppScreen.HOME, "Home", Icons.Outlined.Home),
        Triple(AppScreen.MAP, "Map", Icons.Outlined.Map),
        Triple(AppScreen.TRIPS, "Trips", Icons.Outlined.History),
        Triple(AppScreen.SETTINGS, "Settings", Icons.Outlined.Settings),
    )
    NavigationBar(Modifier.navigationBarsPadding(), containerColor = MaterialTheme.colorScheme.surface) {
        items.forEach { (screen, label, icon) ->
            NavigationBarItem(
                selected = current == screen,
                onClick = { when (screen) { AppScreen.HOME -> vm.openHome(); AppScreen.MAP -> vm.openMap(); AppScreen.TRIPS -> vm.openTrips(); else -> vm.openSettings() } },
                icon = { Icon(icon, null) }, label = { Text(label) },
                colors = NavigationBarItemDefaults.colors(indicatorColor = MaterialTheme.colorScheme.primaryContainer),
            )
        }
    }
}

@Composable
private fun AdaptiveScreen(content: @Composable ColumnScope.() -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val horizontal = when { maxWidth < 380.dp -> 12.dp; maxWidth < 700.dp -> 16.dp; else -> 28.dp }
        val maximum = if (maxWidth < 700.dp) maxWidth else 1080.dp
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier.widthIn(max = maximum).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal, 18.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp), content = content,
            )
        }
    }
}

@Composable
private fun PageIntro(title: String, description: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(description, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun SignInScreen(state: TripUiState, vm: TripViewModel) {
    var driver by rememberSaveable { mutableStateOf(state.driverId) }
    var pin by rememberSaveable { mutableStateOf("") }
    var rememberVehicle by rememberSaveable { mutableStateOf(state.rememberAmbulance) }
    var showPin by rememberSaveable { mutableStateOf(false) }
    AdaptiveScreen {
        PageIntro("Driver sign-in", "Sign in to operate an authorized ambulance.")
        Panel {
            OutlinedTextField(driver, { driver = it }, Modifier.fillMaxWidth(), label = { Text("Driver ID") }, leadingIcon = { Icon(Icons.Outlined.Person, null) }, singleLine = true)
            OutlinedTextField(
                pin, { pin = it.filter(Char::isDigit).take(8) }, Modifier.fillMaxWidth(), label = { Text("Secure PIN") },
                leadingIcon = { Icon(Icons.Outlined.Lock, null) }, singleLine = true,
                visualTransformation = if (showPin) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = { IconButton({ showPin = !showPin }) { Icon(if (showPin) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility, if (showPin) "Hide PIN" else "Show PIN") } },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            )
            state.message?.let { InlineError(it) }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(rememberVehicle, { rememberVehicle = it })
                Text("Remember authorized ambulance", Modifier.clickable { rememberVehicle = !rememberVehicle }.padding(vertical = 12.dp))
            }
            CommandButton("Sign in") { vm.login(driver, pin, rememberVehicle) }
            Text("Controller connectivity is checked when a trip starts.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun AmbulanceScreen(state: TripUiState, vm: TripViewModel) {
    AdaptiveScreen {
        PageIntro("Select ambulance", "Choose the vehicle authorized for this research session.")
        val selected = state.ambulanceId == "AMB-001"
        Panel(
            modifier = Modifier.clickable(role = Role.RadioButton) { vm.selectAmbulance("AMB-001") },
            border = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Icon(Icons.Outlined.DirectionsCar, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(32.dp))
                Column(Modifier.weight(1f)) {
                    Text("AMB-001", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("Prototype fleet · Registration not configured", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("Authorization configured", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
                }
                if (selected) Icon(Icons.Outlined.CheckCircle, "Selected", tint = MaterialTheme.colorScheme.primary)
            }
        }
        state.message?.let { InlineError(it) }
        CommandButton("Continue", state.ambulanceId.isNotBlank(), vm::continueWithAmbulance)
    }
}

@Composable
private fun HomeScreen(state: TripUiState, vm: TripViewModel) {
    AdaptiveScreen {
        PageIntro("Ready for service", "Everything needed for an emergency trip, visible at a glance.")
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer), shape = RoundedCornerShape(22.dp)) {
            Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                StatusTag("Emergency mobility", MaterialTheme.colorScheme.primary, Icons.Outlined.NearMe)
                Text("Start emergency trip", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text("Create a priority route to a receiving hospital.", color = MaterialTheme.colorScheme.onPrimaryContainer)
                CommandButton("Start trip", true, vm::startTripSetup)
            }
        }
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            if (maxWidth >= 700.dp) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricPanel("Ambulance", state.ambulanceId.ifBlank { "Not selected" }, Icons.Outlined.DirectionsCar)
                        MetricPanel("Control", state.mqttState.label(), Icons.Outlined.NearMe)
                    }
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        MetricPanel("GPS", state.gpsState.label(), Icons.Outlined.LocationOn)
                        MetricPanel("Hospitals", if (state.hospitalDataIsDemo) "Demo data" else "Live lookup", Icons.Outlined.LocalHospital)
                    }
                }
            } else {
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    MetricPanel("Ambulance", state.ambulanceId.ifBlank { "Not selected" }, Icons.Outlined.DirectionsCar)
                    MetricPanel("GPS", state.gpsState.label(), Icons.Outlined.LocationOn)
                    MetricPanel("Control", state.mqttState.label(), Icons.Outlined.NearMe)
                    MetricPanel("Hospitals", if (state.hospitalDataIsDemo) "Demo data" else "Live lookup", Icons.Outlined.LocalHospital)
                }
            }
        }
    }
}

@Composable
private fun MapScreen(state: TripUiState, vm: TripViewModel, requestLocation: () -> Unit) {
    Column(Modifier.fillMaxSize()) {
        if (state.latitude == null) {
            InlineBanner(
                title = if (state.gpsState == GpsState.LOCATING) "Finding your location" else "Location is not ready",
                detail = state.message ?: "Turn on precise Location, move to an open area, then retry.",
                action = requestLocation,
            )
        }
        RouteMap(state, Modifier.fillMaxWidth().weight(1f), vm)
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusTag("GPS: ${state.gpsState.label()}", state.gpsState.colour(), Icons.Outlined.LocationOn, Modifier.weight(1f))
            StatusTag("Control: ${state.mqttState.label()}", state.mqttState.colour(), Icons.Outlined.NearMe, Modifier.weight(1f))
        }
    }
}

@Composable
private fun PatientScreen(state: TripUiState, vm: TripViewModel) {
    AdaptiveScreen {
        StepHeader(1, "Patient information")
        PageIntro("Patient information", "Select only the minimum operational category. Do not enter a patient name.")
        Text("Medical priority", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        PatientPriority.entries.forEach { priority ->
            val selected = state.priority == priority
            Panel(Modifier.clickable(role = Role.RadioButton) { vm.setPriority(priority) }, if (selected) priority.colour() else MaterialTheme.colorScheme.outlineVariant) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Box(Modifier.size(12.dp).background(priority.colour(), CircleShape))
                    Column(Modifier.weight(1f)) { Text(priority.label(), fontWeight = FontWeight.Bold); Text(priority.description(), color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    if (selected) Icon(Icons.Outlined.CheckCircle, "Selected", tint = priority.colour())
                }
            }
        }
        Text("Reported condition", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        PatientCondition.entries.chunked(2).forEach { conditions ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                conditions.forEach { condition ->
                    FilterChip(state.condition == condition, { vm.setCondition(condition) }, { Text(condition.label) }, Modifier.weight(1f))
                }
                if (conditions.size == 1) Spacer(Modifier.weight(1f))
            }
        }
        state.message?.let { InlineError(it) }
        CommandButton("Continue", state.priority != null && state.condition != null, vm::continueFromPatient)
        TextButtonRow("Change ambulance", vm::changeAmbulance)
    }
}

@Composable
private fun HospitalScreen(state: TripUiState, vm: TripViewModel, requestLocation: () -> Unit) {
    var filter by rememberSaveable { mutableStateOf("Nearest") }
    val query = state.hospitalSearchQuery.trim()
    val hospitals = remember(state.nearbyHospitals, query, filter) {
        state.nearbyHospitals.filter { hospital ->
            val text = "${hospital.name} ${hospital.specialty} ${hospital.address}".lowercase()
            (query.isBlank() || query.lowercase() in text) && when (filter) {
                "Trauma" -> "trauma" in text
                "Cardiac" -> "cardiac" in text || "heart" in text
                "Maternity" -> "maternity" in text || "women" in text || "obstetric" in text
                "Government" -> "government" in text || "govt" in text
                else -> true
            }
        }
    }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val tablet = maxWidth >= 760.dp
        if (tablet) {
            Row(Modifier.fillMaxSize().padding(20.dp), horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                RouteMap(state, Modifier.weight(1.25f).fillMaxHeight(), vm)
                HospitalList(state, hospitals, filter, { filter = it }, vm, requestLocation, Modifier.weight(.9f).fillMaxHeight())
            }
        } else {
            Column(Modifier.fillMaxSize()) {
                RouteMap(state, Modifier.fillMaxWidth().weight(.48f), vm)
                HospitalList(state, hospitals, filter, { filter = it }, vm, requestLocation, Modifier.fillMaxWidth().weight(.52f))
            }
        }
    }
}

@Composable
private fun HospitalList(state: TripUiState, hospitals: List<HospitalDestination>, filter: String, setFilter: (String) -> Unit, vm: TripViewModel, requestLocation: () -> Unit, modifier: Modifier) {
    Column(modifier.verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        StepHeader(2, "Destination hospital")
        if (state.latitude == null) InlineBanner("Location required", "Enable precise foreground location to calculate hospital distances.", requestLocation)
        if (state.hospitalDataIsDemo) InlineBanner("Demo hospital data", "Configured Rajapalayam samples—not live availability.")
        OutlinedTextField(state.hospitalSearchQuery, vm::setHospitalSearchQuery, Modifier.fillMaxWidth(), placeholder = { Text("Search hospitals") }, leadingIcon = { Icon(Icons.Outlined.Search, null) }, trailingIcon = { IconButton(vm::refreshHospitals) { Icon(Icons.Outlined.Refresh, "Refresh") } }, singleLine = true)
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("Nearest", "Trauma", "Cardiac", "Maternity", "Government").forEach { option -> FilterChip(filter == option, { setFilter(option) }, { Text(option) }) }
        }
        if (state.hospitalsLoading) CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
        state.hospitalsError?.let { InlineBanner("Hospital data unavailable", it, vm::refreshHospitals) }
        hospitals.forEach { hospital -> HospitalRow(hospital, state.selectedHospital?.id == hospital.id) { vm.selectHospital(hospital) } }
        if (!state.hospitalsLoading && hospitals.isEmpty()) Text("No matching hospitals. Adjust the filter or retry the lookup.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        CommandButton("Review route", state.selectedHospital != null, vm::reviewTrip)
        TextButtonRow("Edit patient information") { vm.backTo(AppScreen.PATIENT) }
    }
}

@Composable
private fun HospitalRow(hospital: HospitalDestination, selected: Boolean, onSelect: () -> Unit) {
    Panel(Modifier.clickable(onClick = onSelect), if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant) {
        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(Icons.Outlined.LocalHospital, null, tint = MaterialTheme.colorScheme.secondary)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(hospital.name, fontWeight = FontWeight.Bold)
                Text(hospital.specialty, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.secondary)
                Text(hospital.address, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("${hospital.supportedJunctions} supported junction${if (hospital.supportedJunctions == 1) "" else "s"}", style = MaterialTheme.typography.labelSmall)
            }
            Text(if (hospital.distanceKm > 0) formatDistance(hospital.distanceKm * 1000) else "Unavailable", style = MaterialTheme.typography.labelMedium)
        }
    }
}

@Composable
private fun ReviewScreen(state: TripUiState, vm: TripViewModel, start: () -> Unit) {
    AdaptiveScreen {
        StepHeader(3, "Route review")
        PageIntro("Review the route", "Confirm the operational details before starting location transmission.")
        RouteMap(state, Modifier.fillMaxWidth().height(280.dp), vm)
        DetailPanel("Trip details", listOf(
            "Ambulance" to state.ambulanceId,
            "Medical priority" to state.priority.label(),
            "Condition" to (state.condition?.label ?: "Not selected"),
            "Destination" to state.destination,
            "Distance" to (state.selectedHospital?.distanceKm?.takeIf { it > 0 }?.times(1000)?.let(::formatDistance) ?: "Unavailable"),
            "GPS" to state.gpsState.label(),
            "Control" to state.mqttState.label(),
        ))
        state.message?.let { InlineError(it) }
        CommandButton("Start emergency trip", true, start)
        TextButtonRow("Change hospital") { vm.backTo(AppScreen.DESTINATION) }
    }
}

@Composable
private fun ActiveTripScreen(state: TripUiState, vm: TripViewModel) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val compactHeight = maxHeight < 650.dp
        val sheetMaxHeight = maxHeight * .58f
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Column(Modifier.weight(1f)) {
                    Text("Emergency trip active", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(state.destination, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                }
                StatusTag(state.priority.label(), state.priority.colour(), Icons.Outlined.LocalHospital)
            }
            RouteMap(state, Modifier.fillMaxWidth().weight(1f), vm)
            Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 10.dp, shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp)) {
                Column(
                    Modifier.fillMaxWidth().heightIn(max = sheetMaxHeight).verticalScroll(rememberScrollState()).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(if (compactHeight) 8.dp else 12.dp),
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        StatusTag("GPS ${state.gpsState.label()}", state.gpsState.colour(), Icons.Outlined.LocationOn, Modifier.weight(1f))
                        StatusTag("Control ${state.mqttState.label()}", state.mqttState.colour(), Icons.Outlined.NearMe, Modifier.weight(1f))
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column { Text("Next junction", style = MaterialTheme.typography.labelSmall); Text(state.nextJunction, fontWeight = FontWeight.Bold) }
                        Column(horizontalAlignment = Alignment.End) { Text("Distance", style = MaterialTheme.typography.labelSmall); Text(state.distanceMetres?.let(::formatDistance) ?: "—", fontWeight = FontWeight.Bold) }
                    }
                    JunctionTimeline(state.junctionState)
                    Text("Approach: ${state.detectedApproach} · GPS accuracy: ${state.accuracyMetres?.toInt()?.let { "$it m" } ?: "Unavailable"}", style = MaterialTheme.typography.bodySmall)
                    Text("Queue: ${state.queuePosition?.toString() ?: "—"} · Cleared junctions: ${state.clearedJunctionCount}", style = MaterialTheme.typography.bodySmall)
                    Text("Raspberry Pi: ${if(state.acknowledgement == null) "Awaiting authenticated acknowledgement" else state.requestStatus}", style = MaterialTheme.typography.bodySmall)
                    if (state.mqttState != ConnectionState.CONNECTED) InlineBanner("Control connection interrupted", "Last confirmed state retained. Signal priority is not confirmed.", vm::retryConnections)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(vm::requestCancel, Modifier.weight(1f).height(52.dp), colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Cancel") }
                        Button(vm::requestDelivery, Modifier.weight(1f).height(52.dp)) { Text("Complete trip") }
                    }
                }
            }
        }
    }
}

@Composable
private fun CompletionScreen(state: TripUiState, vm: TripViewModel) {
    AdaptiveScreen {
        PageIntro("Complete trip?", "Confirm only after arriving at the receiving hospital.")
        DetailPanel("Final controller state", listOf("Trip" to state.tripId, "Destination" to state.destination, "Junction state" to state.junctionStage.label()))
        CommandButton("Complete trip") { vm.stopTrip(false) }
        TextButtonRow("Return to live route", vm::dismissConfirmation)
    }
}

@Composable
private fun CancellationScreen(state: TripUiState, vm: TripViewModel) {
    AdaptiveScreen {
        PageIntro("Cancel emergency trip?", "Cancellation remains available even when connectivity is degraded.")
        InlineBanner("Controller confirmation required", "A cancellation request is sent to pending junctions; LifeLane does not treat an unacknowledged request as confirmed.")
        OutlinedTextField(state.cancellationReason, vm::setCancellationReason, Modifier.fillMaxWidth(), label = { Text("Operational reason") }, supportingText = { Text("Required. Do not enter patient-identifying information.") }, minLines = 2)
        Button(
            { vm.stopTrip(true) }, Modifier.fillMaxWidth().height(54.dp), enabled = state.cancellationReason.isNotBlank(),
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
        ) { Text("Send cancellation request") }
        TextButtonRow("Keep trip active", vm::dismissConfirmation)
    }
}

@Composable
private fun TripsScreen(state: TripUiState) {
    AdaptiveScreen {
        PageIntro("Trip history", "Operational summaries without personal patient information.")
        if (state.recentTrips.isEmpty()) InlineBanner("No trip history", "Completed and cancelled journeys will appear here.")
        state.recentTrips.forEach { trip -> DetailPanel(trip.destination, listOf(
            "Date" to trip.startedAt.toString().replace('T', ' ').take(16), "Ambulance" to trip.ambulanceId,
            "Priority" to trip.urgency.label(), "Duration" to formatDuration(Duration.between(trip.startedAt, trip.endedAt).seconds),
            "Distance" to (trip.distanceMetres?.let(::formatDistance) ?: "Unavailable"), "Result" to if (trip.cancelled) "Cancelled" else "Completed",
        )) }
    }
}

@Composable
private fun SettingsScreen(state: TripUiState, vm: TripViewModel) {
    var pin by rememberSaveable { mutableStateOf("") }
    var brokerHost by rememberSaveable { mutableStateOf(vm.brokerHost()) }
    var brokerPort by rememberSaveable { mutableStateOf(vm.brokerPort()) }
    AdaptiveScreen {
        PageIntro("Settings", "Driver preferences and protected laboratory controls.")
        Text("Appearance", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(ThemeMode.LIGHT).forEach { mode -> FilterChip(state.themeMode == mode, { vm.setThemeMode(mode) }, { Text(mode.name.lowercase().replaceFirstChar(Char::titlecase)) }, leadingIcon = { Icon(if (mode == ThemeMode.DARK) Icons.Outlined.DarkMode else Icons.Outlined.LightMode, null, Modifier.size(18.dp)) }) }
        }
        DetailPanel("Device status", listOf("Location" to state.gpsState.label(), "Accuracy" to (state.accuracyMetres?.let { "${it.toInt()} m" } ?: "Unavailable"), "Control connection" to state.mqttState.label()))
        Text("Connect to Windows", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text("Use the same Wi-Fi as the PC. Copy its address from the desktop Settings page, then start a trip with Live mobile GPS enabled on the desktop.")
        OutlinedTextField(brokerHost, { brokerHost = it }, Modifier.fillMaxWidth(), label = { Text("PC address") }, singleLine = true)
        OutlinedTextField(brokerPort, { brokerPort = it }, Modifier.fillMaxWidth(), label = { Text("Port") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
        OutlinedButton({ vm.saveBroker(brokerHost, brokerPort) }, Modifier.fillMaxWidth().height(52.dp)) { Text("Save connection") }
        Text("Developer settings", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (!state.developerUnlocked) {
            OutlinedTextField(pin, { pin = it }, Modifier.fillMaxWidth(), label = { Text("Developer PIN") }, visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword))
            OutlinedButton({ vm.unlockDeveloperSettings(pin) }, Modifier.fillMaxWidth().height(52.dp)) { Text("Unlock") }
        } else Panel {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { Text("Demo hospital mode", fontWeight = FontWeight.Bold); Text("Clearly labeled Rajapalayam sample data", style = MaterialTheme.typography.bodySmall) }
                Switch(state.demoHospitalMode, vm::setDemoHospitalMode)
            }
            HorizontalDivider()
            Text("Map: ${state.mapError ?: "No reported error"}")
            Text("Acknowledgement: ${state.acknowledgement?.controllerState ?: "None received"}")
            Text("Connection: ${vm.brokerHost()}:${vm.brokerPort()}", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        state.message?.let { InlineError(it) }
    }
}

@Composable
private fun SummaryScreen(state: TripUiState, vm: TripViewModel) {
    AdaptiveScreen {
        val trip = state.completedTrip
        PageIntro(if (trip?.cancelled == true) "Trip cancelled" else "Trip complete", "Continuous GPS transmission and the foreground trip service have stopped.")
        if (trip != null) DetailPanel("Trip summary", listOf(
            "Ambulance" to trip.ambulanceId, "Destination" to trip.destination,
            "Duration" to formatDuration(Duration.between(trip.startedAt, trip.endedAt).seconds),
            "Distance" to (trip.distanceMetres?.let(::formatDistance) ?: "Unavailable"),
            "Junctions requested" to trip.junctionsRequested.toString(), "Junctions granted" to trip.junctionsGranted.toString(),
            "GPS interruptions" to trip.gpsInterruptions.toString(), "Network interruptions" to trip.networkInterruptions.toString(),
        ))
        CommandButton("Return home", true, vm::openHome)
    }
}

@Composable
private fun RouteMap(state: TripUiState, modifier: Modifier, vm: TripViewModel) {
    val darkMap = false
    LiveRouteMapView(
        ambulanceLat = state.latitude, ambulanceLon = state.longitude, headingDegrees = state.headingDegrees,
        speedMps = state.speedMps, ambulanceId = state.ambulanceId, destinationHospital = state.destination,
        destinationLat = state.destinationLat, destinationLon = state.destinationLon, signalStatus = state.signalStatus,
        detectedApproach = state.detectedApproach, distanceMetres = state.distanceMetres,
        isEmergencyActive = state.emergencyActive, darkTheme = darkMap,
        priorityConfirmed = state.junctionStage == JunctionStage.PRIORITY_GRANTED,
        modifier = modifier, accuracyMetres = state.accuracyMetres, onMapError = vm::reportMapError,
    )
}

@Composable
private fun Panel(modifier: Modifier = Modifier, border: Color = MaterialTheme.colorScheme.outlineVariant, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), border = BorderStroke(1.dp, border)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

@Composable
private fun MetricPanel(label: String, value: String, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    Panel { Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) { Icon(icon, null, tint = MaterialTheme.colorScheme.primary); Column { Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant); Text(value, fontWeight = FontWeight.Bold) } } }
}

@Composable
private fun DetailPanel(title: String, rows: List<Pair<String, String>>) {
    Panel { Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold); rows.forEachIndexed { index, row -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) { Text(row.first, Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant); Text(row.second, Modifier.weight(1f), fontWeight = FontWeight.SemiBold, textAlign = TextAlign.End) }; if (index < rows.lastIndex) HorizontalDivider() } }
}

@Composable
private fun CommandButton(label: String, enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick, Modifier.fillMaxWidth().height(54.dp), enabled = enabled, shape = RoundedCornerShape(14.dp)) { Text(label, fontWeight = FontWeight.Bold) }
}

@Composable
private fun TextButtonRow(label: String, onClick: () -> Unit) {
    OutlinedButton(onClick, Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(14.dp)) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, null); Spacer(Modifier.width(8.dp)); Text(label) }
}

@Composable
private fun StatusTag(label: String, colour: Color, icon: androidx.compose.ui.graphics.vector.ImageVector, modifier: Modifier = Modifier) {
    Surface(modifier, color = colour.copy(alpha = .12f), contentColor = colour, shape = RoundedCornerShape(12.dp), border = BorderStroke(1.dp, colour.copy(alpha = .35f))) {
        Row(Modifier.padding(horizontal = 10.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) { Icon(icon, null, Modifier.size(16.dp)); Text(label, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, maxLines = 1) }
    }
}

@Composable
private fun InlineBanner(title: String, detail: String, action: (() -> Unit)? = null) {
    Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(14.dp)) {
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(Modifier.weight(1f)) { Text(title, fontWeight = FontWeight.Bold); Text(detail, style = MaterialTheme.typography.bodySmall) }
            if (action != null) OutlinedButton(action) { Text("Retry") }
        }
    }
}

@Composable
private fun InlineError(text: String) { Text(text, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }

@Composable
private fun StepHeader(step: Int, label: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Surface(color = MaterialTheme.colorScheme.primary, shape = CircleShape) { Text(step.toString(), Modifier.padding(horizontal = 10.dp, vertical = 5.dp), color = Color.White, fontWeight = FontWeight.Bold) }
        Text("Step $step of 3 · $label", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun JunctionTimeline(stage: JunctionState) {
    val stages=listOf("Monitoring route","Junction detected","Confirming approach","Request sent","Controller validated",
        "Preparing safe signal","Green corridor active","Junction entered","Junction cleared","Normal signal restored")
    val index=when(stage) {
        JunctionState.OUTSIDE_COVERAGE -> 0
        JunctionState.JUNCTION_CANDIDATE -> 1
        JunctionState.APPROACH_CONFIRMING, JunctionState.APPROACH_CONFIRMED -> 2
        JunctionState.PRIORITY_REQUESTED -> 3
        JunctionState.CONTROLLER_VALIDATED -> 4
        JunctionState.SAFE_TRANSITION -> 5
        JunctionState.PRIORITY_GREEN -> 6
        JunctionState.STOP_LINE_CROSSED, JunctionState.INSIDE_JUNCTION, JunctionState.EXIT_CONFIRMING -> 7
        JunctionState.JUNCTION_CLEARED, JunctionState.NORMAL_RESTORING -> 8
        JunctionState.COMPLETED -> 9
        else -> -1
    }
    Column(verticalArrangement=Arrangement.spacedBy(5.dp)) {
        Text(if(index>=0) stages[index] else stage.name.replace('_',' '),fontWeight=FontWeight.Bold,
            color=if(index>=0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(4.dp)) {
            repeat(stages.size) { step -> Box(Modifier.weight(1f).height(5.dp).background(
                if(step<=index) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,CircleShape)) }
        }
    }
}

private fun screenTitle(screen: AppScreen) = when (screen) {
    AppScreen.LOGIN -> "Driver sign-in"; AppScreen.AMBULANCE -> "Vehicle"; AppScreen.HOME -> "Home"; AppScreen.MAP -> "Map"
    AppScreen.TRIPS -> "Trips"; AppScreen.SETTINGS -> "Settings"; AppScreen.PATIENT, AppScreen.PRIORITY, AppScreen.CONDITION -> "Patient information"
    AppScreen.DESTINATION -> "Destination"; AppScreen.CONFIRM -> "Route review"; AppScreen.TRIP_SUMMARY -> "Trip summary"; else -> "Emergency trip"
}

private fun PatientPriority?.label() = when (this) { PatientPriority.RED -> "Critical"; PatientPriority.YELLOW -> "Serious"; PatientPriority.GREEN -> "Stable"; null -> "Not selected" }
private fun PatientPriority.description() = when (this) { PatientPriority.RED -> "Immediate life-threatening emergency"; PatientPriority.YELLOW -> "Urgent treatment required"; PatientPriority.GREEN -> "Assisted medical transport" }
@Composable private fun PatientPriority?.colour() = when (this) { PatientPriority.RED -> MaterialTheme.colorScheme.error; PatientPriority.YELLOW -> Color(0xFFD97706); PatientPriority.GREEN -> MaterialTheme.colorScheme.secondary; null -> MaterialTheme.colorScheme.primary }
private fun GpsState.label() = name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase)
private fun ConnectionState.label() = name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase)
private fun JunctionStage.label() = name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase)
@Composable private fun GpsState.colour() = when (this) { GpsState.ACCURATE -> MaterialTheme.colorScheme.secondary; GpsState.LOCATING, GpsState.LOW_ACCURACY, GpsState.LAST_KNOWN -> Color(0xFFD97706); else -> MaterialTheme.colorScheme.error }
@Composable private fun ConnectionState.colour() = when (this) { ConnectionState.CONNECTED -> MaterialTheme.colorScheme.secondary; ConnectionState.CONNECTING -> Color(0xFFD97706); else -> MaterialTheme.colorScheme.error }
private fun formatDistance(metres: Double) = if (metres < 1000) "${metres.toInt()} m" else "%.1f km".format(metres / 1000)
private fun formatDuration(seconds: Long) = if (seconds < 60) "Less than 1 min" else "${seconds / 60} min"
