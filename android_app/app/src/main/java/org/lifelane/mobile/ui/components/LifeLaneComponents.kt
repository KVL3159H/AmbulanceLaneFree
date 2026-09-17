package org.lifelane.mobile.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Done
import androidx.compose.material.icons.outlined.DoneAll
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.MedicalServices
import androidx.compose.material.icons.outlined.NearMe
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.lifelane.mobile.PatientPriority
import org.lifelane.mobile.ui.theme.ActiveGreen
import org.lifelane.mobile.ui.theme.EmergencyRed
import org.lifelane.mobile.ui.theme.InformationBlue
import org.lifelane.mobile.ui.theme.LifeLaneDimens
import org.lifelane.mobile.ui.theme.SwiggyBorder
import org.lifelane.mobile.ui.theme.SwiggyGreen
import org.lifelane.mobile.ui.theme.SwiggyGreenSoft
import org.lifelane.mobile.ui.theme.SwiggyOrange
import org.lifelane.mobile.ui.theme.SwiggyOrangeDark
import org.lifelane.mobile.ui.theme.SwiggyOrangeSoft
import org.lifelane.mobile.ui.theme.SwiggyShapes
import org.lifelane.mobile.ui.theme.SwiggyTextBody
import org.lifelane.mobile.ui.theme.SwiggyTextHeading
import org.lifelane.mobile.ui.theme.SwiggyTokens
import org.lifelane.mobile.ui.theme.WarningAmber

@Composable
fun LifeLaneBrand(modifier: Modifier = Modifier, compact: Boolean = false, onDarkHeader: Boolean = false) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            modifier = Modifier
                .size(if (compact) 36.dp else 44.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(SwiggyOrange),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Outlined.NearMe,
                contentDescription = "LifeLane brand mark",
                tint = Color.White,
                modifier = Modifier.size(if (compact) 20.dp else 26.dp),
            )
        }
        Column {
            Text(
                "LifeLane",
                style = if (compact) MaterialTheme.typography.titleMedium else MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                color = if (onDarkHeader) Color.White else SwiggyTextHeading,
            )
            if (!compact) {
                Text(
                    "Smart Ambulance Priority",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (onDarkHeader) Color.White.copy(alpha = 0.85f) else SwiggyTextBody,
                )
            }
        }
    }
}

@Composable
fun LifeLaneTopBar(
    title: String,
    darkTheme: Boolean = false,
    onToggleDark: (() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    val barColor = if (darkTheme) MaterialTheme.colorScheme.surface else Color.White
    val contentColor = if (darkTheme) Color.White else SwiggyTextHeading

    Surface(color = barColor, shadowElevation = 3.dp) {
        Row(
            Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 56.dp)
                .padding(horizontal = LifeLaneDimens.pagePadding, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            LifeLaneBrand(compact = true, onDarkHeader = darkTheme)
            Column(Modifier.weight(1f)) {
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = contentColor,
                    maxLines = 1,
                )
                Text(
                    "Real-Time Traffic Preemption",
                    style = MaterialTheme.typography.labelSmall,
                    color = SwiggyTextBody,
                    maxLines = 1,
                )
            }
            trailing?.invoke()
        }
    }
}

@Composable
fun SwiggyEtaChip(etaMinutes: Int?, distanceKm: Double?, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = SwiggyShapes.pill,
        color = SwiggyGreenSoft,
        border = BorderStroke(1.dp, SwiggyGreen.copy(alpha = 0.4f)),
    ) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Box(Modifier.size(7.dp).clip(CircleShape).background(SwiggyGreen))
            Text(
                text = "${etaMinutes ?: 8} MINS" + if (distanceKm != null && distanceKm > 0) " · ${String.format("%.1f", distanceKm)} KM" else "",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = SwiggyGreen,
            )
        }
    }
}

