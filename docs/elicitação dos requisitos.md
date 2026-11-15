# Elicitação dos requisitos — Chatbot multiusuário

## 1. Objetivo e escopo

Desenvolver um protótipo de chatbot que responda perguntas genéricas usando um modelo de linguagem (LLM), atendendo simultaneamente dezenas de usuários. Cada conversa deve ter histórico próprio e persistente, acessível após o fechamento do navegador e após o desligamento ou reinício do servidor, durante o período de retenção de 1 hora (ver seção 9).

Este documento formaliza os requisitos discutidos a partir de `requisitos.md`. Pontos ainda não definidos são identificados como decisões em aberto; critérios quantitativos propostos não são metas aprovadas.

## 2. Conceito de sessão

Neste projeto, **sessão é uma conversa persistente**, identificada por um ID único. Não se trata de sessão de autenticação: não há login ou identidade verificada no escopo atual, conforme orientação do professor.

Cada cliente tem **uma única conversa**. O servidor gera o ID quando o cliente se conecta pela primeira vez e o entrega em um cookie de sessão; o navegador o devolve automaticamente nas requisições seguintes, e o servidor o usa para localizar a conversa. O servidor guarda o histórico em banco de dados persistente. Ao retornar, o usuário continua a conversa de onde parou, sem copiar ou informar o ID manualmente.

O ID é a chave de acesso à conversa: quem o conhecer ou possuir o cookie poderá acessar seu histórico. Ele deve ser imprevisível e protegido em trânsito por HTTPS. Se os cookies forem apagados ou o usuário trocar de navegador ou dispositivo, o cliente deixa de apresentar o ID e uma nova conversa será iniciada; a conversa anterior fica inacessível e é removida pela política de retenção. Não haverá mecanismo de recuperação (ver seção 9).

### Decisões tomadas

1. **Interface: a própria API HTTP, usada pelo Swagger/OpenAPI.**
   - *Decisão:* não haverá front-end nesta etapa; `curl` e Postman são alternativas opcionais. Um front-end poderá ser feito depois.
   - *Motivo:* o professor dispensou o front-end, e o Swagger dá ao avaliador uma forma de testar a API pelo navegador, sem escrever código, o que atende o RF08.
2. **Identificação do cliente por cookie de sessão (aprovada).**
   - *Decisão:* o servidor gera o ID na primeira requisição e o entrega em cookie; o navegador o devolve automaticamente.
   - *Motivo:* o IP não distingue usuários atrás do mesmo NAT (como a rede da UFPI) e muda com a rede; o `localStorage` exigiria um front-end ou a cópia manual do ID a cada chamada; o cookie é enviado sozinho pelo navegador, inclusive pelo Swagger, e corresponde ao enunciado, que fala em ID gerado no instante em que o cliente HTTP se conecta.
3. **Uma conversa por cliente.**
   - *Decisão:* não há operação para criar várias conversas nem para alternar entre elas. O ID não aparece nas URLs. Abas do mesmo navegador compartilham a conversa; navegadores diferentes, janelas anônimas e outros dispositivos têm conversas distintas.
   - *Motivo:* o enunciado fala em "cada usuário" com "um id único" e não pede várias conversas por pessoa. Isso simplifica a API (sem listar nem escolher conversas), evita expor IDs na URL e reduz o risco de vazamento.
4. **Atributos do cookie: `HttpOnly`, `Secure`, `SameSite=Lax` e validade de 1 hora, renovada a cada requisição.**
   - *Motivo:* o ID dá acesso ao histórico. `HttpOnly` impede que um script da página o leia (XSS); `Secure` o mantém só em HTTPS, como exigem os requisitos de segurança; `SameSite=Lax` reduz o risco de requisições forjadas de outros sites; a validade de 1 hora acompanha o período de retenção das conversas (seção 9), pois um cookie que durasse mais apontaria para uma conversa já removida.
5. **Geração do ID pelo servidor, com gerador criptográfico (por exemplo, UUID v4).**
   - *Motivo:* o ID é o único segredo de acesso, então precisa ser imprevisível. IDs sequenciais poderiam ser adivinhados, e um ID escolhido pelo cliente permitiria colisões ou o sequestro de conversas.
