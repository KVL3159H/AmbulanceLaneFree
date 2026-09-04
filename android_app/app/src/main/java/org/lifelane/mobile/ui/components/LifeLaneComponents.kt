package org.lifelane.mobile.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.MedicalServices
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.SignalCellularAlt
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.lifelane.mobile.PatientPriority
import org.lifelane.mobile.R
import org.lifelane.mobile.ui.theme.ActiveGreen
import org.lifelane.mobile.ui.theme.EmergencyRed
import org.lifelane.mobile.ui.theme.InformationBlue
import org.lifelane.mobile.ui.theme.LifeLaneDimens
import org.lifelane.mobile.ui.theme.PrimaryTeal
import org.lifelane.mobile.ui.theme.TextMutedDark
import org.lifelane.mobile.ui.theme.WarningAmber

@Composable
fun LifeLaneBrand(modifier: Modifier = Modifier, compact: Boolean = false) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Icon(
            painter = painterResource(R.drawable.lifelane_mark),
            contentDescription = "LifeLane route, location, medical and traffic-signal logo",
            tint = Color.Unspecified,
            modifier = Modifier.size(if (compact) 40.dp else 56.dp),
        )
        Column {
            Text("LifeLane", style = if (compact) MaterialTheme.typography.titleMedium else MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            if (!compact) Text("Emergency Mobility Intelligence", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun LifeLaneTopBar(title: String, darkTheme: Boolean, onToggleTheme: () -> Unit, trailing: (@Composable () -> Unit)? = null) {
    Surface(color = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
        Row(
            Modifier.fillMaxWidth().defaultMinSize(minHeight = 68.dp).padding(horizontal = LifeLaneDimens.large, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            LifeLaneBrand(compact = true)
            Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f), maxLines = 1)
            trailing?.invoke()
            OutlinedButton(
                onClick = onToggleTheme,
                modifier = Modifier.defaultMinSize(minHeight = LifeLaneDimens.minTouch),
                contentPadding = ButtonDefaults.ContentPadding,
            ) { Text(if (darkTheme) "Light" else "Dark") }
        }
    }
}

@Composable
fun ConnectionBadge(label: String, state: String, modifier: Modifier = Modifier) {
    val normalized = state.lowercase()
    val (colour, statusIcon) = when {
        normalized.contains("error") || normalized.contains("lost") || normalized.contains("denied") || normalized.contains("disconnected") -> EmergencyRed to Icons.Outlined.ErrorOutline
        normalized.contains("connecting") || normalized.contains("acquiring") || normalized.contains("waiting") -> WarningAmber to Icons.Outlined.SignalCellularAlt
        normalized.contains("connected") || normalized.contains("live") || normalized.contains("online") -> ActiveGreen to Icons.Outlined.CheckCircle
        else -> InformationBlue to Icons.Outlined.Info
    }
    Surface(modifier, shape = RoundedCornerShape(8.dp), color = colour.copy(alpha = 0.10f), border = BorderStroke(1.dp, colour.copy(alpha = 0.72f))) {
        Row(Modifier.padding(horizontal = 10.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(statusIcon, contentDescription = null, tint = colour, modifier = Modifier.size(16.dp))
            Text("$label · $state", style = MaterialTheme.typography.labelMedium, color = colour)
        }
    }
}

@Composable
fun PriorityCard(priority: PatientPriority, selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier) {
    val details = when (priority) {
        PatientPriority.RED -> Triple("Critical", "Immediate life-threatening emergency", EmergencyRed)
        PatientPriority.YELLOW -> Triple("Serious", "Urgent care and expedited passage", WarningAmber)
        PatientPriority.GREEN -> Triple("Stable", "Medical transport requiring assistance", ActiveGreen)
    }
    val animatedBorder by animateColorAsState(if (selected) details.third else MaterialTheme.colorScheme.outline, label = "priority border")
    Card(
        modifier.fillMaxWidth().defaultMinSize(minHeight = 88.dp).clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "${details.first} priority. ${details.second}. ${if (selected) "Selected" else "Not selected"}" },
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(if (selected) 2.dp else 1.dp, animatedBorder),
    ) {
        Row(Modifier.fillMaxWidth().padding(LifeLaneDimens.large), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Icon(Icons.Outlined.MedicalServices, contentDescription = null, tint = details.third, modifier = Modifier.size(28.dp))
            Column(Modifier.weight(1f)) {
                Text(details.first, style = MaterialTheme.typography.titleMedium)
                Text(details.second, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(if (selected) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked, contentDescription = null, tint = if (selected) details.third else MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun ConditionChip(label: String, selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier) {
    Surface(
        modifier.defaultMinSize(minHeight = LifeLaneDimens.minTouch).clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "$label, ${if (selected) "selected" else "not selected"}" },
        shape = RoundedCornerShape(10.dp),
        color = if (selected) PrimaryTeal.copy(alpha = .14f) else MaterialTheme.colorScheme.surface,
        border = BorderStroke(if (selected) 2.dp else 1.dp, if (selected) PrimaryTeal else MaterialTheme.colorScheme.outline),
    ) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            Icon(if (selected) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked, contentDescription = null, tint = if (selected) PrimaryTeal else MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(20.dp))
            Text(label, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
fun LiveMetricCard(label: String, value: String, modifier: Modifier = Modifier, supporting: String? = null) {
    Card(modifier, colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, fontSize = 24.sp, fontWeight = FontWeight.Bold, lineHeight = 28.sp)
            supporting?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

@Composable
fun EmergencyStatusCard(stages: List<String>, currentStage: Int, modifier: Modifier = Modifier) {
    Card(modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)) {
        Column(Modifier.padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Emergency route progress", style = MaterialTheme.typography.titleMedium)
            stages.forEachIndexed { index, stage ->
                val reached = index <= currentStage
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Icon(if (reached) Icons.Outlined.CheckCircle else Icons.Outlined.RadioButtonUnchecked, contentDescription = null, tint = if (reached) PrimaryTeal else MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(20.dp))
                    Text(stage, style = MaterialTheme.typography.bodyMedium, color = if (reached) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
fun PrimaryActionButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Button(onClick, modifier.fillMaxWidth().defaultMinSize(minHeight = 54.dp), enabled = enabled, shape = RoundedCornerShape(10.dp)) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun DangerActionButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    OutlinedButton(
        onClick,
        modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp),
        shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, EmergencyRed),
        colors = ButtonDefaults.outlinedButtonColors(contentColor = EmergencyRed),
    ) { Text(text, style = MaterialTheme.typography.labelLarge) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConfirmationBottomSheet(title: String, detail: String, confirmLabel: String, dangerous: Boolean, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.fillMaxWidth().padding(horizontal = LifeLaneDimens.xlarge, vertical = LifeLaneDimens.large), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(title, style = MaterialTheme.typography.headlineSmall)
            Text(detail, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (dangerous) DangerActionButton(confirmLabel, onConfirm) else PrimaryActionButton(confirmLabel, onConfirm)
            OutlinedButton(onDismiss, Modifier.fillMaxWidth().defaultMinSize(minHeight = 50.dp)) { Text("Go back") }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
fun WarningBanner(title: String, detail: String, modifier: Modifier = Modifier, onRetry: (() -> Unit)? = null) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), color = WarningAmber.copy(alpha = .10f), border = BorderStroke(1.dp, WarningAmber)) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(Icons.Outlined.WarningAmber, contentDescription = null, tint = WarningAmber)
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium, color = WarningAmber)
                Text(detail, style = MaterialTheme.typography.bodyMedium)
            }
            onRetry?.let { OutlinedButton(it, modifier = Modifier.defaultMinSize(minHeight = 48.dp)) { Text("Retry") } }
        }
    }
}

@Composable
fun LoadingState(label: String, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Icon(Icons.Outlined.LocationOn, contentDescription = null, tint = PrimaryTeal, modifier = Modifier.size(32.dp))
        Text(label, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun EmptyState(title: String, detail: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(12.dp)).padding(24.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(Icons.Outlined.Info, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        }
    }
}
