from r2a.ir2a import IR2A
from player.parser import *
from time import perf_counter, sleep

class R2APANDA(IR2A):
    def __init__(self, id):
        IR2A.__init__(self, id)
        self.w = 0.3
        self.k = 0.14
        self.beta = 0.2
        self.tempo_ultima_solicitacao = 0
        self.xtn_m1 = 0 # ~x[n-1] - last TCP throughput measured
        self.xcn_m1 = 0 # ^x[n-1] - last target throughput
        self.tamanho_utlimo_buffer = 0
        self.lista_segmentos = []
        self.tempo_proxima_solicitacao = 0
        self.taxa_transferencias = []
        self.taxa_transferencias_estimadas = []

    
    def handle_xml_request(self, msg):
        """ Sends the XML request to the ConnectionHandler. """

        self.tempo_ultima_solicitacao = perf_counter() # used to calculate the first throughput
        self.send_down(msg)

    def handle_xml_response(self, msg):
        
        # Taxa de transferencia é calculada pelo tamanho do segmento do video pelo tempo decorrido desde a ultima solicitação 
        self.xtn_m1 = msg.get_bit_length() / (perf_counter() - self.tempo_ultima_solicitacao)

        # Ultiam estimativa de taxa de transferencia é igual a taxa de transferencia calculada
        self.xcn_m1 = self.xtn_m1

        # Adiciona a taxa de transferencia calculada à lista de taxas de transferencia calculadas
        self.taxa_transferencias.append(self.xtn_m1)

        # Adiciona a taxa de transferencia estimada à lista de taxas de transferencia estimadas
        self.taxa_transferencias_estimadas.append(self.xcn_m1)


        # Recebe a lista com as qualidades do video
        parsed_mpd = parse_mpd(msg.get_payload())

        # Adiciona a lista de qualidades do video à lista de listas de qualidades do video
        self.lista_segmentos = parsed_mpd.get_qi()


        # Proxima função  
        self.send_up(msg)

    
    def handle_segment_size_request(self, msg):

        # tempo decorrido desde a ultima solicitação
        tempo_de_espera = perf_counter() - self.tempo_ultima_solicitacao
        
        # Se o tempo decorrido desde a ultima solicitação for menor que o tempo de espera, espera o tempo de espera restante
        if tempo_de_espera < self.tempo_proxima_solicitacao:
            sleep(self.tempo_proxima_solicitacao - tempo_de_espera)

        solicitação_de_tempo_atual = perf_counter()
        intervalo_tempo_solicitacao_atual = solicitação_de_tempo_atual - self.tempo_ultima_solicitacao
        self.tempo_ultima_solicitacao = solicitação_de_tempo_atual

        # Estimativa  
        xcn = (self.k * (self.w - (self.xcn_m1 - self.xtn_m1 + self.w))) * intervalo_tempo_solicitacao_atual + self.xcn_m1
        print('estimativa aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa: ', xcn)

    def handle_segment_size_response(self, msg):
        pass

    def initialize(self):
        pass

    def finalization(self):
        pass 
