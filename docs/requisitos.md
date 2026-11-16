Crie um chatbot (simplificado) onde a aplicação do chatbot deve permitir que vários usuários se conectem a aplicação e cada usuário faça perguntas genéricas para o chatbot de forma que  a aplicação reponderá a cada pergunta de cada usuário. Obs: você pode fazer o controle de cada sessão de usuário por um id único gerado no instante que o cliente http se conectar a aplicação servidora. Você pode usar qualquer modelo LLM a sua escolha e qualquer API de desenvolvimento.

#### Funcionalidades Principais:

1. **Conexão Multiusuário**: Permitir que vários usuários interajam com o chatbot simultaneamente.
2. **Gestão de Sessões**:
   - Identificar cada usuário através de um ID único gerado no momento da conexão.
   - Manter o histórico de conversa isolado para cada sessão.
3. **Processamento de Perguntas**:
   - Responder perguntas genéricas usando um modelo LLM de sua escolha.
   - Garantir que cada resposta seja direcionada ao usuário correto.

#### Implementação:

- Livre escolha de modelo LLM (OpenAI GPT, Google Gemini ou outros Modelos Open Weight/Open Source).
- Livre escolha de framework/API (LangChain, OpenAI SDK, Google Generative AI, etc.) ou Vanilla Python (Python "puro").
- Desenvolvimento do backend com qualquer stack de tecnologia (Python/Node.js/Java/etc.).

#### Publicação e Infraestrutura:

- **Implantação em AWS EC2**: A aplicação pode ser hospedada em uma instância EC2 (opcional, mas se implementada a equipe ganha 1,0 pontos extra).
- **Acesso Público**: Disponibilizar endpoint público da aplicação acessível via internet.
- **Documentação**: Incluir instruções de uso do endpoint (API) da aplicação backend.

### Critérios de Avaliação

- A apresentação do protótipo da aplicação deverá ser feita presencialmente em sala de aula (11/novembro). 
- Funcionamento correto do chatbot multiusuário.
- Gestão adequada das sessões por ID único.
- Qualidade e coerência das respostas do LLM.
- Implantação funcional na AWS EC2 (opcional).
- Acessibilidade pública da aplicação.
- Organização e clareza do código.
- Cada equipe terá 30 minutos para apresentar seu trabalho.

### Observações Importantes:

- O controle de sessão por ID único é fundamental para diferenciar os usuários.
- A aplicação deve ser capaz de lidar com conexões concorrentes.
- A escolha do modelo LLM e framework é livre, mas deve ser justificada tecnicamente.
- O código-fonte do protótipo deverá ser publicado em um repositório do Github.