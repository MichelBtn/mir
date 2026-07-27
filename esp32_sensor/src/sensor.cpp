#include "sensor.h"
#include "esp_timer.h"

const int HEADER_SIZE = 15;

Sensor::Sensor(const char* id, size_t data_buffer_size) {
    strncpy(_id, id, sizeof(_id) - 1);
    _id[sizeof(_id) - 1] = '\0';
    _buffer = (uint8_t*)malloc(data_buffer_size + HEADER_SIZE);
}

uint8_t* Sensor::get_data_frame(uint16_t& len) {
    int pos = 0;
    _buffer[pos++] = MAGIC_0;
    _buffer[pos++] = MAGIC_1;
    memcpy(_buffer + pos, &_id,        1); pos += 1;
    memcpy(_buffer + pos, &_sequence,  4); pos += 4;
    memcpy(_buffer + pos, &timestamp,  8); pos += 8;
    if (!_add_frame_data(pos))
        return nullptr;
    len = pos;
    _sequence++;
    return _buffer;
}

void Sensor::update_data() {
    timestamp = esp_timer_get_time();
    _update_data();
}
