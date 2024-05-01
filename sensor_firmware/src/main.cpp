#include <Arduino.h>

const int lightPin = 0;
int value = 0;

void setup() {
  Serial.begin(9600);
}

void loop() {
    int value = analogRead(lightPin);
    Serial.println(value);
    delay(500);
}