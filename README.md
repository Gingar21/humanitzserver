🛡️ HumanitZ RCON By PolarBear
HumanitZ RCON est un outil d'administration complet conçu pour les serveurs HumanitZ. 
Il combine la puissance du protocole RCON pour les commandes en direct et le protocole SSH/SFTP pour récupérer le chat du jeu en temps réel, même sur un serveur dédié distant.

🚀 Fonctionnalités Principales
1. Gestion RCON (Remote Console)
Connexion Sécurisée : Supporte l'authentification par mot de passe RCON.

Console Interactive : Envoyez n'importe quelle commande manuelle et recevez la réponse du serveur instantanément.

Commandes Prédéfinies : Menu déroulant incluant les commandes essentielles (info, save, season, weather, etc.).

Gestion des Joueurs :

Liste des joueurs connectés mise à jour toutes les 2 secondes.

Boutons d'action rapide pour Kicker ou Bannir un joueur via son SteamID.

2. Monitoring du Chat (via SSH/SFTP)
Lecture Distante : Se connecte à votre serveur dédié (Linux ou Windows Server) via OpenSSH.

Live Chat : Récupère et affiche les messages du chat en jeu sans avoir besoin d'être connecté sur le serveur.

Auto-détection : Scanne automatiquement le dossier des logs pour lire le fichier .log le plus récent.

Optimisation : Ne télécharge que les nouvelles lignes (streaming), économisant ainsi la bande passante.

3. Automatisation & Confort
Sauvegarde Automatique : Toutes vos configurations (IP, Ports, Logins SSH) sont sauvegardées localement dans un fichier server_config.json.

Système de Redémarrage : Fonction intégrée pour programmer un redémarrage du serveur avec un délai personnalisé.

🛠️ Configuration Requise
Côté Serveur (Dédié/VPS)
RCON : Doit être activé dans votre fichier ServerSettings.ini.

OpenSSH Server : Doit être installé et actif (Port 22 par défaut).

Pare-feu : Les ports RCON (ex: 8888) et SSH (22) doivent être ouverts en entrée.

📖 Mode d'emploi
Remplissez les RCON Settings et cliquez sur Connect RCON.

Remplissez les SSH Settings (IP, User, Pass, Port et le chemin des logs) puis cliquez sur Connect SSH.

Le statut passera à ONLINE et vous verrez les joueurs ainsi que le chat s'actualiser automatiquement.

🛠️ Script Start.bat et humanitz_rcon.py

Le fichier start.bat lance le serveur et controle toutes les 60 secondes que le serveur fonctionne. Si il trouve pas le serveur allumé dans les taches de l'os, il le rallume.

Le fichier humanitz_rcon.py sert a sauvegardé le server et redémarré le serveur a une heure défini par vous en fonctionne de l'heure local de votre propre os. Il est lié au start.bat car quand le serveur va se coupé,
le Start.bat va detecté que le processuce Humanitzserver.exe n'existe plus et donc va automatiquement relancé le serveur.
