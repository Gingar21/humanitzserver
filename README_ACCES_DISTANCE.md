# Accès distant au panel

## Adresse à utiliser

Depuis ton PC/téléphone, ouvre :

```text
http://IP_DU_SERVEUR:8765
```

Exemple :

```text
http://192.168.1.50:8765
```

ou sur un serveur dédié public :

```text
http://123.45.67.89:8765
```

## Windows

Lance le panel avec :

```bat
LANCER_PANEL_PUBLIC_WINDOWS.bat
```

Puis ouvre le port `8765` dans le pare-feu Windows.

Commande possible en administrateur :

```bat
netsh advfirewall firewall add rule name="HumanitZ Panel 8765" dir=in action=allow protocol=TCP localport=8765
```

## Linux

Lance le panel avec :

```bash
chmod +x LANCER_PANEL_PUBLIC_LINUX.sh
./LANCER_PANEL_PUBLIC_LINUX.sh
```

Ouvre le port selon ton pare-feu.

Avec UFW :

```bash
sudo ufw allow 8765/tcp
```

Avec firewalld :

```bash
sudo firewall-cmd --add-port=8765/tcp --permanent
sudo firewall-cmd --reload
```

## Important sécurité

Ne laisse pas ce panel ouvert à tout Internet sans protection.

Recommandé :

- mettre un mot de passe panel fort
- limiter le port `8765` à ton IP si possible
- utiliser un VPN comme Tailscale/WireGuard
- ou passer par un reverse proxy HTTPS avec authentification
