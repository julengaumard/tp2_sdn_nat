# Import some POX stuff
from pox.core import core                       # Main POX object
import pox.openflow.libopenflow_01 as of        # OpenFlow 1.0 library
from pox.lib.addresses import EthAddr, IPAddr   # Address types
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet import ipv4, arp
from structs import NATTable, FLOW_OUT, FLOW_IN
from arp_utils import create_arp_reply, send_arp_reply, create_arp_request


log = core.getLogger()
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def log_color(color, msg):
    log.info(f"{color}{msg}{RESET}")


PRIVATE_SUBNET = IPAddr("192.168.1.0")      # Red interna
PRIVATE_MASK = 24                           # Máscara de la red interna
PRIVATE_IP = IPAddr("192.168.1.254")        # IP del router en la red privada
PUBLIC_IP = IPAddr("200.0.0.254")           # IP del router en la red pública
PUBLIC_MAC = EthAddr("00:00:00:aa:aa:aa")   # MAC del router hacia la red pública
PRIVATE_MAC = EthAddr("00:00:00:bb:bb:bb")  # MAC del router hacia la red privada
PUBLIC_PORT = 1                             # Puerto del switch conectado a la red pública
FLOW_IDLE_TIMEOUT = 10                      # Segundos sin trafico hasta que el switch borra un flujo


