import socket
import sys
from server import TCP_PORT, UDP_PORT


SERVER_IP = "200.0.0.1"

def probar_tcp():
    print("[TEST] Probando Tráfico TCP...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect((SERVER_IP, UDP_PORT))

        s.sendall(b"Mensaje de prueba tipo TCP")

        respuesta = s.recv(1024)
        print(f"[TEST ÉXITO] Respuesta por TCP: {respuesta.decode().strip()}")
        s.close()
    except Exception as e:
        print(f"[TEST ERROR] Error en tráfico TCP: {e}")

def probar_udp():
    print("[TEST] Probando Tráfico UDP...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3.0)

        s.sendto(b"Mensaje de prueba tipo UDP", (SERVER_IP, UDP_PORT))

        respuesta, _ = s.recvfrom(1024)
        print(f"[TEST ÉXITO] Respuesta por UDP: {respuesta.decode().strip()}")
        s.close()
    except Exception as e:
        print(f"[TEST ERROR] Error en tráfico UDP: {e}")

if __name__ == "__main__":
    sys.stdout = open("test_tipos_trafico.log", "w", buffering=1)
    sys.stderr = sys.stdout

    print("[TEST] Probando diferentes tipos de tráfico...")
    probar_tcp()
    probar_udp()
