import socket
import sys
from server import TCP_PORT


SERVER_IP = "200.0.0.1"

def test_conectividad():
    print("[TEST] Probando conectividad básica...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect((SERVER_IP, TCP_PORT))

        s.sendall(b"Conectividad basica")

        respuesta = s.recv(1024)
        print(f"[TEST ÉXITO] Respuesta recibida del servidor: {respuesta.decode().strip()}")
        s.close()
    except Exception as e:
        print(f"[TEST ERROR] Falló la conectividad básica: {e}")

if __name__ == "__main__":
    sys.stdout = open("test_conectividad.log", "w", buffering=1)
    sys.stderr = sys.stdout

    test_conectividad()