6. **Clientes sem navegador mantêm os cookies entre chamadas.**
   - *Decisão:* `curl` e scripts usam um arquivo de cookies (por exemplo, `curl -c cookies.txt -b cookies.txt`); testes de carga usam um conjunto de cookies por usuário simulado.
   - *Motivo:* sem isso, cada chamada seria vista como um cliente novo, e todas as requisições de um teste de carga criariam conversas diferentes ou se misturariam numa só.
7. **Cookie ausente ou com ID inexistente: o servidor cria uma nova conversa.**
   - *Decisão:* nos dois casos, o servidor gera um novo ID, cria a conversa vazia e envia o novo cookie. A conversa anterior, se existir, fica inacessível a esse cliente e é removida ao fim do período de retenção (1 hora sem atividade).
   - *Motivo:* sem login, não há como recuperar a conversa antiga nem confirmar quem é o cliente, e o usuário perde o cookie ao limpá-los ou trocar de navegador. Criar uma nova conversa deixa a API sempre utilizável, sem exigir que o usuário trate um erro, e trata o ID inexistente (por exemplo, após limpar o banco) do mesmo jeito que o cookie ausente. Contrapartida: o usuário perde o acesso à conversa anterior, o que é consistente com a decisão de não haver recuperação (seção 9).

```mermaid
flowchart TD
    S[Sessão = conversa persistente<br/>Não é autenticação] --> ID[ID único e imprevisível<br/>gerado pelo servidor]
    ID --> C[Cookie de sessão no cliente]
    ID --> B[Banco guarda o histórico completo]
    C --> R[Mesmo navegador retoma a conversa]
    B --> R
    B --> D[Histórico disponível após reinício do servidor]
    C -->|Cookies apagados ou outro navegador/dispositivo| P[Nova conversa<br/>Sem recuperação]
    ID -->|Quem possui o cookie| AC[Acessa o histórico]
```

## 3. Atores e visão geral

- **Usuário:** inicia ou retoma sua conversa e envia perguntas.
- **Desenvolvedor ou avaliador:** utiliza e verifica a API pública conforme sua documentação.
- **Modelo de linguagem:** processa a pergunta e o contexto fornecido pela aplicação.

```mermaid
flowchart LR
    U[Cliente da API<br/>Swagger no navegador] -->|Cookie de sessão e pergunta| A[API do chatbot]
    A --> B[(Banco de dados persistente)]
    A --> L[Modelo de linguagem]
    L --> A
    A -->|Resposta| U
```

## 4. Requisitos funcionais

| ID | Requisito | Critério de aceitação |
|---|---|---|
| RF01 | Criar uma conversa com ID único para cada novo cliente. | Na primeira requisição de um cliente sem cookie de sessão, ou com cookie cujo ID não exista no banco, o servidor gera o ID, cria o histórico próprio e entrega o ID em cookie. |
| RF02 | Reconhecer o cliente pelo cookie de sessão e associá-lo à sua única conversa. | Enquanto o cookie existir, requisições do mesmo cliente acessam a mesma conversa, inclusive após fechar o navegador e após reinício do servidor; o ID não precisa ser informado manualmente. |
| RF03 | Persistir o histórico completo no servidor. | Mensagens confirmadas como salvas continuam disponíveis após reinicialização da aplicação ou da máquina, enquanto a conversa estiver dentro do período de retenção. |
| RF04 | Permitir continuidade da conversa. | O usuário pode consultar o histórico completo e enviar novas perguntas à sua conversa. |
| RF05 | Responder perguntas genéricas usando um LLM. | Cada pergunta válida é encaminhada ao processamento e a resposta é devolvida à conversa correspondente, ou uma falha é comunicada. |
| RF06 | Atender múltiplos usuários concorrentemente. | Dezenas de usuários podem interagir sem mistura de históricos ou respostas; a capacidade exata será medida. |
| RF07 | Informar falhas ao usuário. | Falhas são comunicadas; o texto das mensagens e as ações de recuperação serão definidos. Cookie ausente ou com ID inexistente não é falha: gera nova conversa (RF01, decisão 7). |
| RF08 | Disponibilizar e documentar a API publicamente. | Um avaliador consegue acessar e utilizar o endpoint seguindo a documentação. |
| RF09 | Monitorar desempenho e recursos. | TTFT, tempo de resposta completa e recursos da máquina podem ser acompanhados, inclusive em tempo real. |
| RF10 | Bloquear perguntas simultâneas na mesma conversa. | Enquanto a resposta a uma pergunta está sendo gerada, nova pergunta da mesma conversa é recusada com HTTP 409 (Conflict) e mensagem clara, sem ser enfileirada nem processada. Perguntas de outras conversas não são afetadas. |
| RF11 | Remover conversas inativas. | Conversa sem atividade por mais de 1 hora tem histórico e ID removidos. Um cookie com esse ID passa a ser tratado como ID inexistente (RF01). |

