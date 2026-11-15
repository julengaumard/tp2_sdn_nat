import socket
import time
import sys
from server import TCP_PORT


SERVER_IP = "200.0.0.1"
DURACION_MINUTOS = 10
INTERVALO_SEG = 3

def test_mucho_texto(client_name):
    print(f"[{client_name}] Iniciando conversación de {DURACION_MINUTOS} minutos hacia {SERVER_IP}:{TCP_PORT}")
    cant_mensajes = int(DURACION_MINUTOS * (60 / INTERVALO_SEG))
    contador = 1

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10.0)
    s.connect((SERVER_IP, TCP_PORT))

    while contador <= cant_mensajes:
        try:
            mensaje = f"[{client_name}] Mensaje #{contador}"
            s.sendall(mensaje.encode())

            respuesta = s.recv(1024)
            print(f"[{client_name}] Enviado #{contador} de {cant_mensajes} -> OK Respuesta: {respuesta.decode().strip()}")

            contador += 1
        except Exception as e:
            print(f"[{client_name}] Error en transmisión: {e}")

        time.sleep(INTERVALO_SEG)

    s.close()
    print(f"[{client_name}] Conversación de 10 minutos finalizada con éxito.")

if __name__ == "__main__":
    nombre = sys.argv[1] if len(sys.argv) > 1 else "Cliente"
    sys.stdout = open(f"convo_{nombre}.log", "w", buffering=1)
    sys.stderr = sys.stdout

    test_mucho_texto(nombre)
