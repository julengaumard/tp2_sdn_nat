import socket
import time
import sys
from server import TCP_PORT


SERVER_IP = "200.0.0.1"
CANT_MENSAJES = 180
INTERVALO_SEG = 3.0
TIMEOUT = 10.0

def test_mucho_texto():
    print(f"[CLIENTE LENTO] Iniciando conversación de {(INTERVALO_SEG + request_delay) * CANT_MENSAJES} minutos hacia {SERVER_IP}:{TCP_PORT}")
    contador = 1

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT + request_delay)
    s.connect((SERVER_IP, TCP_PORT))

    while contador <= CANT_MENSAJES:
        try:
            mensaje = f"[CLIENTE LENTO] Mensaje #{contador}"
            s.sendall(mensaje.encode())

            respuesta = s.recv(1024)
            print(f"[CLIENTE LENTO] Enviado #{contador} de {CANT_MENSAJES} -> OK Respuesta: {respuesta.decode().strip()}")

            contador += 1
        except Exception as e:
            print(f"[CLIENTE LENTO] Error en transmisión: {e}")
            return

        time.sleep(INTERVALO_SEG + request_delay)

    s.close()
    print(f"[CLIENTE LENTO] Conversación de 10 minutos finalizada con éxito.")

if __name__ == "__main__":
    request_delay = float(sys.argv[1] if len(sys.argv) > 1 else 0)
    sys.stdout = open(f"demora_{request_delay}.log", "w", buffering=1)
    sys.stderr = sys.stdout

    test_mucho_texto()
