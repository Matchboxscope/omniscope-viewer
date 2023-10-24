#include "esp_camera.h"
#include <WiFi.h>
#include <Preferences.h>
#include <ESPAsyncWebServer.h>
#include "camerapins.h"
#include <ArduinoOTA.h>
#include <ESP32Ping.h>

#include <WebSocketsClient.h>

AsyncWebServer server(80);
Preferences preferences;
WiFiClient mWifiClient;

const char* ssid = "BenMur"; // "omniscope"; //"Blynk1";
const char* password = "MurBen3128"; //"omniscope"; //"12345678";
const char* websockets_server_host_default = "192.168.2.191"; //"192.168.0.176"; //"192.168.0.176"; //BLYNK: "192.168.43.235"; //CHANGE HERE
const char* websockets_server_host = "0.0.0.0"; //"192.168.0.176"; //"192.168.0.176"; //BLYNK: "192.168.43.235"; //CHANGE HERE
const uint16_t serverPort = 3333; //CHANGE HERE
uint32_t cameraPort = 8001; // default port

long tLastConnected = 0;
long timeoutSocketConnection = 5000; // ms

using namespace websockets;
WebsocketsClient wsclient;

void setup() {
  Serial.begin(115200);
  initCamera();
  // get previously stored serverIP
  preferences.begin("network", false);
  websockets_server_host = preferences.getString("wshost", websockets_server_host).c_str();
  preferences.end();
  if(not isValidIP(websockets_server_host)){
    Serial.println("IP from Prefs not valid, switching to defaultx");
    Serial.println(websockets_server_host_default);
    websockets_server_host = websockets_server_host_default;
  }

  Serial.print("websockets_server_host: ");
  Serial.println(websockets_server_host);

  //scanWifi();
  initWifi();
  pingServer();
  //initServer();
  cameraPort = 8000 + createUniqueID();
  announceCameraPort();


  // Setup Websocket client
  //cameraSocketConnect();

  // server address, port and URL
  webSocket.begin(websockets_server_host_default, cameraPort, "/");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);

  // indicate wifi LED
  ledcSetup(LED_LEDC_CHANNEL, 5000, 8);
  ledcAttachPin(LED_GPIO_NUM, LED_LEDC_CHANNEL);

  // Start Arduino OTA
  ArduinoOTA.setHostname("esp32-ota");
  ArduinoOTA.begin();   // Port defaults to 3232

}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {

  switch(type) {
    case WStype_DISCONNECTED:
      Serial.printf("[WSc] Disconnected!\n");
      break;
    case WStype_CONNECTED: {
      Serial.printf("[WSc] Connected to url: %s\n", payload);
    }
      break;
    case WStype_TEXT:
      Serial.printf("[WSc] get text: %s\n", payload);
      break;
    case WStype_BIN:
      Serial.printf("[WSc] get binary length: %u\n", length);
      break;
    case WStype_PING:
        // pong will be send automatically
        Serial.printf("[WSc] get ping\n");
        break;
    case WStype_PONG:
        // answer to a ping we send
        Serial.printf("[WSc] get pong\n");
        break;
    }
}
bool pingServer(){
    // Ping socket server
  bool success = Ping.ping(websockets_server_host, 3);
  if(!success){
      Serial.println("Ping failed");
      return false;
  }
  else{
    Serial.println("Ping succesful.");
    return true;
  }
  return true;

}

void cameraSocketConnect() {


  Serial.print("Connecting to CameraSocket on port");
  Serial.println(cameraPort);
  int nConnectionTrials = 0;
}


void announceCameraPort() {
  // Announce camera port via socket connection
  Serial.print("Announcing the camera port: ");
  Serial.println(cameraPort);
  while (!mWifiClient.connect(websockets_server_host, serverPort)) {
    Serial.print(".");
    delay(500);
  }
  mWifiClient.print(cameraPort);
  Serial.println("Camera Port sent");
  mWifiClient.stop();
}

void loop() {


  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wifi connection lost, restarting");
    ledcWrite(LED_LEDC_CHANNEL, 255);
    ESP.restart();
  }
  {
    // indicate we are connected to the  WIFI
    ledcWrite(LED_LEDC_CHANNEL, 0);
    ArduinoOTA.handle();
  }

  // Check if the client is still connected
  /*if (!mWifiClient.connected() and (millis()-tLastConnected)>timeoutSocketConnection) {
    Serial.println("Client disconnected");
    // reconnect
    announceCameraPort();
    cameraSocketConnect();
  }*/

    webSocket.loop();
    uint64_t now = millis();

    if(now - messageTimestamp > 30) {
        messageTimestamp = now;

        camera_fb_t * fb = NULL;

        // Take Picture with Camera
        fb = esp_camera_fb_get();
        if(!fb) {
          Serial.println("Camera capture failed");
          return;
        }

        webSocket.sendBIN(fb->buf,fb->len);
        esp_camera_fb_return(fb);
    }
}


