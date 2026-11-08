# Import some POX stuff
from pox.core import core                       # Main POX object
import pox.openflow.libopenflow_01 as of        # OpenFlow 1.0 library
from pox.lib.addresses import EthAddr, IPAddr   # Address types
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet import ipv4, arp

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

H1_MAC = EthAddr("00:00:00:00:00:01")       # MAC del host externo (TODO: resolver mediante ARP)

# TODO: moverlos a un archivo de methods.py
def is_private(ip):
    mask = (0xFFFFFFFF << (32 - PRIVATE_MASK)) & 0xFFFFFFFF
    return (ip.toUnsigned() & mask) == PRIVATE_SUBNET.toUnsigned()

def create_arp_reply(src_mac, src_ip, dst_mac, dst_ip):
    packet = arp()
    packet.opcode = arp.REPLY

    packet.hwsrc = EthAddr(src_mac)
    packet.protosrc = IPAddr(src_ip)

    packet.hwdst = EthAddr(dst_mac)
    packet.protodst = IPAddr(dst_ip)

    return packet

def send_arp_reply(self, event, arp_reply):
    eth_packet = ethernet()
    eth_packet.type = ethernet.ARP_TYPE

    eth_packet.src = arp_reply.hwsrc
    eth_packet.dst = arp_reply.hwdst
    eth_packet.payload = arp_reply

    msg = of.ofp_packet_out()
    msg.data = eth_packet.pack()
    msg.actions.append(of.ofp_action_output(port=event.port))

    self.connection.send(msg)

class ProtoRouter(object):
    def __init__(self, connection):
        self.connection = connection
        connection.addListeners(self)

        self.arp_table = {}     # Se registra {IP: MAC}

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

        # # Ethernet
        # eth = packet.find('ethernet')
        # src_mac = eth.src
        # dst_mac = eth.dst

        # # IPv4
        # ip = packet.find('ipv4')
        # src_ip = ip.srcip
        # dst_ip = ip.dstip
        # protocol = ip.protocol

        # # TCP / UDP
        # transport = packet.find('tcp') or packet.find('udp')

        # if transport:
        #     src_port = transport.srcport
        #     dst_port = transport.dstport

        log_color(
            YELLOW, f"RECIBIDO: {ip_pkt.srcip} → {ip_pkt.dstip} | "
            f"MAC: {packet.src} → {packet.dst} | In Port: {in_port}")

        # Desde la red privada
        if ip_pkt.srcip.inNetwork(PRIVATE_SUBNET, PRIVATE_MASK):

            log_color(GREEN, f"MATCH: {ip_pkt.srcip} pertenece a la red privada {PRIVATE_SUBNET}/{PRIVATE_MASK}")

            # Instalar Flujo Saliente
            fm = of.ofp_flow_mod()
            fm.idle_timeout = 10

            # Filtro (Saliente)
            fm.match.nw_src = ip_pkt.srcip
            fm.match.dl_type = 0x800  # IPv4
            fm.match.in_port = in_port

            # Acción (Saliente)
            fm.actions.append(of.ofp_action_dl_addr.set_src(PUBLIC_MAC))
            fm.actions.append(of.ofp_action_dl_addr.set_dst(H1_MAC))
            fm.actions.append(of.ofp_action_output(port=PUBLIC_PORT))
            self.connection.send(fm)

            # Instalar Flujo Entrante (para respuesta)
            fm_back = of.ofp_flow_mod()
            fm_back.idle_timeout = 10

            # Filtro (Entrante)
            fm_back.match.nw_src = ip_pkt.dstip
            fm_back.match.nw_dst = ip_pkt.srcip
            fm_back.match.dl_type = 0x800  # IPv4
            fm_back.match.in_port = PUBLIC_PORT

            # Acción (Entrante)
            fm_back.actions.append(of.ofp_action_dl_addr.set_src(PRIVATE_MAC))
            fm_back.actions.append(of.ofp_action_dl_addr.set_dst(packet.src))
            fm_back.actions.append(of.ofp_action_output(port=in_port))
            self.connection.send(fm_back)

            # Reenviar paquete actual con MACs actualizadas (Los posteriores pasan por flujo)
            packet.src = PUBLIC_MAC
            packet.dst = H1_MAC
            msg = of.ofp_packet_out()
            msg.data = packet.pack()
            msg.actions.append(of.ofp_action_output(port=PUBLIC_PORT))
            log_color(CYAN, f"ENVIANDO: {ip_pkt.srcip} → {ip_pkt.dstip} | MAC: {PUBLIC_MAC} → {H1_MAC} | Out Port: {PUBLIC_PORT}")
            self.connection.send(msg)

        else:   # Desde la red publica (Paquete entrante.)
            log_color(RED, f"NO MATCH: {ip_pkt.srcip} no pertenece a {PRIVATE_SUBNET}/{PRIVATE_MASK}")

    def handle_arp(self, event):
        # Obtiene el payload del paquete Ethernet
        arp_pkt = event.parsed.find('arp')

        print("Es un evento ARP, type: ", arp_pkt.opcode)
        print("MAC origen:", arp_pkt.hwsrc)
        print("MAC destino:", arp_pkt.hwdst)
        print("IP origen:", arp_pkt.protosrc)
        print("IP destino:", arp_pkt.protodst)

        # Aprender IP -> MAC
        self.arp_table[arp_pkt.protosrc] = arp_pkt.hwsrc
            # {IP origen: MAC origen}
 
        # Debemos manejarlo diferente, dependiendo de si es una Request o Reply
        if arp_pkt.opcode == arp.REQUEST:
            
            if is_private(arp_pkt.protodst):
                arp_reply = create_arp_reply(
                    PRIVATE_MAC, PRIVATE_IP,
                    arp_pkt.hwsrc, arp_pkt.protosrc
                )
                 
            else:
                arp_reply = create_arp_reply(
                    PUBLIC_MAC, PUBLIC_IP,
                    arp_pkt.hwsrc, arp_pkt.protosrc
                )

            send_arp_reply(self, event, arp_reply)
 
        # TODO:
            # Ahora solo responde para si mismo, porque no hay otro host local, para pasar un mensaje de ARP
            # Preguntar si agregamos eso o con esto ya esta.

        # DUDA:
            # Hay que permitir que resuelva de fuera? 
            # O hay que bloquearlo?

        # Idea general (si hubiese mas host locales)
            # 1. Obtener paquete ARP.
            # 2. Aprender IP -> MAC del emisor.
            # 3. Si es Request dirigido a una IP del router:
            #       Generar ARP Reply.
            # 4. Si es Reply:
            #       Resolver paquetes pendientes.
        pass

    # Solo si hay mas host locales
    def resolve_arp(self, target_ip, out_port):
        # 1. Consultar tabla ARP.
        # 2. Si existe, devolver MAC.
        # 3. Si no existe:
        #       Guardar paquete pendiente.
        #       Generar ARP Request.
        pass

def launch():

    def start_switch(event):
        log_color(YELLOW, f"Iniciando ProtoRouter para Switch {event.connection.dpid}")
        ProtoRouter(event.connection)

    core.openflow.addListenerByName("ConnectionUp", start_switch)
