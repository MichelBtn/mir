#include "sensor_lidar.h"

SensorLidar::SensorLidar(const char* id) : Sensor(id, MAX_SCAN_POINTS * sizeof(ScanPoint) + 2), lidar(Serial2) {
    scan.count = 0;
    _scanMutex = xSemaphoreCreateMutex();    
}

void SensorLidar::_update_data() {
}

bool SensorLidar::_add_frame_data(int& pos) {
    if (xSemaphoreTake(_scanMutex, pdMS_TO_TICKS(5)) != pdTRUE) {
        return false; // Évite de bloquer la loop principale si le mutex est pris
    }

    if (scan.count == 0) {
        xSemaphoreGive(_scanMutex);
        return false;
    }
    memcpy(_buffer + pos, &scan.count, sizeof(uint16_t));
    pos += sizeof(uint16_t);
    memcpy(_buffer + pos, scan.points, scan.count * sizeof(ScanPoint));
    pos += scan.count * sizeof(ScanPoint);
    scan.count = 0;
    xSemaphoreGive(_scanMutex);    
    return true;
}

bool SensorLidar::init() {
    //supposant une mise sous tension simultanée de l'esp et du lidar,
    //on laisse le temps au lidar de démarrer
    delay(500);
    Serial.println("--- Initialisation RPLidar C1 ---");
    Serial2.setRxBufferSize(4096);
    lidar.begin(460800, 3000, LIDAR_RX, LIDAR_TX);
    LidarInfo info;
    if (lidar.getInfo(info))
        Serial.printf("Modèle: %d  FW: %d.%d  S/N: %s\n",
                      info.model, info.firmware_major, info.firmware_minor,
                      info.serialnumber);
    else {
        Serial.println("Impossible de récupérer les infos du Lidar.");
        return false;
    }
    lidar.startMotor();
    if (!lidar.startScan()) {
        Serial.println("Erreur au démarrage du scan.");
        return false;
    }

    // Création de la tâche de fond qui va "aspirer" le flux à haute priorité
    xTaskCreatePinnedToCore(
        SensorLidar::_lidarTask,   // Fonction de la tâche
        "lidar_task",              // Nom
        4096,                      // Stack size
        this,                      // Passer l'instance courante en paramètre
        3,                         // Priorité élevée (supérieure à la loop standard)
        &_lidarTaskHandle, 
        0                          // Core 1 (ou 0 selon l'usage WiFi)
    );    


    Serial.println("Scan démarré.");
    return true;
}

// Implémentation de la tâche de fond
void SensorLidar::_lidarTask(void* pvParameters) {
    SensorLidar* instance = static_cast<SensorLidar*>(pvParameters);
    ScanData local_scan;

    while (true) {
        // updateScan devient non-bloquant et s'exécute dès que des octets arrivent
        if (instance->lidar.updateScan(local_scan)) {
            local_scan.timestamp = millis();
            // Une rotation complète est prête, on met à jour la variable partagée sous Mutex
            if (xSemaphoreTake(instance->_scanMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                instance->scan = local_scan;
                xSemaphoreGive(instance->_scanMutex);
            }
        }
        // Un très court délai pour laisser l'IDLE task s'exécuter et éviter le Watchdog
        vTaskDelay(pdMS_TO_TICKS(1)); 
    }
}

const char* SensorLidar::read_data() {
    return "lidar: use TCP data stream on port 5001";
}

const char* SensorLidar::get_data_schema() {
    return "magic(2)+id(1)+seq(4)+ts(8)+count(2)+points[quality(1)+angle(2)+dist(2)]";
}


