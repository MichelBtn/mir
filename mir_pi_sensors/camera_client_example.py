import requests

BASE_URL = "http://192.168.1.22:8080"   # change si la caméra tourne sur une autre machine

def read_controls():
    r = requests.get(f"{BASE_URL}/controls", timeout=5)
    r.raise_for_status()
    return r.json()

def set_controls(payload):
    r = requests.patch(f"{BASE_URL}/controls", json=payload, timeout=5)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    # 1) Lire les paramètres actuels
    controls = read_controls()
    print("Contrôles actuels :", controls)

    # 2) Modifier quelques paramètres
    new_settings = {
        "ExposureTime": 20000,      # en microsecondes
        "AeEnable": False,
        "FrameDurationLimits": [33333, 33333]
    }

    result = set_controls(new_settings)
    print("Résultat de la mise à jour :", result)

    # 3) Vérifier la nouvelle valeur
    controls_after = read_controls()
    print("Contrôles après modification :", controls_after)