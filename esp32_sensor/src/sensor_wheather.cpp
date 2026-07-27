#include "sensor_wheather.h"

SensorWheather::SensorWheather(const char* id) : Sensor(id, 22) {

}

void SensorWheather::_update_data() {
    if (aht_init) {
        sensors_event_t humidity, temp;
        aht.getEvent(&humidity, &temp);
        temperature = temp.temperature;
        rel_humidity = humidity.relative_humidity;
    }
}

bool SensorWheather::init() {
    Wire.begin(21, 22);

    if (aht.begin(&Wire)) {
        Serial.println("wheather_sensor. ahtx0 initialized.");
        aht_init = true;
    } else {
        Serial.println("wheather_sensor. ahtx0 failed to initialize.");
        aht_init = false;
    }
    return aht_init;
}

bool SensorWheather::_add_frame_data(int& pos) {
    uint16_t data_len = 4;
    memcpy(_buffer + pos, &data_len, sizeof(uint16_t));
    pos += sizeof(uint16_t);
    memcpy(_buffer + pos, &temperature, 4);
    pos += 4;
    memcpy(_buffer + pos, &rel_humidity, 4);
    pos += 4;
    return true;
}

const char* SensorWheather::read_data() {
    sprintf(buf,
            "%" PRIu64 ";%.1f;%.0f",
            timestamp, temperature, rel_humidity);
    return buf;
}
