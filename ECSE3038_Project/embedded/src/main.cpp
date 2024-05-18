#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "env.h"

#define LED_BUILTIN 2
#define FAN_PIN 23
#define LED_PIN 22
#define PIR_PIN 15
#define TEMP_SENSOR_PIN 4

bool isConnected = false;
bool motionDetected = false;
float temperature = 0;

const char* endpoint = "https://ecse3038-project-bb.onrender.com/sensorData";

OneWire oneWire(TEMP_SENSOR_PIN);
DallasTemperature sensors(&oneWire);

void post_sensor_data(float temp, bool presence) {
  HTTPClient http;
  StaticJsonDocument<100> doc;

  doc["temp"] = temp;
  doc["presence"] = presence;

  String requestBody;
  serializeJson(doc, requestBody);

  http.begin(endpoint);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(requestBody);

  Serial.print("HTTP Response: ");
  Serial.println(httpResponseCode);
  Serial.println(requestBody);

  http.end();
}

void get_sensor_data() {
  HTTPClient http;

  http.begin(endpoint);

  int httpResponseCode = http.GET();

  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);

    String responseBody = http.getString();
    Serial.println(responseBody);

    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, responseBody);

    if (error) {
      Serial.print("deserializeJson() failed: ");
      Serial.println(error.c_str());
      return;
    }

    bool fanState = doc["fan"];
    bool ledState = doc["led_pin"];

    digitalWrite(FAN_PIN, fanState);
    digitalWrite(LED_PIN, ledState);
  }
  else {
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
  }

  http.end();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(FAN_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT);

  Serial.begin(921600);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.println("Starting");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED && !isConnected) {
    Serial.println("Connected");
    digitalWrite(LED_BUILTIN, HIGH);
    isConnected = true;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi Disconnected");
    digitalWrite(LED_BUILTIN, LOW);
    isConnected = false;
    return;
  }

  if (isConnected) {
    sensors.requestTemperatures();
    temperature = sensors.getTempCByIndex(0);
    motionDetected = digitalRead(PIR_PIN);

    post_sensor_data(temperature, motionDetected);
    get_sensor_data();

    delay(10000); // Limit the frequency of requests to 10 seconds
  }
}
