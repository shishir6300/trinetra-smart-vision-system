#include "esp_camera.h"
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ===========================
// WIFI CONFIG
// ===========================
const char* ssid     = "OnePlus 13R D044";
const char* password = "12345678";

// ===========================
// CAMERA PINS (AI THINKER)
// ===========================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ===========================
// OLED CONFIG
// Text size 2 = 12x16px per char
// 128px wide / 12px = ~10 chars per line
// 64px tall  / 16px =  4 rows, use 3 for padding
// ===========================
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64
#define MAX_LINES       3
#define CHARS_PER_LINE 10   // at text size 2, each char = ~12px

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

String lines[MAX_LINES];
int lineCount = 0;

WiFiServer server(80);

// ===========================
// CAMERA INIT
// ===========================
void startCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size   = FRAMESIZE_VGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.jpeg_quality = 8;
  config.fb_count     = 2;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed");
  }
}

// ===========================
// ADD LINE — shifts up when full (max 3 lines)
// ===========================
void addLine(String text) {
  if (lineCount >= MAX_LINES) {
    for (int i = 0; i < MAX_LINES - 1; i++) lines[i] = lines[i + 1];
    lines[MAX_LINES - 1] = text;
  } else {
    lines[lineCount++] = text;
  }
}

// ===========================
// DISPLAY UPDATE — plain normal text, size 2
// ===========================
void updateDisplay() {
  display.clearDisplay();
  display.setTextSize(2);           // big text — 3 lines fit at 16px each
  display.setTextColor(SSD1306_WHITE);

  for (int i = 0; i < lineCount; i++) {
    display.setCursor(0, i * 21);   // 21px row spacing so lines don't overlap
    display.print(lines[i]);
  }

  display.display();
}

// ===========================
// SETUP
// ===========================
void setup() {
  Serial.begin(115200);

  startCamera();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected!");
  Serial.println(WiFi.localIP());

  Wire.begin(14, 15); // SDA=14, SCL=15

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED failed");
    return;
  }

  display.clearDisplay();
  display.display();

  server.begin();
}

// ===========================
// LOOP
// ===========================
void loop() {
  WiFiClient client = server.available();

  if (client) {
    String request = client.readStringUntil('\r');
    client.flush();

    // --- CAPTURE IMAGE ---
    if (request.indexOf("/capture") != -1) {
      camera_fb_t* fb = nullptr;

      // Flush stale frames
      for (int i = 0; i < 2; i++) {
        fb = esp_camera_fb_get();
        if (fb) esp_camera_fb_return(fb);
      }

      fb = esp_camera_fb_get();
      if (!fb) {
        Serial.println("Capture failed");
        return;
      }

      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: image/jpeg");
      client.println("Content-Length: " + String(fb->len));
      client.println();
      client.write(fb->buf, fb->len);
      esp_camera_fb_return(fb);
    }

    // --- DISPLAY TEXT ---
    else if (request.indexOf("/text") != -1) {
      int start = request.indexOf("msg=") + 4;
      int end   = request.indexOf(" HTTP");

      if (start > 3 && end != -1) {
        String msg = request.substring(start, end);
        msg.replace("+", " ");
        msg.replace("%20", " ");

        Serial.println("MSG: " + msg);

        // Reset display and show new message from scratch
        lineCount = 0;

        // Break message into chunks of CHARS_PER_LINE
        for (int i = 0; i < (int)msg.length(); i += CHARS_PER_LINE) {
          addLine(msg.substring(i, min(i + CHARS_PER_LINE, (int)msg.length())));
        }
      }

      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: text/plain");
      client.println();
      client.println("OK");
    }

    client.stop();
  }

  // Update display every 200ms
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 200) {
    updateDisplay();
    lastUpdate = millis();
  }
}