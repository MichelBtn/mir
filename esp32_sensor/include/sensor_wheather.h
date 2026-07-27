#ifndef __sensor__wheather__h__
#define __sensor__wheather__h__
#include <Adafruit_AHTX0.h>

#include "sensor.h"

class SensorWheather : public Sensor {
   private:
    Adafruit_AHTX0 aht;
    bool aht_init = false;
    bool bmp_init = false;
    float temperature,rel_humidity;
    char buf[128];
   public:
    SensorWheather(const char* id);
    void _update_data() override;
    bool init() override;
    bool _add_frame_data(int& pos) override;
    const char* read_data() override;
    const char* get_data_schema() override;
    static inline const char* sensor_type() { return "esp_wheather"; }       
};

#endif
