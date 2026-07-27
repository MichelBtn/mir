#ifndef __sensor__simulation__h__
#define __sensor__simulation__h__
#include "sensor.h"

class SensorSimulation : public Sensor {
private:
    float omega;
    float theta;
    char buf[32];
 public:
 SensorSimulation(const char* id);
    void _update_data() override;
    bool init() override;
    bool _add_frame_data(int& pos) override;
    const char* read_data() override;
    static inline const char* sensor_type() { return "esp_simulation"; }  
};

#endif

