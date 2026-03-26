#include <driver/i2s.h>

// -------- PIR --------
#define PIR_PIN 13

// -------- I2S MIC --------
#define I2S_WS 25
#define I2S_SD 33
#define I2S_SCK 26

#define I2S_PORT I2S_NUM_0
#define SAMPLE_BUFFER_SIZE 512

int16_t sBuffer[SAMPLE_BUFFER_SIZE];

void setupI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
    .use_apll = false
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = -1,
    .data_in_num = I2S_SD
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
}

void setup() {
  Serial.begin(115200);

  pinMode(PIR_PIN, INPUT);

  setupI2S();

  Serial.println("System Started...");
}

void loop() {

  // -------- PIR Motion --------
  int motion = digitalRead(PIR_PIN);

  // -------- MIC Reading --------
  size_t bytesRead;
  i2s_read(I2S_PORT, &sBuffer, sizeof(sBuffer), &bytesRead, portMAX_DELAY);

  int samples = bytesRead / 2;
  long sum = 0;

  for (int i = 0; i < samples; i++) {
    sum += abs(sBuffer[i]);
  }

  int soundLevel = sum / samples;

  // -------- Output --------
  Serial.print("Motion: ");
  Serial.print(motion);

  Serial.print(" | Sound Level: ");
  Serial.println(soundLevel);

  // -------- Breathing Detection Logic --------
  if (soundLevel > 2000) {
    Serial.println("Breathing Detected");
  }

  if (motion == HIGH) {
    Serial.println("Motion Detected");
  }

  delay(200);
}