@Composable
fun ConnectionBadge(type: String, status: String, modifier: Modifier = Modifier) {
    val isGood = status.equals("Live", ignoreCase = true) ||
                 status.equals("Accurate", ignoreCase = true) ||
                 status.equals("Connected", ignoreCase = true)
    val dotColor = if (isGood) SwiggyGreen else WarningAmber
    val bg = if (isGood) SwiggyGreenSoft else WarningAmber.copy(alpha = 0.10f)
    val borderCol = if (isGood) SwiggyGreen.copy(alpha = 0.35f) else WarningAmber.copy(alpha = 0.35f)

    Surface(
        modifier = modifier.defaultMinSize(minHeight = 34.dp),
        shape = SwiggyShapes.pill,
        color = bg,
        border = BorderStroke(1.dp, borderCol),
    ) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(dotColor))
            Text(
                text = "$type: $status",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = SwiggyTextHeading,
                maxLines = 1,
            )
        }
    }
}

enum class CheckMarkState { SINGLE_GREY, DOUBLE_GREY, DOUBLE_BLUE }

@Composable
fun WhatsAppCheckMarks(state: CheckMarkState, modifier: Modifier = Modifier) {
    val icon = when (state) {
        CheckMarkState.SINGLE_GREY -> Icons.Outlined.Done
        CheckMarkState.DOUBLE_GREY, CheckMarkState.DOUBLE_BLUE -> Icons.Outlined.DoneAll
    }
    val tint = when (state) {
        CheckMarkState.DOUBLE_BLUE -> SwiggyGreen
        else -> SwiggyTextBody
    }
    Icon(icon, contentDescription = null, tint = tint, modifier = modifier.size(16.dp))
}

@Composable
fun WhatsAppSecurityBanner(
    modifier: Modifier = Modifier,
    text: String = "Swiggy-style live corridor. Signal priority is authenticated via local controller.",
    darkTheme: Boolean = false,
) {
    val bg = if (darkTheme) Color(0xFF1C1F26) else SwiggyOrangeSoft
    val textCol = if (darkTheme) SwiggyOrange else SwiggyOrangeDark

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = SwiggyShapes.card,
        colors = CardDefaults.cardColors(containerColor = bg),
        border = BorderStroke(1.dp, SwiggyOrange.copy(alpha = 0.3f)),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(Icons.Outlined.Lock, contentDescription = null, tint = SwiggyOrange, modifier = Modifier.size(18.dp))
            Text(
                text,
                style = MaterialTheme.typography.bodySmall.copy(fontSize = 11.5.sp, lineHeight = 15.sp),
                color = textCol,
            )
        }
    }
}

@Composable
fun WarningBanner(title: String, detail: String, modifier: Modifier = Modifier, onRetry: (() -> Unit)? = null) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = SwiggyShapes.card,
        colors = CardDefaults.cardColors(containerColor = WarningAmber.copy(alpha = 0.10f)),
        border = BorderStroke(1.dp, WarningAmber.copy(alpha = 0.40f)),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(Icons.Outlined.WarningAmber, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(20.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = WarningAmber)
                Text(detail, style = MaterialTheme.typography.bodySmall, color = SwiggyTextHeading)
            }
            onRetry?.let {
                OutlinedButton(
                    onClick = it,
                    shape = SwiggyShapes.pill,
                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                    modifier = Modifier.height(32.dp),
                ) {
                    Text("Retry", style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
fun ErrorBanner(title: String, detail: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = SwiggyShapes.card,
        colors = CardDefaults.cardColors(containerColor = EmergencyRed.copy(alpha = 0.10f)),
        border = BorderStroke(1.dp, EmergencyRed.copy(alpha = 0.40f)),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(Icons.Outlined.ErrorOutline, contentDescription = null, tint = EmergencyRed, modifier = Modifier.size(20.dp))
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = EmergencyRed)
                Text(detail, style = MaterialTheme.typography.bodySmall, color = SwiggyTextHeading)
            }
        }
    }
}

