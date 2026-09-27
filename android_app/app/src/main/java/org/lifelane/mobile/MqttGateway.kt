package org.lifelane.mobile

import com.hivemq.client.mqtt.MqttClient
import com.hivemq.client.mqtt.datatypes.MqttQos
import com.hivemq.client.mqtt.mqtt3.Mqtt3AsyncClient
import java.nio.charset.StandardCharsets
import java.util.UUID
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CompletableFuture
import org.json.JSONObject

class MqttGateway(
    private val ambulanceId: String,
    private val onState: (String) -> Unit,
    private val onJunctionStatus: (JSONObject) -> Unit,
    private val onAcknowledgement: (JSONObject) -> Unit,
    private val endpoint: () -> Pair<String, Int> = { Pair(BuildConfig.MQTT_HOST, BuildConfig.MQTT_PORT) },
) {
    private data class PendingPublish(val topic: String, val payload: String, val retained: Boolean)

    @Volatile private var client: Mqtt3AsyncClient? = null
    @Volatile private var generation = UUID.randomUUID()
    private val pending = ConcurrentLinkedQueue<PendingPublish>()
    private val inFlight = ConcurrentLinkedQueue<CompletableFuture<*>>()

    fun connect() {
        if (client?.state?.isConnected == true) return
        val (host, port) = endpoint()
        val session = UUID.randomUUID()
        generation = session
        val built = MqttClient.builder()
            .useMqttVersion3()
            .identifier("lifelane-${ambulanceId}-${UUID.randomUUID().toString().take(8)}")
            .serverHost(host)
            .serverPort(port)
            .automaticReconnectWithDefaultConfig()
            .addConnectedListener {
                if (generation == session) client?.let(::subscribeAndAnnounce)
            }
            .addDisconnectedListener { if (generation == session) onState("Reconnecting") }
            .apply { if (BuildConfig.MQTT_TLS) sslWithDefaultConfig() }
            .buildAsync()
        client = built
        val connect = built.connectWith()
            .keepAlive(30)
            .willPublish()
                .topic("lifelane/ambulance/$ambulanceId/status")
                .qos(MqttQos.AT_LEAST_ONCE)
                .payload("{\"schemaVersion\":1,\"ambulanceId\":\"$ambulanceId\",\"online\":false}".toByteArray())
                .retain(true)
                .applyWillPublish()
        if (BuildConfig.MQTT_USERNAME.isNotBlank()) {
            connect.simpleAuth()
                .username(BuildConfig.MQTT_USERNAME)
                .password(BuildConfig.MQTT_PASSWORD.toByteArray())
                .applySimpleAuth()
        }
        onState("Connecting")
        connect.send().whenComplete { _, error ->
            if (error != null && generation == session) {
                onState("Error: ${error.message ?: "Unable to reach broker"}")
            }
        }
    }

    private fun subscribeAndAnnounce(built: Mqtt3AsyncClient) {
        val status = built.subscribeWith()
            .topicFilter("lifelane/junction/+/status")
            .qos(MqttQos.AT_LEAST_ONCE)
            .callback { publish ->
                runCatching { JSONObject(String(publish.payloadAsBytes, StandardCharsets.UTF_8)) }
                    .onSuccess(onJunctionStatus)
            }.send()
        val acknowledgement = built.subscribeWith()
            .topicFilter("lifelane/junction/+/ack")
            .qos(MqttQos.AT_LEAST_ONCE)
            .callback { publish ->
                runCatching { JSONObject(String(publish.payloadAsBytes, StandardCharsets.UTF_8)) }
                    .onSuccess(onAcknowledgement)
            }.send()
        java.util.concurrent.CompletableFuture.allOf(status, acknowledgement).whenComplete { _, error ->
            if (client !== built) return@whenComplete
            if (error != null) onState("Error: junction subscription failed")
            else {
                onState("Connected")
                sendNow("lifelane/ambulance/$ambulanceId/status",
                    JSONObject().put("schemaVersion", 1).put("ambulanceId", ambulanceId).put("online", true).toString(), true)
                flushPending()
            }
        }
    }

    fun publish(topic: String, payload: String, retained: Boolean = false) {
        if (client?.state?.isConnected == true) sendNow(topic, payload, retained)
        else {
            if (topic.endsWith("/priority") || topic.endsWith("/telemetry2")) return
            if (topic.endsWith("/telemetry")) pending.removeIf { it.topic == topic }
            while (pending.size >= 32) pending.poll()
            pending.add(PendingPublish(topic, payload, retained))
        }
    }

    private fun sendNow(topic: String, payload: String, retained: Boolean) {
        val active = client ?: return
        if (!active.state.isConnected) return
        val sent = active.publishWith()
            .topic(topic)
            .qos(MqttQos.AT_LEAST_ONCE)
            .retain(retained)
            .payload(payload.toByteArray(StandardCharsets.UTF_8))
            .send()
        inFlight.add(sent)
        sent.whenComplete { _, error ->
            inFlight.remove(sent)
            if (error != null && client === active) onState("Error: message delivery failed")
        }
    }

    private fun flushPending() {
        while (client?.state?.isConnected == true) {
            val item = pending.poll() ?: break
            sendNow(item.topic, item.payload, item.retained)
        }
    }

    fun reconnect() {
        val previous = client
        generation = UUID.randomUUID()
        client = null
        previous?.disconnect()
        connect()
    }

    fun disconnect() {
        pending.clear()
        generation = UUID.randomUUID()
        val previous = client
        client = null
        if (previous != null) {
            // Finish lifecycle publishes before closing; graceful MQTT disconnect suppresses the will.
            CompletableFuture.allOf(*inFlight.toTypedArray()).handle { _, _ -> null }
                .thenCompose {
                    if (previous.state.isConnected) previous.publishWith()
                        .topic("lifelane/ambulance/$ambulanceId/status")
                        .qos(MqttQos.AT_LEAST_ONCE).retain(true)
                        .payload(JSONObject().put("schemaVersion", 1).put("ambulanceId", ambulanceId).put("online", false).toString().toByteArray())
                        .send().handle { _, _ -> null }
                    else CompletableFuture.completedFuture(null)
                }.whenComplete { _, _ -> previous.disconnect() }
        }
        onState("Disconnected")
    }
}
