# Funciones auxiliares para construir y enviar paquetes ARP desde el controlador.
import pox.openflow.libopenflow_01 as of        # OpenFlow 1.0 library
from pox.lib.addresses import EthAddr, IPAddr   # Address types
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet import arp


def create_arp_reply(src_mac, src_ip, dst_mac, dst_ip):
    packet = arp()
    packet.opcode = arp.REPLY

    packet.hwsrc = EthAddr(src_mac)
    packet.protosrc = IPAddr(src_ip)

    packet.hwdst = EthAddr(dst_mac)
    packet.protodst = IPAddr(dst_ip)

    return packet


# Encapsula el ARP Reply en Ethernet y lo envía por el puerto del switch indicado.
def send_arp_reply(connection, out_port, arp_reply):
    eth_packet = ethernet()
    eth_packet.type = ethernet.ARP_TYPE

    eth_packet.src = arp_reply.hwsrc
    eth_packet.dst = arp_reply.hwdst
    eth_packet.payload = arp_reply

    msg = of.ofp_packet_out()
    msg.data = eth_packet.pack()
    msg.actions.append(of.ofp_action_output(port=out_port))

    connection.send(msg)


def create_arp_request(
    target_ip,   # IP del dispositivo cuya MAC queremos averiguar.
    out_port,    # Puerto OpenFlow por el que enviaremos el ARP Request.
    router_mac,  # MAC de la interfaz del router conectada a esa red.
    router_ip    # IP de esa misma interfaz del router.
):

    # Crear paquete ARP.
    arp_req = arp()
    arp_req.hwtype = arp.HW_TYPE_ETHERNET
    arp_req.prototype = arp.PROTO_TYPE_IP
    arp_req.hwlen = 6
    arp_req.protolen = 4
    arp_req.opcode = arp.REQUEST

    # Datos de la interfaz del router desde la que se consulta.
    arp_req.hwsrc = router_mac
    arp_req.protosrc = router_ip

    # MAC destino desconocida.
    arp_req.hwdst = EthAddr("00:00:00:00:00:00")
    arp_req.protodst = target_ip

    # Encapsular en Ethernet.
    eth = ethernet()
    eth.type = ethernet.ARP_TYPE
    eth.src = router_mac
    eth.dst = EthAddr("ff:ff:ff:ff:ff:ff")
    eth.payload = arp_req

    # Enviar broadcast por la interfaz correspondiente.
    msg = of.ofp_packet_out()
    msg.data = eth.pack()
    msg.actions.append(of.ofp_action_output(port=out_port))

    return msg
