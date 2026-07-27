import sys
import tty
import termios
from queue import Queue
from enum import Enum, auto
from pynput import keyboard

class Key(Enum):
    """Énumération des touches supportées"""
    # Lettres
    A = auto()
    B = auto()
    C = auto()
    D = auto()
    E = auto()
    F = auto()
    G = auto()
    H = auto()
    I = auto() # noqa: E741
    J = auto()
    K = auto()
    L = auto()
    M = auto()
    N = auto()
    O = auto() # noqa: E741
    P = auto()
    Q = auto() # noqa: E741
    R = auto()
    S = auto()
    T = auto()
    U = auto()
    V = auto()
    W = auto()
    X = auto()
    Y = auto()
    Z = auto()
    
    # Chiffres
    Digit0 = auto()
    Digit1 = auto()
    Digit2 = auto()
    Digit3 = auto()
    Digit4 = auto()
    Digit5 = auto()
    Digit6 = auto()
    Digit7 = auto()
    Digit8 = auto()
    Digit9 = auto()
    
    # Touches spéciales
    Space = auto()
    Enter = auto()
    Tab = auto()
    Backspace = auto()
    Esc = auto()
    Delete = auto()
    
    # Touches fléchées
    Left = auto()
    Right = auto()
    Up = auto()
    Down = auto()
    
    # Autres
    Plus = auto()
    Minus = auto()
    Dot = auto()
    Comma = auto()
    Colon = auto()
    Semicolon = auto()
    Apostrophe = auto()
    Quote = auto()
    Slash = auto()
    Backslash = auto()
    LBracket = auto()
    RBracket = auto()
    Equal = auto()
    
    # Touches non reconnues
    Unknown = auto()


class KeyboardListener:
    """Capture les touches et les stocke dans une queue non-bloquante"""
    
    def __init__(self):
        self.key_queue = Queue()
        self.listener = None
        self._running = False
        self.old_settings = None  # Pour restaurer le terminal
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.stop()
        except Exception:
            pass  # Silencieux en cas d'erreur
    
    def start(self):
        """Démarre l'écoute des touches en arrière-plan et active le mode raw"""
        if self._running:
            return
        
        # Sauvegarde et activation du mode raw (désactive l'echo)
        try:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
        except Exception:
            pass  # Si pas possible (ex: pas de terminal), on continue quand même
        
        self._running = True
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()
    
    def stop(self):
        """Arrête l'écoute des touches et restaure le terminal"""
        if self._running and self.listener:
            self._running = False
            self.listener.stop()
            self.listener.join(timeout=0.5)  # Attendre que le listener s'arrête
        
        # Restaure les paramètres du terminal
        if self.old_settings:
            try:
                import sys
                sys.stdout.flush()
                sys.stderr.flush()
                # TCSAFLUSH vide aussi le buffer d'entrée
                termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, self.old_settings)
                # Un petit délai pour laisser le terminal se stabiliser
                import time
                time.sleep(0.05)
            except Exception:
                pass
    
    def _on_press(self, key):
        """Callback appelé à chaque touche pressée"""
        parsed_key = self._parse_key(key)
        if parsed_key:
            self.key_queue.put(parsed_key)
    
    def _parse_key(self, pynput_key):
        """Convertit une touche pynput en enum Key"""
        try:
            # Touche avec caractère
            if isinstance(pynput_key, keyboard.Key):
                key_map = {
                    keyboard.Key.left: Key.Left,
                    keyboard.Key.right: Key.Right,
                    keyboard.Key.up: Key.Up,
                    keyboard.Key.down: Key.Down,
                    keyboard.Key.enter: Key.Enter,
                    keyboard.Key.space: Key.Space,
                    keyboard.Key.tab: Key.Tab,
                    keyboard.Key.backspace: Key.Backspace,
                    keyboard.Key.delete: Key.Delete,
                    keyboard.Key.esc: Key.Esc,
                }
                return key_map.get(pynput_key)
            else:
                # pynput.keyboard.KeyCode : caractère pressé
                char = pynput_key.char
                if char is None:
                    return None
                
                # Lettres
                if 'a' <= char <= 'z':
                    return Key[char.upper()]
                if 'A' <= char <= 'Z':
                    return Key[char]
                
                # Chiffres
                if '0' <= char <= '9':
                    return Key[f'Digit{char}']
                
                # Caractères spéciaux
                special_chars = {
                    '+': Key.Plus,
                    '-': Key.Minus,
                    '.': Key.Dot,
                    ',': Key.Comma,
                    ':': Key.Colon,
                    ';': Key.Semicolon,
                    "'": Key.Apostrophe,
                    '"': Key.Quote,
                    '/': Key.Slash,
                    '\\': Key.Backslash,
                    '[': Key.LBracket,
                    ']': Key.RBracket,
                    '=': Key.Equal,
                }
                return special_chars.get(char)
        except AttributeError:
            pass
        
        return None
    
    def get_key(self):
        """
        Retourne la prochaine touche de la queue, ou None si vide.
        Non-bloquant.
        """
        try:
            return self.key_queue.get_nowait()
        except Exception:
            return None
    
    def wait_key(self, timeout=None):
        """
        Attend une touche (bloquant avec timeout optionnel).
        timeout en secondes.
        """
        try:
            return self.key_queue.get(timeout=timeout)
        except Exception:
            return None


# ==================== Exemple d'utilisation ====================
if __name__ == "__main__":
    import time
    
    print("Appuyez sur des touches (q pour quitter) :")
    print("- Flèches gauche/droite/haut/bas")
    print("- Lettres (A-Z)")
    print("- Chiffres (0-9)")
    print("- Espace, Entrée, Échap")
    print()
    
    with KeyboardListener() as kbd:
        while True:
            # Mode non-bloquant : vérifier s'il y a une touche
            key = kbd.get_key()
            
            if key is not None:
                print(f"Touche pressée : {key}\r")
                
                if key == Key.Esc or key == Key.Q:
                    print("Sortie...")
                    break
            else:
                # Pas de touche, faire quelque chose d'autre
                time.sleep(0.01)  # Éviter de consommer 100% CPU

