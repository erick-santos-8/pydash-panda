from r2a.ir2a import IR2A
from player.parser import *
from time import perf_counter, sleep
from statistics import harmonic_mean

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
        #self.ycn = ((self.alpha - 1) * self.tempo_ultima_solicitação_global * (self.ycn_m1 - xcn)) + self.ycn_m1
        self.taxa_transferencias_estimadas.append(self.ycn)
        self.ycn_m1 = self.ycn
        print('suavização: fffffffffffffffffffff', self.ycn)
        
        #Quantização
        lista_selecionada = min(self.lista_segmentos, key=lambda seg: abs(seg - self.ycn), default=0)
    
        msg.add_quality_id(lista_selecionada)

        print("quantização: sssssssssssssssssssss", lista_selecionada)

        #Agendamento
        buffer_minimo = 15
        self.tempo_proxima_solicitacao = ((lista_selecionada * msg.get_segment_size())/self.ycn) + (self.beta * (self.tamanho_utlimo_buffer - buffer_minimo))

        self.tamanho_utlimo_buffer = self.whiteboard.get_amount_video_to_play() #Atualiza o estado do buffer com a qualidade de video restante para a reprodução.

        print("agendamento: bbbbbbbbbbbbbbbbbbbbbbbbbbbb", self.tempo_proxima_solicitacao)

        self.send_down(msg)

        

    def handle_segment_size_response(self, msg):
        self.xtn_m1 = msg.get_bit_length() / (perf_counter() - self.tempo_ultima_solicitacao)
        self.taxa_transferencias.append(self.xtn_m1)
        
        # Cálculo do Jain's Fairness Index
        jain_fairness = self.calcular_jains_fairness_index(self.taxa_transferencias)
        # Cálculo da Unfairness
        unfairness = self.calcular_unfairness(jain_fairness)
        
        print("----------------------------------------------------------")
        print("Tamanho buffers playbacks", self.whiteboard.get_playback_buffer_size())
        print("Tamanho Segmento no buffer", self.whiteboard.get_playback_segment_size_time_at_buffer())
        print("Buffer maximo", self.whiteboard.get_max_buffer_size())
        print("----------------------------------------------------------")
        print("----------------------------------------------------------")

        self.plot_filas()
        self.plot_tamanho_buffers()
        self.plot_taxas_transferencia()

        # Plota a instabilidade
        self.plot_instabilidade()
        
        self.plot_ineficiencia()
        
        self.plot_unfairness(unfairness)
        
        self.plot_ineficiencia_instabilidade()


        self.send_up(msg)
        pass

    def initialize(self):
        pass

    def finalization(self):
        pass 

    def plot_filas(self):
        dados = self.whiteboard.get_playback_qi()  # Exemplo: [(tempo1, taxa1), (tempo2, taxa2)]
        print("KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK", dados)
        tempos, taxas = zip(*dados) if dados else ([], [])

        plt.figure(figsize=(10, 5))
        plt.plot(tempos, taxas, marker='o', color='blue')
        plt.title("Video ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Qualidade do video")
        plt.grid(True)
        plt.savefig("grafico_fila_tempo.png")
    
    def plot_tamanho_buffers(self):
        dados_buffer = self.whiteboard.get_playback_buffer_size()
        tempos_buffer, tamanhos_buffer = zip(*dados_buffer) if dados_buffer else ([], [])

        plt.figure(figsize=(10, 5))
        plt.plot(tempos_buffer, tamanhos_buffer, marker='x', color='red', label="Tamanho do buffer")
        plt.title("Tamanho do Buffer ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Tamanho do Buffer")
        plt.grid(True)
        plt.savefig("grafico_buffer_tempo.png")

    def plot_taxas_transferencia(self):
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
        k = 20  # Número de amostras (segundos)
        instabilidade = []

        # Verifique se há pelo menos 'k' amostras
        if len(self.taxa_transferencias) < k:
            return instabilidade

        for t in range(k, len(self.taxa_transferencias)):
            numerador = sum(abs(self.taxa_transferencias[t-d] - self.taxa_transferencias[t-d-1]) * (k - d) for d in range(k))
            denominador = sum(self.taxa_transferencias[t-d] * (k - d) for d in range(k))
            
            if denominador != 0:
                instabilidade.append(numerador / denominador)
            else:
                instabilidade.append(0)  # Evitar divisão por zero

        return instabilidade

    def plot_instabilidade(self):
        instabilidade = self.calcular_instabilidade()
        
        # Plotar a instabilidade ao longo do tempo
        tempos = [i for i in range(len(instabilidade))]

        plt.figure(figsize=(10, 5))
        plt.plot(tempos, instabilidade, marker='o', color='green', label="Instabilidade")
        plt.title("Instabilidade ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Instabilidade")
        plt.legend()
        plt.grid(True)
        plt.savefig("grafico_instabilidade_tempo.png")
        
    def calcular_ineficiencia(self):
        C = sum(self.taxa_transferencias_estimadas)  # Soma das taxas estimadas, por exemplo
        soma_taxas = sum(self.taxa_transferencias)
        print("CCCCCCCCCC: ", C)
        print("TAXAAAAA: ", soma_taxas)
        print((soma_taxas - C) / C)

        if C > 0:
            ineficiencia = max(0, (soma_taxas - C) / C)
        else:
            ineficiencia = 0
        
        return ineficiencia

    def plot_ineficiencia(self):
        ineficiencia = self.calcular_ineficiencia()
        
        # Plotar a ineficiência ao longo do tempo
        tempos = [i for i in range(len(self.taxa_transferencias))]

        plt.figure(figsize=(10, 5))
        plt.plot(tempos, [ineficiencia] * len(tempos), marker='x', color='red', label="Ineficiência")
        plt.title("Ineficiência ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Ineficiência")
        plt.legend()
        plt.grid(True)
        plt.savefig("grafico_ineficiencia_tempo.png")
        
    def calcular_jains_fairness_index(self, rates):
        n = len(rates)
        soma_taxas = sum(rates)
        soma_quadrados_taxas = sum([r**2 for r in rates])
        
        jain_fairness = (soma_taxas**2) / (n * soma_quadrados_taxas)
        return jain_fairness
        
    def calcular_unfairness(self, jain_fairness):
        # Calculando a Unfairness
        unfairness = math.sqrt(1 - jain_fairness)
        return unfairness

    def plot_unfairness(self, unfairness):
        tempos = [i for i in range(len(self.taxa_transferencias))]
        
        plt.figure(figsize=(10, 5))
        plt.plot(tempos, [unfairness] * len(tempos), marker='x', color='purple', label="Unfairness")
        plt.title("Unfairness ao Longo do Tempo")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Unfairness")
        plt.legend()
        plt.grid(True)
        plt.savefig("grafico_unfairness_tempo.png")

    def plot_ineficiencia_instabilidade(self):
        # Calcular a ineficiência a cada tempo
        ineficiencia = [self.calcular_ineficiencia()] * len(self.taxa_transferencias)
        
        # Calcular a instabilidade
        instabilidade = self.calcular_instabilidade()
        
        # Ajuste para que o número de pontos das duas listas seja igual
        # Caso a instabilidade tenha menos pontos, estenda o último valor para o número de pontos de ineficiência
        instabilidade_anterior = 0
        if len(instabilidade) > 2 :
            instabilidade_anterior = instabilidade[-1]
            
        if len(instabilidade) < len(ineficiencia):
            instabilidade = instabilidade + [instabilidade_anterior] * (len(ineficiencia) - len(instabilidade))

        # Plotando a relação entre ineficiência e instabilidade
        plt.figure(figsize=(10, 5))
        plt.plot(ineficiencia, instabilidade, marker='o', color='orange', label="Relação Ineficiência vs Instabilidade")
        plt.title("Relação entre Ineficiência e Instabilidade")
        plt.xlabel("Ineficiência")
        plt.ylabel("Instabilidade")
        plt.legend()
        plt.grid(True)
        plt.savefig("grafico_ineficiencia_instabilidade.png")