@Composable
fun PriorityCard(priority: PatientPriority, selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier, darkTheme: Boolean = false) {
    val details = when (priority) {
        PatientPriority.RED -> Triple("Critical", "Immediate life-threat (cardiac, major trauma)", EmergencyRed)
        PatientPriority.YELLOW -> Triple("Serious", "Severe injury or illness, urgent preemption", WarningAmber)
        PatientPriority.GREEN -> Triple("Stable", "Medical transport requiring assistance", SwiggyGreen)
    }
    val targetBg = if (selected) SwiggyOrangeSoft else (if (darkTheme) Color(0xFF1C1F26) else Color.White)
    val targetBorder = if (selected) SwiggyOrange else SwiggyBorder
    val animatedBorder by animateColorAsState(targetBorder, label = "priority border")

    Card(
        modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 68.dp)
            .clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "${details.first} priority. ${details.second}. ${if (selected) "Selected" else "Not selected"}" },
        shape = SwiggyShapes.card,
        colors = CardDefaults.cardColors(containerColor = targetBg),
        border = BorderStroke(if (selected) 2.dp else 1.dp, animatedBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = if (selected) 3.dp else 1.dp),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(
                Modifier
                    .size(38.dp)
                    .clip(CircleShape)
                    .background(details.third.copy(alpha = 0.14f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Outlined.MedicalServices, contentDescription = null, tint = details.third, modifier = Modifier.size(20.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(details.first, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = details.third)
                Text(details.second, style = MaterialTheme.typography.bodySmall, color = SwiggyTextBody)
            }
            if (selected) {
                Box(Modifier.size(24.dp).clip(CircleShape).background(SwiggyOrange), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Done, contentDescription = "Selected", tint = Color.White, modifier = Modifier.size(16.dp))
                }
            } else {
                Icon(Icons.Outlined.RadioButtonUnchecked, contentDescription = "Unselected", tint = SwiggyTextBody, modifier = Modifier.size(20.dp))
            }
        }
    }
}

@Composable
fun ConditionChip(label: String, selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier, darkTheme: Boolean = false) {
    val bg = if (selected) SwiggyOrangeSoft else (if (darkTheme) Color(0xFF1C1F26) else Color.White)
    val borderCol = if (selected) SwiggyOrange else SwiggyBorder

    Surface(
        modifier = modifier
            .defaultMinSize(minHeight = 42.dp)
            .clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "$label, ${if (selected) "selected" else "not selected"}" },
        shape = SwiggyShapes.chip,
        color = bg,
        border = BorderStroke(if (selected) 2.dp else 1.dp, borderCol),
        shadowElevation = if (selected) 2.dp else 0.dp,
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (selected) {
                Box(Modifier.size(16.dp).clip(CircleShape).background(SwiggyOrange), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Done, contentDescription = null, tint = Color.White, modifier = Modifier.size(11.dp))
                }
            } else {
                Icon(Icons.Outlined.RadioButtonUnchecked, contentDescription = null, tint = SwiggyTextBody, modifier = Modifier.size(16.dp))
            }
            Text(label, style = MaterialTheme.typography.bodySmall, fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal, color = if (selected) SwiggyOrangeDark else SwiggyTextHeading)
        }
    }
}

@Composable
fun LiveMetricCard(label: String, value: String, modifier: Modifier = Modifier, supporting: String? = null, isHighlight: Boolean = false, darkTheme: Boolean = false) {
    val bg = if (isHighlight) SwiggyOrangeSoft else (if (darkTheme) Color(0xFF1C1F26) else Color.White)
    Card(
        modifier,
        shape = SwiggyShapes.card,
        colors = CardDefaults.cardColors(containerColor = bg),
        border = BorderStroke(1.dp, if (isHighlight) SwiggyOrange.copy(alpha = 0.5f) else SwiggyBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = SwiggyTextBody, maxLines = 1)
            Text(value, fontSize = 18.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp, color = SwiggyTextHeading, maxLines = 1)
            supporting?.let { Text(it, style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp), color = SwiggyOrangeDark, maxLines = 1) }
        }
    }
}