class ProtoRouter(object):
    def __init__(self, connection):
        self.connection = connection
        connection.addListeners(self)

        self.arp_table = {}     # Se registra {IP: MAC}
        self.pending_packets = {}   # Guarda los paquetes, para los que se desconocia la MAC destino (Se genero un ARP request)
        self.nat_table = NATTable(PUBLIC_IP)

    # Punto de entrada del paquete, solamente si el hard, NO ENCONTRO UNA REGLA
        # Por lo cual, para una conexion activa, solo deberias de ver el primer paquete. (U otro, si vence la regla)
        # Tanto entrada a la red local, como salida.
    def _handle_PacketIn(self, event):
        if not event.parsed.parsed:
            log.warning("[DROP] PacketIn con trama no reconocida. POX no pudo decodificar el paquete.")
            return

        if event.parsed.type == ethernet.IP_TYPE:
            self.handle_ip(event)
        elif event.parsed.type == ethernet.ARP_TYPE:
            self.handle_arp(event)
        else:
            log_color(YELLOW, f"Paquete ignorado: protocolo distinto de IPv4 o ARP.")

    def handle_ip(self, event):
        packet = event.parsed
        ip_pkt = packet.payload
        in_port = event.port

        ip_packet = packet.find('ipv4')
        if ip_packet is None:
            return

        # Ahora para debug. Se necesita, porque puede haber conexiones en el mismo.
        if ip_packet.protocol == ipv4.TCP_PROTOCOL:
            log_color(GREEN, "TCP")
        elif ip_packet.protocol == ipv4.UDP_PROTOCOL:
            log_color(GREEN, "UDP")
        else:
            log_color(GREEN, "OTROooo")

        log_color(
            YELLOW, f"RECIBIDO: {ip_pkt.srcip} → {ip_pkt.dstip} | "
            f"MAC: {packet.src} → {packet.dst} | In Port: {in_port}")

        # Desde la red privada
        if ip_pkt.srcip.inNetwork(PRIVATE_SUBNET, PRIVATE_MASK):

            log_color(GREEN, f"MATCH: {ip_pkt.srcip} pertenece a la red privada {PRIVATE_SUBNET}/{PRIVATE_MASK}")

            mac_dst = self.resolve_arp(ip_pkt.dstip, PUBLIC_PORT, PUBLIC_MAC, PUBLIC_IP, event)
            # Si la MAC, no se conoce, debemos enviar la ARP Request
                # Y almacenar el paquete para el envio posterior
            if mac_dst is None:
                log_color(
                    RED, f"RECIBIDO: {ip_pkt.srcip} → {ip_pkt.dstip} | "
                    f"No se conoce MAC destino. Se envio un ARP Request")
                # No se conoce, no podemos seguir con el flujo
                # A la espera de la respuesta de ARP.
                return

            transport = packet.find('tcp') or packet.find('udp')
            if transport is None:
                log_color(YELLOW, "Protocolo no soportado para NAT por puertos (Solo UDP/TCP)")
                return 

            #Consulta/crea la traducción en la tabla NAT
            conn = self.nat_table.translate_outbound(
                protocol = ip_pkt.protocol,
                src_ip = ip_pkt.srcip,
                src_port = transport.srcport,
                dst_ip = ip_pkt.dstip,
                dst_port = transport.dstport
            )

            # Instalar los dos flujos de la conexion en el switch
            fm = self.install_outbound_flow(conn, in_port, mac_dst)
            self.install_inbound_flow(conn, packet.src, in_port)
            self.nat_table.flows_installed(conn) # La conexion tiene los dos flujos instalados en el switch

            # Enviar el primer paquete actual por el puerto público (aplicándole las mismas acciones de traducción)
            msg = of.ofp_packet_out()
            msg.data = packet.pack()
            msg.in_port = in_port
            msg.actions = fm.actions
            self.connection.send(msg)

            log_color(
                CYAN, f"NAT OUT: {ip_pkt.srcip}:{transport.srcport} → {PUBLIC_IP}:{conn.nat_port} | "
                f"DST: {ip_pkt.dstip}:{transport.dstport} | MAC: {PUBLIC_MAC} → {mac_dst} | Out Port: {PUBLIC_PORT}")

        else:   # Desde la red pública (Paquete entrante sin flujo instalado)
            # Al ser un NAT saliente, si un paquete entra desde la red pública y no matcheó con ninguna regla
            # entrante activa en el switch, es tráfico externo no solicitado y se descarta.
            log_color(RED, f"DROP: Tráfico entrante no solicitado desde {ip_pkt.srcip} hacia {ip_pkt.dstip}")

    # Crea un flow_mod con el idle timeout y el aviso de vencimiento
    def new_flow_mod(self):
        fm = of.ofp_flow_mod()
        fm.idle_timeout = FLOW_IDLE_TIMEOUT
        fm.flags |= of.OFPFF_SEND_FLOW_REM  # Flag que hace que el switch avise cuando el flujo vence
        return fm

    # Instala el flujo saliente: host privado:puerto -> servidor:puerto
    # Devuelve el flow_mod, para reutilizar las acciones en el packet_out del primer paquete.
    def install_outbound_flow(self, conn, in_port, server_mac):
        fm = self.new_flow_mod()

        # Filtro (Saliente)
        fm.match.in_port = in_port
        fm.match.dl_type = 0x800 #Ipv4
        fm.match.nw_proto = conn.protocol
        fm.match.nw_src = conn.src_ip
        fm.match.nw_dst = conn.dst_ip
        fm.match.tp_src = conn.src_port
        fm.match.tp_dst = conn.dst_port

        # Acción (Saliente)
        # Reescribe Macs (Origen: Mac publica del router, destino: Mac del servidor publico)
        # Traduce ip origen privada a public_ip del router
        # Puerto origen privado a nat_port asignado en la tabla
        fm.actions.append(of.ofp_action_dl_addr.set_src(PUBLIC_MAC))
        fm.actions.append(of.ofp_action_dl_addr.set_dst(server_mac))
        fm.actions.append(of.ofp_action_nw_addr.set_src(PUBLIC_IP))
        fm.actions.append(of.ofp_action_tp_port.set_src(conn.nat_port))
        fm.actions.append(of.ofp_action_output(port=PUBLIC_PORT))
        self.connection.send(fm)

        return fm

    # Instala el flujo entrante (respuestas): servidor:puerto -> IP pública:nat_port
    def install_inbound_flow(self, conn, host_mac, host_port):
        fm_back = self.new_flow_mod()

        # Filtro (Entrante)
        fm_back.match.in_port = PUBLIC_PORT
        fm_back.match.dl_type = 0x800  # IPv4
        fm_back.match.nw_proto = conn.protocol
        fm_back.match.nw_src = conn.dst_ip
        fm_back.match.nw_dst = PUBLIC_IP
        fm_back.match.tp_src = conn.dst_port
        fm_back.match.tp_dst = conn.nat_port

        # Acción (Entrante)
        fm_back.actions.append(of.ofp_action_dl_addr.set_src(PRIVATE_MAC))
        fm_back.actions.append(of.ofp_action_dl_addr.set_dst(host_mac))
        fm_back.actions.append(of.ofp_action_nw_addr.set_dst(conn.src_ip))
        fm_back.actions.append(of.ofp_action_tp_port.set_dst(conn.src_port))
        fm_back.actions.append(of.ofp_action_output(port=host_port))
        self.connection.send(fm_back)

    # El switch avisa que un flujo fue removido (idle timeout vencido)
    # Cuando a una conexion no le queda ni flujo saliente ni entrante, se libera la entrada de la tabla NAT
    def _handle_FlowRemoved(self, event):
        match = event.ofp.match

        # Solo importan los flujos de TCP/udp 
        if match.nw_proto not in (ipv4.TCP_PROTOCOL, ipv4.UDP_PROTOCOL):
            return

        if match.in_port == PUBLIC_PORT: # Flujo entrante servidor:puerto -> ippublica:nat_port
            direction = FLOW_IN
            conn = self.nat_table.get_inbound(
                match.nw_proto, match.tp_dst, match.nw_src, match.tp_src)
        else: # flujo saliente: host privado:puerto -> servidor:puerto
            direction = FLOW_OUT
            conn = self.nat_table.get_outbound(
                match.nw_proto, match.nw_src, match.tp_src, match.nw_dst, match.tp_dst)

        if conn is None:
            return

        released = self.nat_table.flow_expired(conn, direction)

        if released:
            log_color(
                CYAN, f"NAT LIBERADO: {conn.src_ip}:{conn.src_port} - {PUBLIC_IP}:{conn.nat_port} | "
                f"DST: {conn.dst_ip}:{conn.dst_port} | Puerto público {conn.nat_port} disponible")
        else:
            log_color(
                YELLOW, f"Flujo {direction} vencido: {conn.src_ip}:{conn.src_port} - {PUBLIC_IP}:{conn.nat_port} | "
                f"La conexion sigue activa por el otro flujo")

    def handle_arp(self, event):
        # Obtiene el payload del paquete Ethernet
        arp_pkt = event.parsed.find('arp')

        print("Es una REQUEST? ", arp_pkt.opcode == arp.REQUEST)
        print("MAC origen:", arp_pkt.hwsrc)
        print("MAC destino:", arp_pkt.hwdst)
        print("IP origen:", arp_pkt.protosrc)
        print("IP destino:", arp_pkt.protodst)

        # Aprender IP -> MAC
        self.arp_table[arp_pkt.protosrc] = arp_pkt.hwsrc
            # {IP origen: MAC origen}
 
        # Debemos manejarlo diferente, dependiendo de si es una Request o Reply
        if arp_pkt.opcode == arp.REQUEST:

            # Solo responde a requests de IPs del router
            if arp_pkt.protodst == PRIVATE_IP:
                arp_reply = create_arp_reply(
                    PRIVATE_MAC, PRIVATE_IP,
                    arp_pkt.hwsrc, arp_pkt.protosrc
                )
            elif arp_pkt.protodst == PUBLIC_IP:
                arp_reply = create_arp_reply(
                    PUBLIC_MAC, PUBLIC_IP,
                    arp_pkt.hwsrc, arp_pkt.protosrc
                )
            else: # si se consulta por otro host
                log_color(YELLOW, f"ARP Request ignorada: {arp_pkt.protodst} no es una IP del router.")
                return

            send_arp_reply(self.connection, event.port, arp_reply)

        # Si recibe una Reply, es de alguna Request que genero.
            # Asi que busca los paquetes pendientes y los envia.
        if arp_pkt.opcode == arp.REPLY:
            pending = self.pending_packets.pop(arp_pkt.protosrc, [])
            for item in pending:
                print("eberia enviar", item)
                self.handle_ip(item["event"])
            return
 
        # Solo se responden los ARP dirigidos a las IPs del router
        pass


    def resolve_arp(self, target_ip, out_port, router_mac, router_ip, event):
        # Si ya conocemos la MAC, la devolvemos.
        if target_ip in self.arp_table:
            return self.arp_table[target_ip]

        # Debemos guardar el paquete y generar la ARP request
        if target_ip not in self.pending_packets:
            self.pending_packets[target_ip] = []

            # Enviar ARP Request solamente si todavía no hay una consulta pendiente.
            msg = create_arp_request(
                target_ip, out_port, router_mac, router_ip
            )
            log_color(YELLOW, f"ARP Request enviado: quien tiene {target_ip}? (por el puerto {out_port})")
            self.connection.send(msg)

        # Agregar el Event (que incluye el paquete) a la lista de pendientes.
            # Ya que mientras se espera respuesta, podria llegar otro paquete, que no sabemos como resolver.
        self.pending_packets[target_ip].append({"event": event})

        return None 

def launch():

    def start_switch(event):
        log_color(YELLOW, f"Iniciando ProtoRouter para Switch {event.connection.dpid}")
        ProtoRouter(event.connection)

    core.openflow.addListenerByName("ConnectionUp", start_switch)
