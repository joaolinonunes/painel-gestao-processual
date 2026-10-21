# Painel de Apoio à Gestão Processual

Projeto desenvolvido no âmbito do **Projeto Integrador IV (UNIVESP)**.

## Objetivo

Auxiliar gestores e servidores judiciais a identificar, de forma visual e intuitiva, onde se concentram os atrasos na tramitação de processos judiciais, destacando os processos com maior tempo de tramitação e as classes processuais que demandam mais tempo.

A solução utiliza dados públicos da **API Pública do DataJud (CNJ)** e aplica técnicas de aprendizado de máquina não supervisionado (**K-Means**) para segmentar os processos em grupos conforme sua celeridade (ex.: rápidos, médios e lentos), apresentando os resultados em um painel interativo construído com **Streamlit**.

## Estrutura do Repositório

```text
painel-gestao-processual/
├── data/
│   ├── raw/            # Retorno bruto coletado da API do DataJud
│   └── processed/      # Arquivos tratados e dados agrupados
├── src/                # Scripts de coleta, tratamento e modelagem
├── notebooks/          # Análises exploratórias e gráficos para relatório
├── docs/               # Registros e documentação de validação com especialistas
├── .gitignore          # Arquivos e pastas ignorados pelo controle de versão
├── requirements.txt    # Dependências do projeto
└── README.md           # Visão geral do projeto
```
