import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use(::load)
}

android {
    namespace = "org.lifelane.mobile"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.lifelane.mobile"
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "1.2"
        buildConfigField("String", "MQTT_HOST", "\"${localProperties.getProperty("lifelane.mqtt.host", "10.0.2.2")}\"")
        buildConfigField("int", "MQTT_PORT", localProperties.getProperty("lifelane.mqtt.port", "1883"))
        buildConfigField("String", "MQTT_USERNAME", "\"${localProperties.getProperty("lifelane.mqtt.username", "")}\"")
        buildConfigField("String", "MQTT_PASSWORD", "\"${localProperties.getProperty("lifelane.mqtt.password", "")}\"")
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    packaging {
        resources.excludes += setOf(
            "/META-INF/{AL2.0,LGPL2.1}",
            "META-INF/INDEX.LIST",
            "META-INF/io.netty.versions.properties",
        )
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.google.android.gms:play-services-location:21.3.0")
    implementation("com.hivemq:hivemq-mqtt-client:1.3.3")
}