## 5. Casos de uso

### UC01 — Iniciar conversa

**Ator:** usuário. **Fluxo:** o usuário faz a primeira requisição sem cookie de sessão; a aplicação cria a conversa, gera o ID e o entrega em cookie, que o navegador preserva. **Alternativa (decisão 7):** se a requisição chegar com cookie cujo ID não existe no banco, a aplicação trata como cliente novo: cria uma nova conversa, gera novo ID e substitui o cookie, sem retornar erro. **Resultado:** existe uma conversa própria disponível para receber perguntas.

```mermaid
sequenceDiagram
    actor U as Usuário
    participant C as Cliente
    participant A as Aplicação
    U->>C: Primeira requisição (sem cookie)
    C->>A: Requisição
    A-->>C: Resposta + Set-Cookie com ID único
    Note over C: Navegador preserva o cookie
```

### UC02 — Enviar pergunta e receber resposta

**Ator:** usuário. **Fluxo:** o usuário envia a pergunta; a aplicação identifica a conversa pelo cookie de sessão, recupera o contexto pertinente, consulta o LLM, associa e registra a resposta na conversa e a apresenta ao usuário. **Alternativa 1 (decisão 7):** se o cookie estiver ausente ou seu ID não existir no banco, a aplicação cria uma nova conversa (como no UC01), emite novo cookie e processa a pergunta nela, sem retornar erro; o contexto enviado ao modelo contém apenas essa pergunta. **Alternativa 2 (decisão de bloqueio, seção 9):** se já houver uma resposta em geração nesta conversa, a aplicação recusa a nova pergunta com HTTP 409 e mensagem clara, sem enfileirá-la; o usuário pode reenviar após a conclusão da resposta em andamento. **Alternativa 3:** em caso de falha do modelo ou outra falha, a aplicação informa o erro. O comportamento detalhado de recuperação permanece em aberto.

```mermaid
sequenceDiagram
    actor U as Usuário
    participant A as Aplicação
    participant B as Banco
    participant L as LLM
    U->>A: Pergunta + cookie de sessão
    A->>B: Localiza conversa pelo ID do cookie
    alt Cookie ausente ou ID inexistente
        A->>B: Cria nova conversa e novo ID
        A-->>U: Set-Cookie com novo ID
    end
    Note over A,U: Se já há resposta em geração nesta conversa:<br/>HTTP 409 e fim do fluxo
    A->>B: Recupera histórico pertinente
    B-->>A: Contexto
    A->>L: Pergunta + contexto
    alt Resposta gerada
        L-->>A: Resposta
        A->>B: Associa e registra resposta
        A-->>U: Apresenta resposta
    else Falha
        A-->>U: Informa erro
        Note over A,U: Recuperação detalhada em aberto
    end
```

### UC03 — Retomar conversa

**Ator:** usuário. **Pré-condição:** o cliente ainda possui o cookie de sessão e o histórico foi persistido. **Fluxo:** a aplicação lê o ID do cookie e recupera o histórico; o usuário consulta as mensagens e continua a conversa. O mesmo histórico deve continuar disponível após reinício do servidor. **Alternativa (decisão 7):** se o cookie estiver ausente ou seu ID não existir no banco, a aplicação cria uma nova conversa, emite novo cookie e apresenta o histórico vazio, sem retornar erro; a conversa anterior não é recuperada.

