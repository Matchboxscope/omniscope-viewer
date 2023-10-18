#include "esp_camera.h"
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <Preferences.h>
#include <ESPAsyncWebServer.h>
#include "camerapins.h"

AsyncWebServer server(80);
Preferences preferences;
WiFiClient mWifiClient;

const char* ssid = "Blynk1";
const char* password = "12345678";
const char* websockets_server_host = "192.168.43.235"; //CHANGE HERE
const uint16_t serverPort = 3333; //CHANGE HERE
const uint16_t cameraPort = 8002;

using namespace websockets;
WebsocketsClient client;
bool isWebSocketConnected;





void setup() {

  isWebSocketConnected = false;
  Serial.begin(115200);
  initCamera();
  // get previously stored serverIP
  /*
     preferences.begin("network", false);
    websockets_server_host = preferences.getString("wshost", websockets_server_host);
    preferences.end();
  */
  Serial.print("websockets_server_host : ");
  Serial.println(websockets_server_host);

  scanWifi();
  initWifi();
  initServer();
  announceCameraPort();


  // Setup Websocket client
  //mWifiClient.onEvent(onEventsCallback);
  cameraSocketConnect();

}


void cameraSocketConnect() {
  Serial.println("Connecting to CameraSocket");
  int nConnectionTrials = 0;
  while (!mWifiClient.connect(websockets_server_host, cameraPort)) {
    delay(500);
    Serial.print(".");
    if (nConnectionTrials > 10) {
      announceCameraPort();
      nConnectionTrials = 0;
    }
    nConnectionTrials++;
  }
  Serial.println("Websocket Connected!");
  isWebSocketConnected = true;
}

void onEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    Serial.println("Connection Opened");
    isWebSocketConnected = true;
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    Serial.println("Connection Closed");
    //isWebSocketConnected = false;
    //webSocketConnect();
  }
}

void announceCameraPort() {
  // Announce camera port via socket connection
  Serial.println("Announcing the camera port");
  while (!mWifiClient.connect(websockets_server_host, serverPort)) {
    Serial.print(".");
  }
  mWifiClient.print(cameraPort);

  // Receive the reply from the server
  byte reply_bytes[4];
  mWifiClient.readBytes(reply_bytes, 4);

  // Convert the reply to an integer
  int reply_int = (int)reply_bytes[0] << 24 |
                  (int)reply_bytes[1] << 16 |
                  (int)reply_bytes[2] << 8 |
                  (int)reply_bytes[3];

  // Print the received port number
  Serial.print("Received port number: ");
  Serial.println(reply_int);

  mWifiClient.stop();

}

void loop() {

  if(!WiFi.status() != WL_CONNECTED)
     ESP.restart();
  // Check if the client is still connected
  if (!mWifiClient.connected()) {
    Serial.println("Client disconnected");
    // reconnect
    announceCameraPort();
    cameraSocketConnect();
  }

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

  // Send the frame over the socket
  mWifiClient.write((const char*) fb->buf, fb->len);
  //client.sendBinary((const char*) fb->buf, fb->len);
  esp_camera_fb_return(fb);

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
    if(iWifiTrial>10)
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
  return upper ^ lower; // XOR upper and lower parts to get a 32-bit result
}
