# HumanitZ Server Manager - Linux

## Lancer le panel

```bash
chmod +x LANCER_PANEL_WEB_LINUX.sh
./LANCER_PANEL_WEB_LINUX.sh
```

Le panel ouvre ensuite `http://127.0.0.1:8765`.

## Construire le binaire Linux

Le binaire Linux doit être construit depuis Linux.

```bash
chmod +x BUILD_LINUX.sh
./BUILD_LINUX.sh
```

Le résultat sera ici :

```bash
dist-linux/server-manager
```

## Notes

- Sous Linux, le lancement serveur génère `start.sh` au lieu de `start.bat`.
- SteamCMD utilise `steamcmd.sh` ou la commande système `steamcmd` si elle existe.
- Pour le bouton Parcourir, installe `zenity` ou `kdialog`, sinon colle le chemin du dossier à la main.
- Les fichiers `data`, `logs` et `mots_interdits.txt` restent à côté du panel ou du binaire.