### UC04 — Interagir simultaneamente

**Atores:** vários usuários. **Fluxo:** usuários, cada um com seu cookie de sessão, enviam perguntas em suas respectivas conversas ao mesmo tempo. **Resultado:** cada resposta é associada à conversa e à requisição corretas, sem acesso a históricos de outras conversas.

```mermaid
flowchart LR
    A[Usuário A] -->|Cookie A + pergunta| API[API concorrente]
    B[Usuário B] -->|Cookie B + pergunta| API
    API --> HA[(Histórico A)]
    API --> HB[(Histórico B)]
    API -->|Resposta A| A
    API -->|Resposta B| B
```

### UC05 — Consultar a API

**Ator:** desenvolvedor ou avaliador. **Fluxo:** abre a documentação Swagger e utiliza o endpoint público. **Resultado:** consegue iniciar ou retomar sua conversa (por cookie) e enviar perguntas conforme as operações disponibilizadas.

## 6. Invariantes

1. Cada conversa tem um ID único e um histórico próprio, e cada cliente tem uma única conversa.
2. Uma conversa não pode acessar ou alterar o histórico de outra.
3. Uma resposta concluída pertence à pergunta e à conversa que a originaram.
4. Mensagens confirmadas como salvas permanecem disponíveis após reinício do servidor.
5. O histórico completo é preservado, mesmo quando apenas parte dele puder ser enviada ao modelo.
6. Falhas são comunicadas como falhas, sem serem apresentadas como respostas geradas pelo modelo.
7. O ID (e o cookie que o contém) é tratado como informação sensível, pois dá acesso ao histórico; não deve aparecer em URLs, logs públicos ou mensagens de erro. Credenciais do provedor do modelo também devem permanecer protegidas e fora do repositório público.
8. Cada conversa tem no máximo uma resposta em geração por vez.

## 7. Histórico e contexto do modelo

O histórico integral deve ser armazenado e ficar disponível para consulta. Já a quantidade de mensagens que pode ser enviada ao modelo em cada chamada depende de sua janela de contexto. Conversas longas podem exceder esse limite ou elevar custo e latência.

**Decisão:** a conversa continua de forma coerente combinando **mensagens recentes** com um **resumo das mensagens antigas**, preservando o histórico integral no banco. Motivo: o histórico completo pode exceder a janela de contexto do modelo ou elevar custo e latência; o resumo mantém o assunto da conversa sem reenviar tudo. Contrapartida: o resumo pode omitir detalhes das mensagens antigas no contexto do modelo (o histórico completo continua guardado). O bloqueio de perguntas simultâneas (seção 9) evita que dois processamentos atualizem o resumo ao mesmo tempo.

Os detalhes (10 mensagens recentes, atualização em lotes, mesmo modelo, resumo guardado na conversa) estão na seção 9, decisão 9.

```mermaid
flowchart LR
    H[(Histórico completo<br/>preservado e consultável)] --> S[Preparação do contexto]
    S --> R[Mensagens recentes + resumo das antigas<br/>pode omitir detalhes]
    R --> L[LLM]
    L --> A[Resposta coerente]
    A --> H
```

## 8. Qualidade, monitoramento e infraestrutura

