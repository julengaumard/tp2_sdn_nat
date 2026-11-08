Al quitar los `ARP` harcodeados de `topo.py`

1. Primero observo que para el `h1 ping h2` envian un `ARP request` a la `IP` del __default gateway__, no del destino.

    Construyo un `ARP reply`, para notificarle la MAC del router (sea la de la interfaz __publica__ o __privada__ (segun corresponda))

2. Falta resolver el `ARP`, para los `dispositivos` (Sigue hardcodeado)

    Todo lo relaciondo con `H1_MAC`.