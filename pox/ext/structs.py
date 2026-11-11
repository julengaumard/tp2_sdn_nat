import time

MIN_PORT = 10000
MAX_PORT = 60000


# Guarda toda la informacion de un flujo (una fila de la tabla NAT).
class Connection:
    def __init__(self, protocol, src_ip, src_port, dst_ip, dst_port,
                 nat_ip, nat_port):

        self.protocol = protocol

        # Conexión original (lado privado)
        self.src_ip = src_ip
        self.src_port = src_port
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        # Traducción NAT (lado público)
        self.nat_ip = nat_ip
        self.nat_port = nat_port

        # Gestión temporal
        self.created_at = time.time()
        self.last_seen = self.created_at

    def update_last_seen(self):
        self.last_seen = time.time()


# Asigna las tablas de traducción (saliente y entrante) y la asignación de puertos.
class NATTable:
    def __init__(self, nat_ip):
        self.nat_ip = nat_ip

        # Diccionario saliente:
        # key = (protocol, src_ip, src_port, dst_ip, dst_port) -> Connection
        self.connections = {}

        # Diccionario inverso (entrante):
        # reverse_key = (protocol, nat_port, dst_ip, dst_port) -> Connection
        self.reverse_connections = {}

        # Puertos públicos actualmente en uso (por protocolo)
        self.used_ports = {}
        self.next_port = MIN_PORT

    def assign_port(self, protocol):
        if protocol not in self.used_ports:
            self.used_ports[protocol] = set()

        # Busca el proximo puerto libre en el rango [MIN_PORT, MAX_PORT]
        for _ in range(MIN_PORT, MAX_PORT + 1):
            port = self.next_port
            self.next_port += 1
            if self.next_port > MAX_PORT:
                self.next_port = MIN_PORT

            if port not in self.used_ports[protocol]:
                self.used_ports[protocol].add(port)
                return port

        raise RuntimeError("No hay puertos públicos disponibles en el NAT")

    # Para tráfico SALIENTE (red privada -> red pública)
    # Si la conexión ya existe la devuelve; si no, le asigna puerto y la crea.
    def translate_outbound(self, protocol, src_ip, src_port, dst_ip, dst_port):
        key = (protocol, src_ip, src_port, dst_ip, dst_port)

        if key in self.connections:
            conn = self.connections[key]
            conn.update_last_seen()
            return conn

        nat_port = self.assign_port(protocol)
        conn = Connection(
            protocol=protocol,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
            nat_ip=self.nat_ip,
            nat_port=nat_port
        )

        reverse_key = (protocol, nat_port, dst_ip, dst_port)
        self.connections[key] = conn
        self.reverse_connections[reverse_key] = conn

        return conn

    # Para tráfico ENTRANTE (red pública -> red privada)
    # El servidor (remote_ip/remote_port) responde a nuestra IP pública al puerto nat_port.
    def translate_inbound(self, protocol, nat_port, remote_ip, remote_port):
        reverse_key = (protocol, nat_port, remote_ip, remote_port)
        conn = self.reverse_connections.get(reverse_key)
        if conn is not None:
            conn.update_last_seen()
        return conn

    # Libera la conexión de las tablas y devuelve el puerto al pool de disponibles.
    def remove_connection(self, conn):
        key = (conn.protocol, conn.src_ip, conn.src_port, conn.dst_ip, conn.dst_port)
        reverse_key = (conn.protocol, conn.nat_port, conn.dst_ip, conn.dst_port)

        self.connections.pop(key, None)
        self.reverse_connections.pop(reverse_key, None)

        if conn.protocol in self.used_ports:
            self.used_ports[conn.protocol].discard(conn.nat_port)
