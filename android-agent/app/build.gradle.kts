plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "com.formafx.storyfx.agent"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.formafx.storyfx.agent"
        minSdk = 26
        targetSdk = 35
        versionCode = 23
        versionName = "0.4.18"
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildTypes {
        debug { applicationIdSuffix = ".qa" }
        release { isMinifyEnabled = false }
    }
    testOptions { unitTests.isReturnDefaultValues = true }
}
dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.work:work-runtime:2.9.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
