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
import org.lifelane.mobile.ui.theme.MobilityTeal
import org.lifelane.mobile.ui.theme.WarningAmber
import org.lifelane.mobile.ui.theme.WhatsAppBlueTick
import org.lifelane.mobile.ui.theme.WhatsAppSecurityGold
import org.lifelane.mobile.ui.theme.WhatsAppShapes
import org.lifelane.mobile.ui.theme.WhatsAppTokens
import org.lifelane.mobile.ui.theme.WhatsAppVibrantGreen

@Composable
fun LifeLaneBrand(modifier: Modifier = Modifier, compact: Boolean = false, onDarkHeader: Boolean = false) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Icon(
            painter = painterResource(R.drawable.lifelane_mark),
            contentDescription = "LifeLane emergency mobility mark",
            tint = Color.Unspecified,
            modifier = Modifier.size(if (compact) 34.dp else 44.dp),
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
fun LifeLaneTopBar(
    title: String,
    darkTheme: Boolean = false,
    onToggleDark: (() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    val barColor = MaterialTheme.colorScheme.surface
    val contentColor = MaterialTheme.colorScheme.onSurface

    Surface(color = barColor, shadowElevation = 2.dp) {
        Row(
            Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 52.dp)
                .padding(horizontal = LifeLaneDimens.pagePadding, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            LifeLaneBrand(compact = true, onDarkHeader = false)
            Column(Modifier.weight(1f)) {
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = contentColor,
                    maxLines = 1,
                )
                Text(
                    "Emergency mobility research prototype",
                    style = MaterialTheme.typography.labelSmall,
                    color = contentColor.copy(alpha = 0.75f),
                    maxLines = 1,
                )
            }
            trailing?.invoke()
        }
    }
}

@Composable
fun ConnectionBadge(type: String, status: String, modifier: Modifier = Modifier) {
    val isGood = status.equals("Live", ignoreCase = true) ||
                 status.equals("Accurate", ignoreCase = true) ||
                 status.equals("Connected", ignoreCase = true)
    val dotColor = if (isGood) ActiveGreen else WarningAmber
    val bg = if (isGood) ActiveGreen.copy(alpha = 0.08f) else WarningAmber.copy(alpha = 0.08f)
    val borderCol = if (isGood) ActiveGreen.copy(alpha = 0.35f) else WarningAmber.copy(alpha = 0.35f)

    Surface(
        modifier = modifier.defaultMinSize(minHeight = 36.dp),
        shape = WhatsAppShapes.pillBadge,
        color = bg,
        border = BorderStroke(1.dp, borderCol),
    ) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(dotColor))
            Text(
                text = "$type: $status",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface,
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
        CheckMarkState.DOUBLE_BLUE -> WhatsAppBlueTick
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Icon(icon, contentDescription = null, tint = tint, modifier = modifier.size(16.dp))
}

@Composable
fun WhatsAppSecurityBanner(
    modifier: Modifier = Modifier,
    text: String = "Research prototype. Controller status is shown only when received from the configured junction.",
    darkTheme: Boolean = false,
) {
    val bg = WhatsAppTokens.securityCardBackground(darkTheme)
    val textCol = WhatsAppTokens.securityCardTextColor(darkTheme)

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = bg),
        border = BorderStroke(1.dp, WhatsAppSecurityGold),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(Icons.Outlined.Lock, contentDescription = null, tint = MobilityTeal, modifier = Modifier.size(18.dp))
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
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = WarningAmber.copy(alpha = 0.12f)),
        border = BorderStroke(1.dp, WarningAmber.copy(alpha = 0.45f)),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(Icons.Outlined.WarningAmber, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(20.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = WarningAmber)
                Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface)
            }
            onRetry?.let {
                OutlinedButton(
                    onClick = it,
                    shape = WhatsAppShapes.pillBadge,
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
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = EmergencyRed.copy(alpha = 0.12f)),
        border = BorderStroke(1.dp, EmergencyRed.copy(alpha = 0.45f)),
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(Icons.Outlined.ErrorOutline, contentDescription = null, tint = EmergencyRed, modifier = Modifier.size(20.dp))
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = EmergencyRed)
                Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface)
            }
        }
    }
}

