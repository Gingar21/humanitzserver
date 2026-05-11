import socket
import struct
import sys
import time


# CONFIGURATION 
RCON_IP = "Your server ip"
RCON_PORT =
RCON_PASS = "Your pass"

def send_rcon(cmd):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((RCON_IP, RCON_PORT))
        
        # Auth
        auth_pkt = struct.pack('<ii', 1, 3) + RCON_PASS.encode() + b'\x00\x00'
        sock.sendall(struct.pack('<i', len(auth_pkt)) + auth_pkt)
        sock.recv(4096) # Ignore auth response
        
        # Command
        cmd_pkt = struct.pack('<ii', 2, 2) + cmd.encode() + b'\x00\x00'
        sock.sendall(struct.pack('<i', len(cmd_pkt)) + cmd_pkt)
        sock.recv(4096) # Receive response
        sock.close()
    except:
        pass # Silent if the server has already crashed

if __name__ == "__main__":
    # We warn the players to save an restart
        send_rcon("restart 1")
        time.sleep(30)
        send_rcon("admin Reboot server in 30 Secondes!")
        time.sleep(20)
        send_rcon("save")
        send_rcon("admin Reboot server in 10 Secondes!")
        
        
        
