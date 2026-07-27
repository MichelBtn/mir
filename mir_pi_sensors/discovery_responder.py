import json
import socket
import threading
import logging

DISCOVERY_PORT = 5679
REPLY_PORT     = 5678
MAGIC          = b"mir_discover_request\n"

class DiscoveryResponder:
    """
    Thread UDP en arrière-plan.
    Écoute les broadcasts de découverte et répond avec le profil de l'équipement.
    """
    
    def __init__(self, profile: dict):
        self._profile = profile
        self._thread  = threading.Thread(target=self._listen, daemon=True)

    def update_profile(self, profile: dict):
        self._profile = profile

    def start(self):
        self._thread.start()
        logging.info(f"[Discovery] Responder actif sur port {DISCOVERY_PORT}.")

    def _listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))

        while True:
            try:
                data, (sender_ip, _) = sock.recvfrom(256)
                if data == MAGIC:
                    response = json.dumps(self._profile).encode()
                    sock.sendto(response, (sender_ip, REPLY_PORT))
                    logging.info(f"[Discovery] Requête de {sender_ip} → réponse envoyée")
            except Exception as e:
                logging.warning(f"[Discovery] Erreur : {e}")