bool isValidIP(const String &str) {
  int parts[4] = {0};
  int partCount = 0;

  for (uint16_t i = 0; i < str.length(); i++) {
    char c = str.charAt(i);
    if (c == '.') {
      if (parts[partCount] > 255) return false;
      partCount++;
      if (partCount > 3) return false;
    } else if (c >= '0' && c <= '9') {
      parts[partCount] = parts[partCount] * 10 + (c - '0');
    } else {
      return false;
    }
  }

  if (partCount != 3 || parts[3] > 255) return false;

  return true;
}

void initServer() {


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
}

void  initWifi() {

  Serial.println("Connecting to Wifi");
  WiFi.begin(ssid, password);
  WiFi.setSleep(false);
  int iWifiTrial = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    iWifiTrial ++;
    if (iWifiTrial > 10)
      ESP.restart();
  }
  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("Camera Stream Ready! Go to: http://");
  Serial.println(WiFi.localIP());

}

void initCamera() {
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
  config.pixel_format = PIXFORMAT_JPEG; // for streaming
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  /*
     FRAMESIZE_UXGA (1600 x 1200)
    FRAMESIZE_QVGA (320 x 240)
    FRAMESIZE_CIF (352 x 288)
    FRAMESIZE_VGA (640 x 480)
    FRAMESIZE_SVGA (800 x 600)
    FRAMESIZE_XGA (1024 x 768)
    FRAMESIZE_SXGA (1280 x 1024)
  */
  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if (psramFound()) {
    config.jpeg_quality = 10;
    config.fb_count = 2;
    config.grab_mode = CAMERA_GRAB_LATEST;
    config.frame_size = FRAMESIZE_QVGA; //iFRAMESIZE_UXGA;
  } else {
    Serial.println("NO PSRAM");
    // Limit the frame size when PSRAM is not available
    config.frame_size = FRAMESIZE_QVGA;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }


  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }


}


void scanWifi() {
  Serial.println("Scan start");

  // WiFi.scanNetworks will return the number of networks found.
  int n = WiFi.scanNetworks();
  Serial.println("Scan done");
  if (n == 0) {
    Serial.println("no networks found");
  } else {
    Serial.print(n);
    Serial.println(" networks found");
    Serial.println("Nr | SSID                             | RSSI | CH | Encryption");
    for (int i = 0; i < n; ++i) {
      // Print SSID and RSSI for each network found
      Serial.printf("%2d", i + 1);
      Serial.print(" | ");
      Serial.printf("%-32.32s", WiFi.SSID(i).c_str());
      Serial.print(" | ");
      Serial.printf("%4d", WiFi.RSSI(i));
      Serial.print(" | ");
      Serial.printf("%2d", WiFi.channel(i));
      Serial.print(" | ");
      switch (WiFi.encryptionType(i))
      {
        case WIFI_AUTH_OPEN:
          Serial.print("open");
          break;
        case WIFI_AUTH_WEP:
          Serial.print("WEP");
          break;
        case WIFI_AUTH_WPA_PSK:
          Serial.print("WPA");
          break;
        case WIFI_AUTH_WPA2_PSK:
          Serial.print("WPA2");
          break;
        case WIFI_AUTH_WPA_WPA2_PSK:
          Serial.print("WPA+WPA2");
          break;
        case WIFI_AUTH_WPA2_ENTERPRISE:
          Serial.print("WPA2-EAP");
          break;
        case WIFI_AUTH_WPA3_PSK:
          Serial.print("WPA3");
          break;
        case WIFI_AUTH_WPA2_WPA3_PSK:
          Serial.print("WPA2+WPA3");
          break;
        case WIFI_AUTH_WAPI_PSK:
          Serial.print("WAPI");
          break;
        default:
          Serial.print("unknown");
      }
      Serial.println();
      delay(10);
    }
  }
  Serial.println("");

  // Delete the scan result to free memory for code below.
  WiFi.scanDelete();
}


uint32_t createUniqueID() {
  uint64_t mac = ESP.getEfuseMac(); // Get MAC address
  uint32_t upper = mac >> 32; // Get upper 16 bits
  uint32_t lower = mac & 0xFFFFFFFF; // Get lower 32 bits
  uint32_t uid = upper ^ lower; // XOR upper and lower parts to get a 32-bit result
  return uid%1000;
}
