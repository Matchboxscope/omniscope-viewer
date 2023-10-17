#include "esp_camera.h"
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include <ESPAsyncWebServer.h>
#include <WiFi.h>
#include <WebSocketsServer.h>
#include <Preferences.h>


#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39

#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

#define LED_GPIO_NUM      21


AsyncWebServer server(80);
Preferences preferences;
const char* ssid = "BenMur"; //"Blynk";
const char* password = "MurBen3128"; //"12345678";
const char* websockets_server_host = "192.168.137.53"; //CHANGE HERE
const uint16_t websockets_server_port = 3001; // OPTIONAL CHANGE


using namespace websockets;
WebsocketsClient client;
bool isWebSocketConnected;

uint32_t createUniqueID() {
  uint64_t mac = ESP.getEfuseMac(); // Get MAC address
  uint32_t upper = mac >> 32; // Get upper 16 bits
  uint32_t lower = mac & 0xFFFFFFFF; // Get lower 32 bits
  return upper ^ lower; // XOR upper and lower parts to get a 32-bit result
}


void onEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    Serial.println("Connection Opened");
    isWebSocketConnected = true;
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    Serial.println("Connection Closed");
    isWebSocketConnected = false;
    webSocketConnect();
  }
}

void setup() {
  isWebSocketConnected = false;
  Serial.begin(115200);
  Serial.print("START");
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG; // for streaming
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
      config.frame_size = FRAMESIZE_QVGA; //iFRAMESIZE_UXGA;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    // Best option for face detection/recognition
    config.frame_size = FRAMESIZE_240X240;
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  // get previously stored serverIP
  /*
   * preferences.begin("network", false);
  websockets_server_host = preferences.getString("wshost", websockets_server_host);
  preferences.end();
  */
  Serial.print("websockets_server_host : ");
  Serial.println(websockets_server_host);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.print("Camera Stream Ready! Go to: http://");
  Serial.print(WiFi.localIP());



  // Setup Web server
  Serial.println("Staring Server");
  // Modify /setServer to handle HTTP_GET
  server.on("/setServer", HTTP_GET, [](AsyncWebServerRequest * request) {
    String message;
    Serial.println("setServer");

    // Check if query parameter server exists
    if (request->hasParam("server")) {
      String serverIP = request->getParam("server")->value();
      Serial.println(serverIP);

      preferences.begin("network", false);
      preferences.putString("wshost", serverIP);
      preferences.end();


      message = "{\"success\":\"server IP updated\"}";
      request->send(200, "application/json", message);

      // Restart the ESP
      ESP.restart();

    } else {
      message = "{\"error\":\"No server IP provided\"}";
    }

    request->send(200, "application/json", message);
  });

  server.on("/getId", HTTP_GET, [](AsyncWebServerRequest * request) {
    uint32_t uniqueId = createUniqueID();
    String message = "{\"id\":\"" + String(uniqueId) + "\"}";
    request->send(200, "application/json", message);
  });

  server.begin();


  client.onEvent(onEventsCallback);
  webSocketConnect();
}

void onWebSocketEvent(WebsocketsEvent event, WebsocketsClient& client, WebsocketsMessage message) {
  // Handle WebSocket events here
  Serial.println("EVENT");
}

void webSocketConnect() {


  while (!client.connect(websockets_server_host, websockets_server_port, "/")) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("Websocket Connected!");
}

void loop() {

  if (client.available()) {
    client.poll();
  }

  if (!isWebSocketConnected) return;

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    esp_camera_fb_return(fb);
    return;
  }

  if (fb->format != PIXFORMAT_JPEG) {
    Serial.println("Non-JPEG data not implemented");
    return;
  }

  fb->buf[12] = createUniqueID(); //FIRST CAM
  //fb->buf[12] = 0x02; //SECOND CAM

  client.sendBinary((const char*) fb->buf, fb->len);
  esp_camera_fb_return(fb);
}
