# Installation M.I.R

### 1. installer git et lerobot
voir documents installation_lerobot_linux.pdf et installation_lerobot_windows.pdf

--- 

### 2. cloner le dépot  
sous linux : depuis le terminal
sous windows : depuis Miniforge Prompt

si ce n'est déjà fait créer une clé SSH sur la machine cible avec ssh-keygen   
valider les options proposées (fichier id_ed25519.pub), notrer le mot de passe si entré (déconseillé)   
copier le contenu du fichier .pub  
demander à MichelBtn d'ajouter la clé SSH sur github    

```bash
git clone git@github.com:MichelBtn/mir.git  
```

--- 

### 3. installer mir
sous windows, depuis Miniforge Prompt :
aller dans le dossier racine du projet (mir par défaut) et faire :
```bash
conda activate lerobot
install.bat
```
sous linux, depuis le terminal :
aller dans le dossier racine du projet (mir par défaut) et faire :
```bash
conda activate lerobot
./install.sh
```

---
### si problème lié à PySide6 sous windows
message du genre :
*ImportError: DLL load failed while importing QtWidgets: The specified procedure could not be found*

depuis Miniforge prompt :
```bash
pip uninstall -y PySide6 PySide6_Essentials PySide6_Addons
conda install -c conda-forge pyside6
```

### pour réutiliser la librairie mir_utils (pas de dépendance lerobot):   
pip install -e "git+ssh://git@github.com/MichelBtn/mir.git#subdirectory=mir_utils"   
ou en local, après installation comme ci-dessus :
pip install -e /chemin/local/mir/mir_utils   
