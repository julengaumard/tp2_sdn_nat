import time


# Guarda toda la informacion de un flujo.
class Connection:
    def __init__(self, protocol, src_ip, src_port, dst_ip, dst_port,
                 nat_ip, nat_port):

        self.protocol = protocol

        # Conexión original
        self.src_ip = src_ip
        self.src_port = src_port
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        # Traducción NAT
        self.nat_ip = nat_ip
        self.nat_port = nat_port

        # Gestión temporal
        self.created_at = time.time()
        self.last_seen = self.created_at

    def update_last_seen(self):
        self.last_seen = time.time()

# Sí, pero hay una distinción importante: si una conexión venció, no deberías reutilizar automáticamente su entrada NAT para una respuesta entrante
# Tengo que preguntar, como funciona lo del vencimiento en NAT.

# Veo como recomendacion, tener un dict inverso, para las entrantes. (en vez de recorrerlo todo)

# key = (protocol, src_ip, src_port, dst_ip, dst_port)
# self.connections[key] = connection

# reverse_key = (protocol, nat_port, dst_ip, dst_port)
# self.reverse_connections[reverse_key] = connection


# Talvez una clase que englobe esos dicts, asi 
    # Hay metodos que manejan ambas
        # Que buscan, agregan, etc
    # Un metodo para chequear que no se esta usando el Puerto_externo:Protocolo
        # Etc