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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.Done
import androidx.compose.material.icons.outlined.DoneAll
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.outlined.LocationOn
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.MedicalServices
import androidx.compose.material.icons.outlined.NearMe
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material.icons.outlined.SignalCellularAlt
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import org.lifelane.mobile.ui.theme.WarningAmber
import org.lifelane.mobile.ui.theme.WhatsAppBlueTick
import org.lifelane.mobile.ui.theme.WhatsAppShapes
import org.lifelane.mobile.ui.theme.WhatsAppTokens
import org.lifelane.mobile.ui.theme.WhatsAppVibrantGreen

@Composable
fun LifeLaneBrand(modifier: Modifier = Modifier, compact: Boolean = false, onDarkHeader: Boolean = false) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Icon(
            painter = painterResource(R.drawable.lifelane_mark),
            contentDescription = "LifeLane WhatsApp emergency mark",
            tint = Color.Unspecified,
            modifier = Modifier.size(if (compact) 38.dp else 52.dp),
        )
        Column {
            Text(
                "LifeLane",
                style = if (compact) MaterialTheme.typography.titleMedium else MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                color = if (onDarkHeader) Color.White else MaterialTheme.colorScheme.onSurface,
            )
            if (!compact) {
                Text(
                    "Emergency Mobility Intelligence",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (onDarkHeader) Color.White.copy(alpha = 0.85f) else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
fun LifeLaneTopBar(title: String, darkTheme: Boolean, onToggleTheme: () -> Unit, trailing: (@Composable () -> Unit)? = null) {
    val barColor = WhatsAppTokens.topBarColor(darkTheme)
    val contentColor = WhatsAppTokens.topBarContentColor(darkTheme)

    Surface(color = barColor, shadowElevation = 3.dp) {
        Row(
            Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 64.dp)
                .padding(horizontal = LifeLaneDimens.large, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            LifeLaneBrand(compact = true, onDarkHeader = !darkTheme || barColor != MaterialTheme.colorScheme.surface)
            Column(Modifier.weight(1f)) {
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = contentColor,
                    maxLines = 1,
                )
                Text(
                    "LifeLane Network · Active",
                    style = MaterialTheme.typography.labelMedium.copy(fontSize = 11.sp),
                    color = contentColor.copy(alpha = 0.80f),
                    maxLines = 1,
                )
            }
            trailing?.invoke()
            IconButton(
                onClick = onToggleTheme,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(contentColor.copy(alpha = 0.12f))
                    .size(38.dp),
            ) {
                Icon(
                    if (darkTheme) Icons.Outlined.LightMode else Icons.Outlined.DarkMode,
                    contentDescription = "Toggle WhatsApp theme",
                    tint = contentColor,
                    modifier = Modifier.size(20.dp),
                )
            }
        }
    }
}

enum class CheckMarkState { SINGLE_GREY, DOUBLE_GREY, DOUBLE_BLUE }

@Composable
fun WhatsAppCheckMarks(state: CheckMarkState, modifier: Modifier = Modifier) {
    val (icon, tint) = when (state) {
        CheckMarkState.SINGLE_GREY -> Icons.Outlined.Done to MaterialTheme.colorScheme.onSurfaceVariant
        CheckMarkState.DOUBLE_GREY -> Icons.Outlined.DoneAll to MaterialTheme.colorScheme.onSurfaceVariant
        CheckMarkState.DOUBLE_BLUE -> Icons.Outlined.DoneAll to WhatsAppBlueTick
    }
    Icon(icon, contentDescription = "Delivery status", tint = tint, modifier = modifier.size(17.dp))
}

@Composable
fun WhatsAppSecurityBanner(
    text: String = "Messages and emergency telemetry are end-to-end encrypted. No third party can alter junction preemption.",
    modifier: Modifier = Modifier,
    darkTheme: Boolean = false,
) {
    val bg = WhatsAppTokens.securityCardBackground(darkTheme)
    val textColor = WhatsAppTokens.securityCardTextColor(darkTheme)
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = WhatsAppShapes.card,
        color = bg,
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Icon(Icons.Outlined.Lock, contentDescription = null, tint = textColor, modifier = Modifier.size(16.dp))
            Text(
                text,
                style = MaterialTheme.typography.labelMedium.copy(fontSize = 12.sp, lineHeight = 16.sp),
                color = textColor,
                textAlign = TextAlign.Start,
            )
        }
    }
}