- **Concorrência:** projetar e avaliar para algumas dezenas de usuários simultâneos (meta: 30, com teste de estresse até 50; ver metas abaixo).
- **Tempo até o primeiro token (TTFT):** medir o intervalo entre o envio da pergunta e o recebimento do primeiro token. A resposta é entregue progressivamente por SSE (seção 9, decisão 7).
- **Tempo total de resposta:** medir o intervalo entre o envio da pergunta e o recebimento do último token.
- **Recursos:** acompanhar CPU e RAM da máquina, inclusive em tempo real; acompanhar GPU e sua memória se utilizadas. Medir o consumo do próprio modelo quando ele executar na infraestrutura sob controle da equipe.
- **Erros e carga:** acompanhar falhas e requisições em andamento para relacionar desempenho à concorrência.
- **Modelo externo:** se uma API de terceiros executar o modelo, o consumo de recursos dessa execução pode não estar disponível; ainda assim, é possível medir recursos locais e latências percebidas.
- **Segurança e privacidade:** proteger o tráfego com HTTPS, guardar credenciais no servidor e considerar a exposição de conteúdo enviado ao provedor. O ID não comprova a identidade do usuário. O cookie de sessão segue os atributos da decisão 4 da seção 2.
- **Hospedagem:** AWS EC2 (decidido). Conforme o enunciado, sua utilização é opcional e concede pontuação extra; o endpoint público e as instruções de uso são exigidos.
- **Tecnologia:** Python com FastAPI e banco PostgreSQL (decididos; justificativas na seção 9). Modelo Gemini 3.1 Flash-Lite, pelo SDK oficial do Google (decisão 8; era o Gemini 2.5 Flash até 15/11/2026).

As metas abaixo foram **aprovadas** como critérios de aceitação do protótipo. O TTFT é medido com a resposta entregue por streaming SSE (decisão 7). **Não haverá teste de carga** (decisão 11): as metas de TTFT e tempo total foram verificadas apenas com um usuário (decisão 8, medições), e as metas com 30 e 50 usuários simultâneos não serão medidas.

| Métrica | Meta aprovada |
|---|---|
| Usuários simultâneos no teste de carga | 30 (com teste de estresse até 50) |
| TTFT | mediana ≤ 2 s; percentil 95 ≤ 5 s |
| Tempo total de resposta (resposta típica de cerca de 300 tokens) | percentil 95 ≤ 30 s |
| Taxa de erro durante o teste | ≤ 2%, sem contar recusas 409 intencionais |
| CPU da instância EC2 | média ≤ 70% |
| RAM da instância EC2 | ≤ 80% |

```mermaid
sequenceDiagram
    participant U as Cliente
    participant A as Aplicação / modelo
    U->>A: Envio da pergunta — início
    A-->>U: Primeiro token — fim do TTFT
    A-->>U: Tokens seguintes — streaming
    A-->>U: Último token — fim do tempo total
    Note over U,A: Monitorar CPU, RAM, erros e requisições em tempo real
    Note over U,A: GPU e memória de GPU quando utilizadas
```

## 9. Decisões e questões em aberto

### 9.1 Decisões tomadas

1. **Perguntas simultâneas na mesma conversa: bloquear.**
   - *Decisão:* enquanto a resposta a uma pergunta está sendo gerada, nova pergunta da mesma conversa é recusada com HTTP 409 (Conflict) e mensagem clara. Não há fila nem processamento em paralelo.
   - *Motivo:* mantém a ordem das mensagens previsível, evita respostas fora de ordem ou com contexto incompleto e impede atualizações concorrentes do resumo (seção 7). É também a opção mais simples de implementar.
   - *Consequências:* o bloqueio deve ser liberado ao fim da resposta e em caso de falha ou demora, para não travar a conversa. Com mais de um processo da aplicação, o controle deve ficar no banco (por exemplo, marcador de estado ou *advisory lock* do PostgreSQL), não em memória do processo.
2. **Contexto longo: mensagens recentes + resumo das antigas** (ver seção 7).
   - *Motivo:* mantém a coerência da conversa dentro da janela do modelo, com custo e latência controlados, e preserva o histórico completo no banco.
3. **Concorrência e metas de desempenho aprovadas (seção 8).**
   - *Decisão:* 30 usuários simultâneos no teste de carga (estresse até 50); TTFT com mediana ≤ 2 s e p95 ≤ 5 s; tempo total (resposta de cerca de 300 tokens) com p95 ≤ 30 s; taxa de erro ≤ 2%, sem contar os 409 intencionais; CPU média ≤ 70% e RAM ≤ 80% na instância EC2.
   - *Motivo:* o enunciado pede algumas dezenas de usuários simultâneos. Os valores são conservadores e dão critério objetivo para a demonstração, sem prometer desempenho que dependa do provedor do modelo.
   - *Situação:* o teste de carga foi cancelado (decisão 11). TTFT e tempo total foram verificados com um usuário e ficaram dentro das metas (decisão 8); a concorrência foi verificada funcionalmente (isolamento entre clientes e HTTP 409), mas não sob carga.
