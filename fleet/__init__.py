"""Servidor de frota — painel central de gerenciamento dos equipamentos de cubagem.

Recebe heartbeats dos equipamentos (versão, unidade, status, produção, erros), guarda o histórico
e distribui as atualizações (versão-alvo + pacotes). Roda num servidor central (não no Pi).
"""