@Composable
fun LiveLocationRadarBanner(status: String, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = WhatsAppShapes.card,
        color = WhatsAppVibrantGreen.copy(alpha = 0.12f),
        border = BorderStroke(1.dp, WhatsAppVibrantGreen.copy(alpha = 0.5f)),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 11.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Box(
                Modifier
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(WhatsAppVibrantGreen)
            )
            Icon(Icons.Outlined.NearMe, contentDescription = null, tint = WhatsAppVibrantGreen, modifier = Modifier.size(18.dp))
            Column(Modifier.weight(1f)) {
                Text("Sharing live emergency location", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
                Text(status, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
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
    Surface(
        modifier,
        shape = WhatsAppShapes.pillBadge,
        color = colour.copy(alpha = 0.12f),
        border = BorderStroke(1.dp, colour.copy(alpha = 0.50f)),
    ) {
        Row(
            Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(colour))
            Icon(statusIcon, contentDescription = null, tint = colour, modifier = Modifier.size(15.dp))
            Text("$label: $state", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Medium, color = colour)
        }
    }
}

@Composable
fun PriorityCard(priority: PatientPriority, selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier, darkTheme: Boolean = false) {
    val details = when (priority) {
        PatientPriority.RED -> Triple("Critical", "Immediate life-threatening emergency", EmergencyRed)
        PatientPriority.YELLOW -> Triple("Serious", "Urgent care and expedited passage", WarningAmber)
        PatientPriority.GREEN -> Triple("Stable", "Medical transport requiring assistance", ActiveGreen)
    }
    val targetBg = if (selected) WhatsAppTokens.outgoingBubbleColor(darkTheme) else MaterialTheme.colorScheme.surface
    val targetBorder = if (selected) WhatsAppVibrantGreen else MaterialTheme.colorScheme.outline.copy(alpha = 0.6f)
    val animatedBorder by animateColorAsState(targetBorder, label = "priority border")

    Card(
        modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 84.dp)
            .clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "${details.first} priority. ${details.second}. ${if (selected) "Selected" else "Not selected"}" },
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = targetBg),
        border = BorderStroke(if (selected) 2.dp else 1.dp, animatedBorder),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(LifeLaneDimens.large),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Box(
                Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(details.third.copy(alpha = 0.14f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Outlined.MedicalServices, contentDescription = null, tint = details.third, modifier = Modifier.size(22.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(details.first, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(details.second, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (selected) {
                Box(Modifier.size(24.dp).clip(CircleShape).background(WhatsAppVibrantGreen), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Done, contentDescription = "Selected", tint = Color.White, modifier = Modifier.size(16.dp))
                }
            } else {
                Icon(Icons.Outlined.RadioButtonUnchecked, contentDescription = "Unselected", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(22.dp))
            }
        }
    }
}

@Composable
fun ConditionChip(label: String, selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier, darkTheme: Boolean = false) {
    val bg = if (selected) WhatsAppTokens.outgoingBubbleColor(darkTheme) else MaterialTheme.colorScheme.surface
    val borderCol = if (selected) WhatsAppVibrantGreen else MaterialTheme.colorScheme.outline.copy(alpha = 0.6f)

    Surface(
        modifier = modifier
            .defaultMinSize(minHeight = LifeLaneDimens.minTouch)
            .clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "$label, ${if (selected) "selected" else "not selected"}" },
        shape = WhatsAppShapes.pillBadge,
        color = bg,
        border = BorderStroke(if (selected) 2.dp else 1.dp, borderCol),
    ) {
        Row(
            Modifier.padding(horizontal = 16.dp, vertical = 11.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            if (selected) {
                Box(Modifier.size(18.dp).clip(CircleShape).background(WhatsAppVibrantGreen), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Done, contentDescription = null, tint = Color.White, modifier = Modifier.size(12.dp))
                }
            } else {
                Icon(Icons.Outlined.RadioButtonUnchecked, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
            }
            Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal)
        }
    }
}

@Composable
fun LiveMetricCard(label: String, value: String, modifier: Modifier = Modifier, supporting: String? = null, isHighlight: Boolean = false, darkTheme: Boolean = false) {
    val bg = if (isHighlight) WhatsAppTokens.outgoingBubbleColor(darkTheme) else MaterialTheme.colorScheme.surface
    Card(
        modifier,
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = bg),
        border = BorderStroke(1.dp, if (isHighlight) WhatsAppVibrantGreen.copy(alpha = 0.5f) else MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, fontSize = 23.sp, fontWeight = FontWeight.Bold, lineHeight = 27.sp, color = MaterialTheme.colorScheme.onSurface)
            supporting?.let { Text(it, style = MaterialTheme.typography.labelMedium.copy(fontSize = 11.sp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

@Composable
fun EmergencyStatusCard(stages: List<String>, currentStage: Int, modifier: Modifier = Modifier) {
    Card(
        modifier.fillMaxWidth(),
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
    ) {
        Column(Modifier.padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(11.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Emergency route progress", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("WhatsApp sync", style = MaterialTheme.typography.labelMedium, color = WhatsAppVibrantGreen, fontWeight = FontWeight.Medium)
            }
            stages.forEachIndexed { index, stage ->
                val reached = index <= currentStage
                val activeCurrent = index == currentStage
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
                    if (reached) {
                        WhatsAppCheckMarks(CheckMarkState.DOUBLE_BLUE)
                    } else {
                        WhatsAppCheckMarks(CheckMarkState.SINGLE_GREY)
                    }
                    Text(
                        stage,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = if (activeCurrent) FontWeight.Bold else FontWeight.Normal,
                        color = when {
                            activeCurrent -> WhatsAppVibrantGreen
                            reached -> MaterialTheme.colorScheme.onSurface
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
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
        shape = WhatsAppShapes.actionButton,
        colors = ButtonDefaults.buttonColors(
            containerColor = WhatsAppVibrantGreen,
            contentColor = Color.White,
            disabledContainerColor = WhatsAppVibrantGreen.copy(alpha = 0.38f),
            disabledContentColor = Color.White.copy(alpha = 0.6f),
        ),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp, pressedElevation = 4.dp),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge.copy(fontSize = 16.sp, fontWeight = FontWeight.Bold))
    }
}

@Composable
fun DangerActionButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Button(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp),
        shape = WhatsAppShapes.actionButton,
        colors = ButtonDefaults.buttonColors(
            containerColor = EmergencyRed,
            contentColor = Color.White,
        ),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp, pressedElevation = 4.dp),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge.copy(fontSize = 16.sp, fontWeight = FontWeight.Bold))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConfirmationBottomSheet(title: String, detail: String, confirmLabel: String, dangerous: Boolean, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
        containerColor = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = LifeLaneDimens.xlarge, vertical = LifeLaneDimens.large),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(detail, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (dangerous) DangerActionButton(confirmLabel, onConfirm) else PrimaryActionButton(confirmLabel, onConfirm)
            OutlinedButton(
                onDismiss,
                Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp),
                shape = WhatsAppShapes.actionButton,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            ) {
                Text("Go back", color = MaterialTheme.colorScheme.onSurface)
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
fun WarningBanner(title: String, detail: String, modifier: Modifier = Modifier, onRetry: (() -> Unit)? = null) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = WhatsAppShapes.card,
        color = WarningAmber.copy(alpha = 0.12f),
        border = BorderStroke(1.dp, WarningAmber.copy(alpha = 0.6f)),
    ) {
        Row(
            Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Icon(Icons.Outlined.WarningAmber, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(24.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, color = WarningAmber)
                Text(detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
            }
            onRetry?.let {
                Button(
                    it,
                    modifier = Modifier.defaultMinSize(minHeight = 40.dp),
                    shape = WhatsAppShapes.pillBadge,
                    colors = ButtonDefaults.buttonColors(containerColor = WarningAmber, contentColor = Color.White),
                ) {
                    Text("Retry", fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}

@Composable
fun LoadingState(label: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            Modifier.size(48.dp).clip(CircleShape).background(WhatsAppVibrantGreen.copy(alpha = 0.15f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Outlined.LocationOn, contentDescription = null, tint = WhatsAppVibrantGreen, modifier = Modifier.size(28.dp))
        }
        Text(label, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun EmptyState(title: String, detail: String, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f), WhatsAppShapes.card)
            .padding(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(Icons.Outlined.Info, contentDescription = null, tint = WhatsAppVibrantGreen, modifier = Modifier.size(30.dp))
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        }
    }
}