4. **Sem recuperação de conversa.**
   - *Decisão:* quem apagar os cookies ou trocar de navegador ou dispositivo perde o acesso à conversa e inicia outra (seção 2, decisão 7).
   - *Motivo:* não há login nem identidade verificada no escopo, e qualquer mecanismo de recuperação (código, e-mail, conta) ampliaria o escopo e a superfície de segurança.
5. **Retenção: 1 hora sem atividade, depois remoção.**
   - *Decisão:* conversa sem nenhuma requisição por 1 hora tem histórico e ID removidos por uma rotina de limpeza periódica. O cookie tem validade de 1 hora, renovada a cada requisição (seção 2, decisão 4).
   - *Motivo:* o protótipo não precisa guardar dados por longo prazo, o que reduz o acúmulo no banco e a exposição de dados pessoais. A remoção também resolve o acúmulo de conversas abandonadas gerado pela decisão de criar nova conversa quando o cookie falha.
   - *Interpretação confirmada:* "1 hora" significa 1 hora **sem atividade** (contada desde a última requisição), e não desde a criação da conversa, para evitar cortar uma conversa ativa no meio.
6. **Implantação e tecnologia: Python com FastAPI, PostgreSQL e AWS EC2.**
   - *Motivo (FastAPI):* gera a documentação OpenAPI/Swagger automaticamente, que é a interface escolhida (seção 2, decisão 1) e atende o RF08; suporta código assíncrono, adequado a muitas requisições que aguardam resposta do LLM, e streaming.
   - *Motivo (PostgreSQL):* banco relacional durável, que suporta várias conexões concorrentes e dá suporte a bloqueios no banco, necessários para a decisão 1.
   - *Motivo (EC2):* dá endpoint público e controle da máquina, permite acompanhar CPU e RAM (RF09) e vale ponto extra no enunciado.
7. **Streaming por SSE (Server-Sent Events).**
   - *Decisão:* o endpoint de pergunta responde com `text/event-stream`, enviando a resposta em partes à medida que o modelo a gera, seguida de um evento de fim (ou de erro). A recusa por bloqueio (HTTP 409) acontece antes de o stream começar.
   - *Motivo:* a meta de TTFT (p95 ≤ 5 s) só é atingível se o primeiro trecho chegar antes do fim da resposta, que pode levar até 30 s. O SSE é HTTP comum, suportado nativamente pelo FastAPI (`StreamingResponse`) e mais simples que WebSocket, já que a comunicação é só do servidor para o cliente.
   - *Consequência:* o Swagger não exibe a resposta chegando aos poucos; mostra o conteúdo completo ao fim. O TTFT é medido por um cliente que lê o stream (como os scripts de verificação usados nas medições da decisão 8).
