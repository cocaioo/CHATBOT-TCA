# Instância EC2: levantamento

> **Documento histórico.** Descreve a instância **antes** do deploy. O estado atual (nginx,
> PostgreSQL, serviço `chatbot` no systemd, swap, portas 80 e 443 abertas) está no
> README, seção 9. A equipe acabou não usando Docker nem Caddy: tudo roda direto na instância,
> com nginx.

Varredura **somente leitura** feita em **14/11/2026**, antes de qualquer deploy. Nada foi
instalado nem alterado na instância.

## Resumo

> A instância está **vazia** (Ubuntu recém-criado) e é pequena (`t3.micro`, 908 MB de RAM).
> Como o modelo é o **Gemini (hoje 3.1 Flash-Lite), executado pelo Google**, a instância só precisa rodar a
> aplicação e o banco, o que cabe nela. Antes do deploy é preciso **liberar as portas 80 e 443**.

| | Situação |
|---|---|
| ✅ Acesso SSH | Funcionando com `chatbot-key.pem` |
| ✅ Memória | 908 MB: suficiente para aplicação + PostgreSQL (o modelo roda no Google) |
| ✅ Disco | 4,4 GB livres: suficiente para aplicação + banco |
| ❌ Portas 80/443 | Bloqueadas no *security group* |
| ❌ Software da aplicação | Docker, PostgreSQL e Caddy não instalados |
| ❓ IP fixo (elástico) | Não verificável de dentro da instância; conferir no console da AWS |

## Ficha da instância

| Item | Valor |
|---|---|
| Tipo | `t3.micro` (nível gratuito) |
| Região / zona | Ohio, `us-east-2a` |
| IP público | `13.58.162.232` |
| Usuário SSH | `ubuntu` |
| CPU | 2 vCPU, Intel Xeon Platinum 8259CL @ 2,5 GHz |
| Memória | 908 MB (≈ 570 MB disponíveis), **sem swap** |
| Disco | 6,7 GB (2,3 GB usados, **4,4 GB livres**) |
| Sistema | Ubuntu 26.04.1 LTS, kernel 7.0 |

## Software

| Programa | Situação |
|---|---|
| Python | ✅ 3.14.4 (mesma versão usada no desenvolvimento) |
| pip | ✅ 25.1.1 |
| Git | ✅ 2.53 |
| Docker | ❌ não instalado |
| PostgreSQL | ❌ não instalado |
| Caddy / Nginx | ❌ não instalados |

Serviços rodando: apenas os padrões do sistema e o agente da AWS (SSM). A pasta do usuário
`ubuntu` está vazia: nenhum código foi enviado ainda.

## Rede

| Porta | Uso | Situação vista de fora |
|---|---|---|
| 22 | SSH | ✅ Liberada |
| 80 | HTTP (emissão do certificado HTTPS) | ❌ Bloqueada no *security group* |
| 443 | HTTPS (acesso público à API) | ❌ Bloqueada no *security group* |

Dentro da instância, só a porta 22 está escutando.

## Pontos de atenção para o deploy

### 1. Memória

A aplicação e o PostgreSQL usam juntos cerca de 300 a 500 MB, o que cabe nos ≈ 570 MB
disponíveis, mas com pouca folga. Um arquivo de swap pequeno (1 a 2 GB) evita que picos de
memória derrubem os processos.

### 2. Chave do Gemini

A aplicação no servidor precisa de acesso à internet (já existe) e da chave `GEMINI_API_KEY` no
`.env` **do servidor**, criado direto na instância. A chave nunca vai para o repositório.

### 3. Portas

Liberar **80 e 443** (origem `0.0.0.0/0`) no *security group*. A porta 80 é necessária para o
Let's Encrypt emitir o certificado HTTPS, sem o qual o cookie de sessão não funciona.

### 4. IP fixo

Confirmar no console da AWS que `13.58.162.232` é um **IP elástico**. Se não for, o IP muda quando
a instância reinicia, e o endereço público e o certificado deixam de valer.

## Checklist antes do deploy

- [ ] Liberar portas 80 e 443 no *security group*
- [ ] Confirmar que o IP é elástico
- [ ] Criar swap pequeno (1 a 2 GB)
- [ ] Instalar Docker na instância
- [ ] Criar o `.env` do servidor com `GEMINI_API_KEY` e uma senha forte para o banco

O plano proposto (Docker Compose com Caddy, aplicação e PostgreSQL) foi discutido pela equipe, mas
ainda não foi implementado.

## Histórico

Antes da adoção do Gemini, a equipe avaliou rodar o Qwen 3 no Ollama. A `t3.micro` não comporta
esse modelo, e por isso chegou a ser testado um túnel SSH reverso para usar o Ollama do notebook
de quem apresentaria (prova de conceito aprovada em 14/11/2026). A abordagem foi descartada com a
troca para o Gemini; o motivo está em `docs/elicitação dos requisitos.md`, seção 9, decisão 8.

## Como repetir a varredura

A partir da pasta `infra/` (funciona no Git Bash do Windows sem ajustar permissões da chave):

```bash
ssh -i chatbot-key.pem ubuntu@13.58.162.232 \
  'free -h; df -h /; nproc; . /etc/os-release; echo $PRETTY_NAME; ss -tln'
```

Tipo da instância (pelos metadados da AWS, de dentro dela):

```bash
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-type
```