@Composable
fun EmergencyStatusCard(stages: List<String>, currentStage: Int, modifier: Modifier = Modifier) {
    Card(
        modifier.fillMaxWidth(),
        shape = SwiggyShapes.card,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, SwiggyBorder),
        elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
    ) {
        Column(Modifier.padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Live Preemption Status", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = SwiggyTextHeading)
                Text("CORRIDOR", style = MaterialTheme.typography.labelSmall, color = SwiggyOrange, fontWeight = FontWeight.Bold)
            }
            stages.forEachIndexed { index, stage ->
                val reached = index < currentStage
                val activeCurrent = index == currentStage
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    when {
                        reached -> Icon(Icons.Outlined.CheckCircle, "Completed", tint = SwiggyGreen, modifier = Modifier.size(18.dp))
                        activeCurrent -> CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.5.dp, color = SwiggyOrange)
                        else -> Icon(Icons.Outlined.RadioButtonUnchecked, "Pending", tint = SwiggyBorder, modifier = Modifier.size(18.dp))
                    }
                    Text(
                        stage,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = if (activeCurrent) FontWeight.Bold else FontWeight.Normal,
                        color = when {
                            activeCurrent -> SwiggyOrange
                            reached -> SwiggyTextHeading
                            else -> SwiggyTextBody
                        },
                    )
                }
            }
        }
    }
}

@Composable
fun PrimaryActionButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Button(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp),
        enabled = enabled,
        shape = SwiggyShapes.action,
        colors = ButtonDefaults.buttonColors(
            containerColor = SwiggyOrange,
            contentColor = Color.White,
            disabledContainerColor = SwiggyOrange.copy(alpha = 0.38f),
            disabledContentColor = Color.White.copy(alpha = 0.6f),
        ),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 3.dp, pressedElevation = 6.dp),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge.copy(fontSize = 16.sp, fontWeight = FontWeight.Bold))
    }
}

@Composable
fun DangerActionButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Button(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp),
        shape = SwiggyShapes.action,
        enabled = enabled,
        colors = ButtonDefaults.buttonColors(
            containerColor = EmergencyRed,
            contentColor = Color.White,
        ),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 3.dp, pressedElevation = 6.dp),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge.copy(fontSize = 16.sp, fontWeight = FontWeight.Bold))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConfirmationBottomSheet(title: String, detail: String, confirmLabel: String, dangerous: Boolean, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        shape = SwiggyShapes.sheet,
        containerColor = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = LifeLaneDimens.xlarge, vertical = LifeLaneDimens.large),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = SwiggyTextHeading)
            Text(detail, style = MaterialTheme.typography.bodyLarge, color = SwiggyTextBody)
            if (dangerous) DangerActionButton(confirmLabel, onConfirm) else PrimaryActionButton(confirmLabel, onConfirm)
            OutlinedButton(
                onDismiss,
                Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp),
                shape = SwiggyShapes.action,
                border = BorderStroke(1.dp, SwiggyBorder),
            ) {
                Text("Go back", color = SwiggyTextHeading, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
fun LoadingState(label: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            Modifier.size(48.dp).clip(CircleShape).background(SwiggyOrangeSoft),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Outlined.LocationOn, contentDescription = null, tint = SwiggyOrange, modifier = Modifier.size(28.dp))
        }
        Text(label, textAlign = TextAlign.Center, color = SwiggyTextBody)
    }
}

@Composable
fun EmptyState(title: String, detail: String, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, SwiggyBorder, SwiggyShapes.card)
            .padding(20.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(Icons.Outlined.Info, contentDescription = null, tint = SwiggyOrange, modifier = Modifier.size(30.dp))
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = SwiggyTextHeading)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = SwiggyTextBody, textAlign = TextAlign.Center)
        }
    }
}