8. **Modelo: Gemini 3.1 Flash-Lite (antes, Gemini 2.5 Flash), pelo SDK oficial do Google (`google-genai`).**
   - *Atualização (15/11/2026):* o modelo passou a ser o `gemini-3.1-flash-lite`. No deploy do EC2, a chave do servidor recebeu HTTP 404 do Google: o `gemini-2.5-flash` "não está mais disponível para novos usuários". Entre os modelos liberados para a chave, o 3.1 Flash-Lite é o de menor custo (US$ 0,25 por milhão de tokens de entrada e US$ 1,50 de saída, contra US$ 0,75 e US$ 3,75 do 3.8 Flash, sugerido pelo Google, cujo preço dobra em 2027) e o único Flash-Lite testado que aceita o raciocínio desligado (`thinking_budget=0`) sem mudança de código; o 3.5 Flash-Lite recusou a chamada com HTTP 400. Em troca, é o modelo mais simples da família. Os motivos e medições abaixo se referem à escolha original do 2.5 Flash.
   - *Decisão:* a aplicação usa exclusivamente o Gemini 2.5 Flash, executado como serviço pelo Google. A chave de API fica só no `.env` (local e do servidor), nunca no repositório. Um modelo simulado é mantido apenas para os testes automatizados, que rodam sem chave nem internet.
   - *Motivo (Gemini 2.5 Flash):*
     - **Executado como serviço:** o servidor da aplicação não precisa de GPU nem de memória para o modelo. A instância EC2 disponível (`t3.micro`, 908 MB de RAM) comporta a aplicação e o banco, mas não um modelo local.
     - **Linha "Flash", voltada a baixa latência:** compatível com as metas de TTFT e tempo total.
     - **Escala com vários usuários:** o processamento ocorre na infraestrutura do Google, e não numa CPU compartilhada; as metas com 30 usuários simultâneos tornam-se realistas.
     - **Qualidade das respostas**, critério de avaliação: superior à dos modelos pequenos avaliados localmente (ver histórico abaixo).
     - **Multilíngue, incluindo português**, idioma das perguntas e respostas.
     - **Raciocínio ajustável (*thinking budget*):** desligado por padrão (`LLM_ORCAMENTO_RACIOCINIO=0`), para o primeiro trecho chegar mais cedo.
     - **Citado no enunciado** como opção de modelo.
   - *Motivo (SDK `google-genai`):* SDK oficial, com chamadas assíncronas e streaming, integrado ao FastAPI; permite configurar a instrução de sistema e o orçamento de raciocínio de forma explícita. A conversão entre o formato de mensagens da aplicação e o do Gemini (papel `model`, instrução de sistema separada) fica isolada em `app/llm.py`.
   - *Detalhe técnico:* o cliente usa a versão `v1beta` da API, porque a instrução de sistema é recusada na `v1` (padrão do SDK 3.3.0).
   - *Medições (14/11/2026, um usuário, raciocínio desligado):* primeiro trecho entre **0,45 s e 0,94 s** e tempo total entre **0,6 s e 1,3 s**; zero tokens de raciocínio. Respostas corretas onde o Qwen 3 local errou (capital do Piauí: Teresina), memória de contexto e isolamento entre clientes corretos; bloqueio com HTTP 409 confirmado. Janela de entrada de 1.048.576 tokens.
   - *Consequências:* as conversas são processadas pelo Google. O plano gratuito permite só **5 requisições por minuto** para o `gemini-2.5-flash` (verificado em 14/11/2026: a 6ª chamada no mesmo minuto foi recusada com HTTP 429), o que levou à ativação do faturamento pré-pago (decisão 10). Cada pergunta consome uma requisição, e a atualização do resumo, outra.
   - *Histórico:* antes desta decisão, a equipe avaliou o **Qwen 3** (pesos abertos) executado localmente no **Ollama**, inclusive com o modelo rodando no notebook de quem apresentaria, ligado ao EC2 por túnel SSH reverso (prova de conceito aprovada em 14/11/2026). Foi substituído porque: os modelos que cabem em CPU (0.6B e 1.7B) erraram fatos simples (por exemplo, a capital do Piauí); a `t3.micro` não comporta o modelo; o arranjo com o notebook dependia de ele ficar ligado e conectado e não atenderia as metas com 30 usuários.
9. **Detalhes do resumo (seção 7).**
   - *Decisão:* as mensagens ainda não resumidas são enviadas inteiras ao modelo; quando houver 10 ou mais delas fora da janela das 10 mais recentes, o resumo é atualizado pelo mesmo modelo, depois que a resposta é entregue e antes da liberação do bloqueio. O resumo e a posição até onde ele cobre ficam guardados na própria conversa.
   - *Motivo:* atualizar em lotes evita uma chamada extra ao modelo a cada pergunta; gerar depois da resposta não aumenta o TTFT; fazer isso ainda sob o bloqueio impede que duas atualizações concorram.
