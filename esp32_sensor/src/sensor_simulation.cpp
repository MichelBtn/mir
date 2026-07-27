#include "sensor_simulation.h"


SensorSimulation::SensorSimulation(const char* id) : Sensor(id, 10) {
}

void SensorSimulation::_update_data() {
    double t = timestamp / 1000000.0;
    omega = sin(3.14159 * t);  // 2 Hz
    theta = 0.5 * cos(3.14159 * t);
}

bool SensorSimulation::init() {
    Serial.println("simulation_sensor initialized.");
    return true;
}

bool SensorSimulation::_add_frame_data(int& pos) {
    uint16_t data_len = 2;
    memcpy(_buffer + pos, &data_len, sizeof(uint16_t));
    pos += sizeof(uint16_t);
    memcpy(_buffer + pos, &omega, 4);
    pos += 4;
    memcpy(_buffer + pos, &theta, 4);
    pos += 4;
    return true;
}

const char* SensorSimulation::read_data() {
    sprintf(buf, "%" PRIu64 ";%.3f;%.3f", timestamp, omega, theta);
    return buf;
}

const char* SensorSimulation::get_data_schema() {
    return "omega,-1,1;theta,-1,1";
}

