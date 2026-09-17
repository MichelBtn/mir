## mir

### *M*odular *I*ntelligent *R*obot

### construisez votre robot en quelques clics

OS supporté : Linux only

###
installation :  
#### cloner le dépot  
si ce n'est déjà fait créer une clé SSH sur la machine cible:   
ssh-keygen   
valider les options proposées (fichier id_ed25519.pub), notrer le mot de passe si entré (déconseillé)   
copier le contenu du fichier .pub  
ajouter la clé SSH sur github    
git clone git@github.com:MichelBtn/mir.git  

#### activer l'environnement conda lerobot  

#### linux :  
depuis le dossier racine du projet, exécuter install.sh  (faire ./install.sh)

#### windows :  
depuis le dossier racine du projet, exécuter install.bat  

pour réutiliser la librairie mir_utils (pas de dépendance lerobot):   
pip install -e "git+ssh://git@github.com/MichelBtn/mir.git#subdirectory=mir_utils"   
ou en local, après installation comme ci-dessus :
pip install -e /chemin/local/mir/mir_utils   

## Citation

Ce projet utilise [LeRobot](https://github.com/huggingface/lerobot) de HuggingFace.
Si vous utilisez ce projet, merci de citer :

```bibtex
@misc{cadene2024lerobot,
    author = {Cadene, Remi and Alibert, Simon and Soare, Alexander and Gallouedec, Quentin and Zouitine, Adil and Palma, Steven and Kooijmans, Pepijn and Aractingi, Michel and Shukor, Mustafa and Aubakirova, Dana and Russi, Martino and Capuano, Francesco and Pascal, Caroline and Choghari, Jade and Moss, Jess and Wolf, Thomas},
    title = {LeRobot: State-of-the-art Machine Learning for Real-World Robotics in Pytorch},
    howpublished = "\url{https://github.com/huggingface/lerobot}",
    year = {2024}
}
```
