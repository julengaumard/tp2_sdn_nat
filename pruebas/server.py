import socket
import threading
import time
import sys


TCP_PORT = 49152
UDP_PORT = 49152

def handle_tcp(conn, addr):
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[SERVER TCP] Datos recibidos de {addr}: {data.decode().strip()}")
            conn.sendall(b"ACK_TCP: " + data)
    except Exception as e:
        print(f"[SERVER TCP] Conexión interrumpida con {addr}: {e}")
    finally:
        conn.close()
        print(f"[SERVER TCP] Conexión cerrada para {addr}")

def run_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", TCP_PORT))
    server.listen(10)
    print(f"[SERVER TCP] Escuchando en el puerto {TCP_PORT}...")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_tcp, args=(conn, addr), daemon=True).start()

def run_udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("0.0.0.0", UDP_PORT))
    print(f"[SERVER UDP] Escuchando en el puerto {UDP_PORT}...")
    while True:
        data, addr = server.recvfrom(1024)
        print(f"[SERVER UDP] Paquete recibido de {addr}: {data.decode().strip()}")
        server.sendto(b"ACK_UDP: " + data, addr)

if __name__ == "__main__":
    sys.stdout = open("server.log", "w", buffering=1)
    sys.stderr = sys.stdout

    threading.Thread(target=run_tcp_server, daemon=True).start()
    threading.Thread(target=run_udp_server, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServidor detenido.")
