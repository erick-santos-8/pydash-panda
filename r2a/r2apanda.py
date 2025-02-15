from r2a.ir2a import IR2A
from player.parser import *
from time import perf_counter, sleep
from statistics import harmonic_mean, stdev

from base.whiteboard import Whiteboard

import math
import matplotlib.pyplot as plt

class R2APanda(IR2A):
    def __init__(self, id):
        IR2A.__init__(self, id)
        self.alpha = 0.2
        self.w = 0.3
        self.k = 0.14
        self.beta = 0.2
        self.xtn_m1 = 0 
        self.xcn_m1 = 0 
        self.ycn = 0 # Versão filtrada do throughput
        self.ycn_m1 = 0
        self.tamanho_utlimo_buffer = 0
        self.lista_segmentos = []
        self.taxa_transferencias = []
        self.taxa_transferencias_estimadas = []
        self.tempo_ultima_solicitacao = 0
        self.tempo_ultima_solicitação_global = 0
        self.tempo_proxima_solicitacao = 0
        self.xcn = 0        

        self.whiteboard = Whiteboard.get_instance()

    
    def handle_xml_request(self, msg):
        """ Sends the XML request to the ConnectionHandler. """

        self.tempo_ultima_solicitacao = perf_counter() 
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # Taxa de transferência calculada
        self.xtn_m1 = msg.get_bit_length() / (perf_counter() - self.tempo_ultima_solicitacao)

        # Estimativa de taxa de transferência
        self.xcn_m1 = self.xtn_m1

        # Atualizando as listas de taxas
        self.taxa_transferencias.append(self.xtn_m1)
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
        self.tempo_ultima_solicitação_global = self.tempo_ultima_solicitacao
        self.tempo_ultima_solicitacao = solicitação_de_tempo_atual

        # Estimativa  
        self.xcn = (self.k * (self.w - (self.xcn_m1 - self.xtn_m1 + self.w))) * intervalo_tempo_solicitacao_atual + self.xcn_m1

        #Suavização
        if self.ycn_m1 == 0:
            self.ycn_m1 = self.xcn

        #EWMA adaptado
        self.ycn = self.alpha * self.xcn + (1 - self.alpha) * self.ycn_m1
        
        #EWMA formula original
        #self.ycn = ((self.alpha - 1) * self.tempo_ultima_solicitação_global * (self.ycn_m1 - self.xcn)) + self.ycn_m1

        self.taxa_transferencias_estimadas.append(self.ycn)
        self.ycn_m1 = self.ycn
        
        #Quantização
        lista_selecionada = min(self.lista_segmentos, key=lambda seg: abs(seg - self.ycn), default=0)
    
        msg.add_quality_id(lista_selecionada)

        #Agendamento
        buffer_minimo = 26
        self.tempo_proxima_solicitacao = ((lista_selecionada * msg.get_segment_size())/self.ycn) + (self.beta * (self.tamanho_utlimo_buffer - buffer_minimo))
        self.tamanho_utlimo_buffer = self.whiteboard.get_amount_video_to_play() #Atualiza o estado do buffer com a qualidade de video restante para a reprodução.

        self.send_down(msg)
        
    def handle_segment_size_response(self, msg):
        self.xtn_m1 = msg.get_bit_length() / (perf_counter() - self.tempo_ultima_solicitacao)
        self.taxa_transferencias.append(self.xtn_m1)

        self.grafico_filas()
        self.grafico_taxas_transferencia()
        self.grafico_instabilidade()
        self.grafico_desvio_padrao_transferencias()
        self.grafico_distribuicao_taxas()

        self.send_up(msg)
        pass

    def initialize(self):
        pass

    def finalization(self):
        pass 

    def grafico_filas(self):
        dados = self.whiteboard.get_playback_qi() 
        tempos, taxas = zip(*dados) if dados else ([], [])

        plt.figure(figsize=(10, 5))
        plt.plot(tempos, taxas, marker='o', color='blue')
        plt.title("Video ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Qualidade do video")
        plt.grid(True)
        plt.savefig("grafico_fila_tempo.png")
    

    def grafico_taxas_transferencia(self):
        tempos = [i for i in range(len(self.taxa_transferencias))]
        plt.figure(figsize=(10, 5))
        plt.plot(tempos, self.taxa_transferencias, marker='o', label="Taxa de Transferência Real")
        plt.plot(tempos, self.taxa_transferencias_estimadas, marker='x', label="Taxa de Transferência Estimada")
        plt.title("Taxas de Transferência ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Taxa de Transferência (bits/s)")
        plt.legend()
        plt.grid(True)
        plt.savefig("grafico_taxas_transferencia_tempo.png")
        
    def calcular_instabilidade(self):
        k = 20  # Número de amostras 
        instabilidade = []
        
        if len(self.taxa_transferencias) < k:
            return instabilidade

        for t in range(k, len(self.taxa_transferencias)):
            numerador = sum(abs(self.taxa_transferencias[t-d] - self.taxa_transferencias[t-d-1]) * (k - d) for d in range(k))
            denominador = sum(self.taxa_transferencias[t-d] * (k - d) for d in range(k))
            
            if denominador != 0:
                instabilidade.append(numerador / denominador)
            else:
                instabilidade.append(0)  # Evita a divisão por zero

        return instabilidade

    def grafico_instabilidade(self):
        instabilidade = self.calcular_instabilidade()
        tempos = [i for i in range(len(instabilidade))]

        plt.figure(figsize=(10, 5))
        plt.plot(tempos, instabilidade, marker='o', color='green', label="Instabilidade")
        plt.title("Instabilidade ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Instabilidade")
        plt.legend()
        plt.grid(True)
        plt.savefig("grafico_instabilidade_tempo.png")
        
    
    def grafico_desvio_padrao_transferencias(self):
        if len(self.taxa_transferencias) < 2:
            return
        
        desvios = [stdev(self.taxa_transferencias[:i+1]) for i in range(1, len(self.taxa_transferencias))]
        tempos = range(1, len(desvios) + 1)
        
        plt.figure(figsize=(10, 5))
        plt.plot(tempos, desvios, marker='o', color='purple', label="Desvio Padrão das Taxas")
        plt.title("Desvio Padrão das Taxas de Transferência")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Desvio Padrão")
        plt.legend()
        plt.grid(True)
        plt.savefig("grafico_desvio_padrao.png")
    
    def grafico_distribuicao_taxas(self):
        plt.figure(figsize=(10, 5))
        plt.hist(self.taxa_transferencias, bins=20, color='blue', edgecolor='black', alpha=0.7)
        plt.title("Distribuição das Taxas de Transferência")
        plt.xlabel("Taxa de Transferência (bits/s)")
        plt.ylabel("Frequência")
        plt.grid(True)
        plt.savefig("grafico_distribuicao_taxas.png")
