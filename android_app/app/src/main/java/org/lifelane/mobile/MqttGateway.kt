package org.lifelane.mobile

import com.hivemq.client.mqtt.MqttClient
import com.hivemq.client.mqtt.datatypes.MqttQos
import com.hivemq.client.mqtt.mqtt3.Mqtt3AsyncClient
import java.nio.charset.StandardCharsets
import java.util.UUID
import java.util.concurrent.ConcurrentLinkedQueue
import org.json.JSONObject

class MqttGateway(
    private val ambulanceId: String,
    private val onState: (String) -> Unit,
    private val onJunctionStatus: (JSONObject) -> Unit,
) {
    private data class PendingPublish(val topic: String, val payload: String, val retained: Boolean)

    private var client: Mqtt3AsyncClient? = null
    private val pending = ConcurrentLinkedQueue<PendingPublish>()

    fun connect() {
        if (client?.state?.isConnected == true) return
        val built = MqttClient.builder()
            .useMqttVersion3()
            .identifier("lifelane-${ambulanceId}-${UUID.randomUUID().toString().take(8)}")
            .serverHost(BuildConfig.MQTT_HOST)
            .serverPort(BuildConfig.MQTT_PORT)
            .automaticReconnectWithDefaultConfig()
            .addConnectedListener {
                onState("Connected")
                flushPending()
            }
            .addDisconnectedListener { onState("Reconnecting") }
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
            if (error != null) {
                onState("Error: ${error.message ?: "Unable to reach broker"}")
            } else {
                built.subscribeWith()
                    .topicFilter("lifelane/junction/+/status")
                    .qos(MqttQos.AT_LEAST_ONCE)
                    .callback { publish ->
                        runCatching {
                            JSONObject(String(publish.payloadAsBytes, StandardCharsets.UTF_8))
                        }.onSuccess(onJunctionStatus)
                    }
                    .send()
                sendNow(
                    "lifelane/ambulance/$ambulanceId/status",
                    "{\"schemaVersion\":1,\"ambulanceId\":\"$ambulanceId\",\"online\":true}",
                    true,
                )
                flushPending()
            }
        }
    }

    fun publish(topic: String, payload: String, retained: Boolean = false) {
        if (client?.state?.isConnected == true) sendNow(topic, payload, retained)
        else pending.add(PendingPublish(topic, payload, retained))
    }

    private fun sendNow(topic: String, payload: String, retained: Boolean) {
        val active = client ?: return
        if (!active.state.isConnected) return
        active.publishWith()
            .topic(topic)
            .qos(MqttQos.AT_LEAST_ONCE)
            .retain(retained)
            .payload(payload.toByteArray(StandardCharsets.UTF_8))
            .send()
    }

    private fun flushPending() {
        while (client?.state?.isConnected == true) {
            val item = pending.poll() ?: break
            sendNow(item.topic, item.payload, item.retained)
        }
    }

    fun reconnect() {
        client?.disconnect()
        client = null
        connect()
    }

    fun disconnect() {
        pending.clear()
        client?.disconnect()
        client = null
        onState("Disconnected")
    }
}
