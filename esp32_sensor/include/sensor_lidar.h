#ifndef __sensor__lidar__h__
#define __sensor__lidar__h__

#include "sensor.h"
#include "rplidar.h"

class SensorLidar : public Sensor {
private:
    RPLidar  lidar;
    ScanData scan;
    char     buf[32];

    static constexpr int LIDAR_RX = 16;
    static constexpr int LIDAR_TX = 17;
    
    // Ajout pour le multi-threading
    TaskHandle_t _lidarTaskHandle = nullptr;
    SemaphoreHandle_t _scanMutex = nullptr;
    static void _lidarTask(void* pvParameters); // Tâche statique obligatoire
    
protected:
    virtual bool _add_frame_data(int& pos) override;

public:
    SensorLidar(const char* id);
    void        _update_data()      override;
    bool        init()              override;
    const char* read_data()         override;
    const char* get_data_schema()   override;
    static inline const char* sensor_type() { return "esp_lidar"; }
};

#endif