@Composable
fun PriorityCard(priority: PatientPriority, selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier, darkTheme: Boolean = false) {
    val details = when (priority) {
        PatientPriority.RED -> Triple("Critical", "Immediate life-threat (cardiac, major trauma)", EmergencyRed)
        PatientPriority.YELLOW -> Triple("Serious", "Severe injury or illness, urgent preemption", WarningAmber)
        PatientPriority.GREEN -> Triple("Stable", "Medical transport requiring assistance", ActiveGreen)
    }
    val targetBg = if (selected) WhatsAppTokens.outgoingBubbleColor(darkTheme) else MaterialTheme.colorScheme.surface
    val targetBorder = if (selected) WhatsAppVibrantGreen else MaterialTheme.colorScheme.outline.copy(alpha = 0.6f)
    val animatedBorder by animateColorAsState(targetBorder, label = "priority border")

    Card(
        modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 64.dp)
            .clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "${details.first} priority. ${details.second}. ${if (selected) "Selected" else "Not selected"}" },
        shape = WhatsAppShapes.card,
        colors = CardDefaults.cardColors(containerColor = targetBg),
        border = BorderStroke(if (selected) 2.dp else 1.dp, animatedBorder),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(
                Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(details.third.copy(alpha = 0.14f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Outlined.MedicalServices, contentDescription = null, tint = details.third, modifier = Modifier.size(20.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(details.first, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = details.third)
                Text(details.second, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (selected) {
                Box(Modifier.size(22.dp).clip(CircleShape).background(WhatsAppVibrantGreen), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Done, contentDescription = "Selected", tint = Color.White, modifier = Modifier.size(15.dp))
                }
            } else {
                Icon(Icons.Outlined.RadioButtonUnchecked, contentDescription = "Unselected", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(20.dp))
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
            .defaultMinSize(minHeight = 40.dp)
            .clickable(role = Role.RadioButton, onClick = onSelect)
            .semantics { contentDescription = "$label, ${if (selected) "selected" else "not selected"}" },
        shape = WhatsAppShapes.pillBadge,
        color = bg,
        border = BorderStroke(if (selected) 2.dp else 1.dp, borderCol),
    ) {
        Row(
            Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (selected) {
                Box(Modifier.size(16.dp).clip(CircleShape).background(WhatsAppVibrantGreen), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Done, contentDescription = null, tint = Color.White, modifier = Modifier.size(11.dp))
                }
            } else {
                Icon(Icons.Outlined.RadioButtonUnchecked, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
            }
            Text(label, style = MaterialTheme.typography.bodySmall, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal)
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
        Column(Modifier.padding(horizontal = 8.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
            Text(value, fontSize = 17.sp, fontWeight = FontWeight.Bold, lineHeight = 21.sp, color = MaterialTheme.colorScheme.onSurface, maxLines = 1)
            supporting?.let { Text(it, style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp), color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1) }
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
        Column(Modifier.padding(LifeLaneDimens.cardPadding), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Emergency route progress", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("Controller timeline", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, fontWeight = FontWeight.Medium)
            }
            stages.forEachIndexed { index, stage ->
                val reached = index < currentStage
                val activeCurrent = index == currentStage
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    when {
                        reached -> Icon(Icons.Outlined.CheckCircle, "Completed", tint = WhatsAppVibrantGreen, modifier = Modifier.size(16.dp))
                        activeCurrent -> CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = InformationBlue)
                        else -> Icon(Icons.Outlined.RadioButtonUnchecked, "Pending", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(16.dp))
                    }
                    Text(
                        stage,
                        style = MaterialTheme.typography.bodySmall,
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
        modifier = modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp),
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
        Text(text, style = MaterialTheme.typography.labelLarge.copy(fontSize = 15.sp, fontWeight = FontWeight.Bold))
    }
}

@Composable
fun DangerActionButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Button(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp),
        shape = WhatsAppShapes.actionButton,
        enabled = enabled,
        colors = ButtonDefaults.buttonColors(
            containerColor = EmergencyRed,
            contentColor = Color.White,
        ),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp, pressedElevation = 4.dp),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge.copy(fontSize = 15.sp, fontWeight = FontWeight.Bold))
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
fun LoadingState(label: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            Modifier.size(44.dp).clip(CircleShape).background(WhatsAppVibrantGreen.copy(alpha = 0.15f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Outlined.LocationOn, contentDescription = null, tint = WhatsAppVibrantGreen, modifier = Modifier.size(26.dp))
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
            .padding(20.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(Icons.Outlined.Info, contentDescription = null, tint = WhatsAppVibrantGreen, modifier = Modifier.size(28.dp))
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        }
    }
}