10. **Faturamento da API do Gemini: crédito pré-pago de R$ 30, sem recarga automática.**
   - *Decisão:* o projeto do Google ligado à chave saiu do plano gratuito com a compra de R$ 30 em créditos pré-pagos (14/11/2026). A recarga automática fica **desligada**. Os créditos valem só para a API do Gemini, não são reembolsáveis e expiram em um ano.
   - *Motivo:* o limite gratuito (5 requisições por minuto) inviabilizava a demonstração com várias pessoas. No pré-pago, quando o crédito acaba a API para de responder, sem cobrança adicional: o gasto máximo é conhecido, mesmo com o endereço público aberto.
   - *Verificação:* 7 chamadas seguidas em 4,4 s, todas aceitas (antes, a 6ª falhava).
   - *Estimativa de custo atualizada (15/11/2026, `gemini-3.1-flash-lite`, decisão 8):* cerca de US$ 0,001 por pergunta, ou da ordem de 5 mil perguntas com o crédito, sem contar as chamadas de resumo. Estimativa grosseira, supondo 2 mil tokens de contexto e 300 de resposta por pergunta.
   - *Estimativa de custo original* (preços do `gemini-2.5-flash` no nível pago: US$ 0,30 por milhão de tokens de entrada e US$ 2,50 por milhão de saída): cerca de US$ 0,001 por pergunta numa conversa curta e US$ 0,004 no pior caso (histórico cheio). O crédito comporta com folga as duas apresentações previstas.
   - *Observação:* a assinatura de consumidor Google AI Plus não altera os limites da API, que dependem do projeto do Google Cloud.
11. **Sem teste de carga.**
   - *Decisão:* o teste de carga com 30 e 50 usuários simultâneos não será feito.
   - *Motivo:* com a API paga por uso, o teste consumiria créditos sem benefício para a demonstração; a equipe prioriza reservar o crédito para as apresentações.
   - *Consequência:* as metas com 30 e 50 usuários e a taxa de erro sob carga (seção 8) não serão medidas. Ficam como evidências as medições com um usuário (decisão 8) e os testes funcionais de concorrência (isolamento e HTTP 409).

```mermaid
flowchart TD
    Q[Nova pergunta na mesma conversa] --> G{Resposta anterior<br/>em geração?}
    G -->|Sim| R[HTTP 409<br/>pergunta recusada]
    G -->|Não| P[Processa a pergunta]
```

### 9.2 Em aberto

1. **Falhas:** definir mensagens e ações para entrada vazia, indisponibilidade ou demora do modelo e outros erros pertinentes, incluindo timeout, nova tentativa e liberação do bloqueio. Já decidido e fora desta questão: cookie ausente ou com ID inexistente cria nova conversa, sem erro (seção 2, decisão 7). A definição foi adiada por enquanto.
2. **Mensagem para crédito esgotado ou limite atingido (HTTP 429 do Gemini):** hoje o usuário recebe a mensagem genérica de falha. Uma mensagem específica deixaria claro, na demonstração, que o problema é cota e não defeito da aplicação.
3. **[Resolvida em 15/11/2026: troca para o `gemini-3.1-flash-lite`, decisão 8] Descontinuação do `gemini-2.5-flash`:** segundo a página de preços do Google (consultada em 14/11/2026, por resumo automático), a partir de 1º/12/2026 as chamadas a esse modelo serão redirecionadas ao Gemini 3.5 Flash-Lite. Não afeta a apresentação de 16/11; avaliar a troca de `LLM_MODELO` antes de uma segunda apresentação posterior a essa data.

## 10. Verificação e apresentação

Um cenário de demonstração é usar dois clientes distintos (por exemplo, dois navegadores ou uma janela anônima, já que o cookie é por navegador), informar um dado diferente em cada um e perguntar em seguida qual dado foi informado. Isso permite verificar continuidade de contexto e isolamento. Também devem ser demonstrados o retorno à conversa após recarregar a página ou fechar o navegador, a recuperação após reiniciar o servidor, o acesso público e o acompanhamento das métricas.

Conforme o enunciado, o código-fonte deve ser publicado em repositório GitHub. A apresentação do protótipo será presencial, em 11 de novembro, com 30 minutos por equipe; o ano não está especificado no arquivo de origem.
