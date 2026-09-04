package org.lifelane.mobile

import com.hivemq.client.mqtt.MqttClient
import com.hivemq.client.mqtt.datatypes.MqttQos
import com.hivemq.client.mqtt.mqtt3.Mqtt3AsyncClient
import java.nio.charset.StandardCharsets
import java.util.UUID
import org.json.JSONObject

class MqttGateway(
    private val ambulanceId: String,
    private val onState: (String) -> Unit,
    private val onJunctionStatus: (JSONObject) -> Unit,
) {
    private var client: Mqtt3AsyncClient? = null

    fun connect() {
        val built = MqttClient.builder()
            .useMqttVersion3()
            .identifier("lifelane-${ambulanceId}-${UUID.randomUUID().toString().take(8)}")
            .serverHost(BuildConfig.MQTT_HOST)
            .serverPort(BuildConfig.MQTT_PORT)
            .automaticReconnectWithDefaultConfig()
            .addConnectedListener { onState("Connected") }
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
            if (error != null) onState("Error: ${error.message}")
            else {
                built.subscribeWith()
                    .topicFilter("lifelane/junction/+/status")
                    .qos(MqttQos.AT_LEAST_ONCE)
                    .callback { publish ->
                        runCatching {
                            val json = JSONObject(String(publish.payloadAsBytes, StandardCharsets.UTF_8))
                            onJunctionStatus(json)
                        }
                    }
                    .send()
                publish("lifelane/ambulance/$ambulanceId/status", "{\"schemaVersion\":1,\"ambulanceId\":\"$ambulanceId\",\"online\":true}", true)
            }
        }
    }

    fun publish(topic: String, payload: String, retained: Boolean = false) {
        val active = client ?: return
        if (active.state.isConnected) {
            active.publishWith()
                .topic(topic)
                .qos(MqttQos.AT_LEAST_ONCE)
                .retain(retained)
                .payload(payload.toByteArray(StandardCharsets.UTF_8))
                .send()
        }
    }

    fun disconnect() {
        client?.disconnect()
        client = null
        onState("Disconnected")
    }
}
