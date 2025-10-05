# 📧 Sistema de Chat Concorrente com Salas

Este projeto implementa um sistema de chat distribuído em Python, utilizando Sockets para a comunicação em rede e Threads para gerenciar múltiplos clientes simultaneamente. O sistema suporta a criação dinâmica de salas de chat e utiliza threading.Lock para garantir a sincronização e evitar condições de corrida no acesso a recursos compartilhados.

- **Servidor Multithread:** Capaz de gerenciar múltiplas conexões de clientes de forma concorrente.

- **Salas de Chat Dinâmicas:** Crie ou entre em salas de chat existentes usando um comando simples.

- **Isolamento de Mensagens:** Mensagens enviadas em uma sala são visíveis apenas para os participantes daquela sala.

- **Comandos Intuitivos:** Interface baseada em comandos simples para interagir com o sistema.

- **Sincronização Segura:** Uso de Lock para garantir que as operações em recursos compartilhados (como a lista de salas e clientes) sejam atômicas e seguras.

- **Enquadramento de Mensagens (Message Framing):** O sistema implementa um protocolo próprio sobre TCP para garantir que cada mensagem seja transmitida de forma completa e isolada. Cada mensagem é prefixada com 4 bytes que representam seu tamanho, evitando problemas de fragmentação (quando uma mensagem chega cortada) ou coalescência (quando várias chegam “coladas” em uma só leitura). Isso torna a comunicação muito mais confiável e fácil de depurar.

## Tecnologias Utilizadas
### Python (3.11)

**Sockets:** Para a comunicação de baixo nível via TCP/IP.

**Threads:** Para o gerenciamento de concorrência.

**threading.Lock:** Para sincronização e prevenção de condições de corrida.

## 📂 Estrutura do Projeto  
📂 projeto-chat/  
 ├── 📜 server.py      # Lógica do servidor central que gerencia salas e clientes  
 ├── 📜 cliente.py     # Aplicação cliente para conectar e interagir com o servidor  
 └── 📄 README.md      # Esta documentação  

# Guia de Instalação e Execução  

### Pré-requisitos

- Python 3.8 ou superior instalado.  
- Um terminal ou prompt de comando.  
- Os arquivos server.py e cliente.py devem estar na mesma pasta.  

## Passo 1: Iniciar o Servidor

1. Abra um terminal.
2. Navegue até o diretório onde os arquivos do projeto estão localizados.
3. Execute o seguinte comando para iniciar o servidor:
```Bash
python3 server.py
```

O terminal exibirá uma mensagem indicando que o servidor está pronto para receber conexões:  
*[ESCUTANDO] Servidor em 127.0.0.1:12345*


## Passo 2: Conectar Clientes

1. Abra um novo terminal para cada cliente que deseja conectar.
2. Navegue até o mesmo diretório do projeto.
3. Execute o comando abaixo:
```Bash
python3 cliente.py
```
4. O programa solicitará que você digite um nome de usuário. Após digitar, pressione Enter.  
5. Repita este passo em quantos terminais desejar para simular múltiplos usuários.

## Passo 3: Utilizar o Chat

Após conectar, você entrará automaticamente na sala padrão #geral. Você pode interagir com o chat através dos seguintes comandos:

## 🚀 Uso via Navegador (Interface Web)

Além do cliente de terminal (`cliente.py`), o sistema também possui uma interface web (`index.html`) que pode ser acessada diretamente pelo navegador.

### Passo 1: Iniciar o Servidor TCP

python3 server.py

Passo 2: Iniciar a Ponte WebSocket

python3 ponte.py --ws-host 0.0.0.0 --ws-port 8765
Passo 3: Abrir o Chat no Navegador

Abra o arquivo index.html no navegador.

Informe:

URL do WebSocket (ex: ws://localhost:8765)

Apelido (ex: ana)

Sala (ex: geral)

Clique em Conectar e use o chat diretamente no browser.


| **Comando**      | **Descrição**                                                                   | **Exemplo de Uso** |
| ---------------- | ------------------------------------------------------------------------------- | ------------------ |
| `/help`          | Exibe todos os comandos disponíveis e instruções básicas de uso.                | `/help`            |
| `/nick <nome>`   | Define ou altera o seu apelido (nickname) visível aos outros usuários.          | `/nick Matheus`    |
| `/create <sala>` | Cria uma nova sala de chat (caso ainda não exista).                             | `/create #geral`   |
| `/join <sala>`   | Entra em uma sala existente ou cria e entra automaticamente se ela não existir. | `/join #jogos`     |
| `/rooms`         | Lista todas as salas ativas e o número de participantes em cada uma.            | `/rooms`           |
| `/leave`         | Sai da sala atual (sem desconectar do servidor).                                | `/leave`           |
| `/who`           | Mostra a lista de membros conectados na sala atual.                             | `/who`             |
| `/quit`          | Encerra a conexão com o servidor de chat.                                       | `/quit`            |
| `<mensagem>`     | Envia uma mensagem para todos os usuários da sala atual.                        | Olá, pessoal! 👋   |


## Passo 4: Encerrar a Execução

- **Para desconectar um cliente:** Digite /quit ou sair no terminal do cliente.
- **Para desligar o servidor:** Vá para o terminal onde o server.py está rodando e pressione Ctrl + C.

# 📈 Exemplo de Fluxo de Uso
Veja um exemplo de interação entre três clientes (Alice, Bob e Carol).

### Terminal do Servidor:

*[ESCUTANDO] Servidor em 127.0.0.1:12345*  
*[NOVA CONEXÃO] ('127.0.0.1', 54321) conectado.*  
*[NOVA CONEXÃO] ('127.0.0.1', 54322) conectado.*  
*[NOVA CONEXÃO] ('127.0.0.1', 54323) conectado.*  

### Terminal do Cliente A (Alice):

*[OK] Conectado a 127.0.0.1:12345*  
*Informe seu nome de usuário:* Alice  
*Você:* /join #geral  
*[SYS] Você entrou em #geral.*
*Você:* Olá a todos!  

### Terminal do Cliente B (Bob):

*[OK] Conectado a 127.0.0.1:12345*  
*Informe seu nome de usuário:* Bob  
*Você:* /join #geral  
*[SYS] Você entrou em #geral.*  
*[#geral] Alice: Olá a todos!*  

### Terminal do Cliente C (Carol):

*[OK] Conectado a 127.0.0.1:12345*  
*Informe seu nome de usuário:* Carol  
*Você:* /join #jogos  
*[SYS] Você entrou em #jogos.*  
*Você:* Alguém para jogar?  
**Neste ponto, a mensagem da Carol só é visível para quem está na sala #jogos. Alice e Bob não a recebem.**

<details>
 <summary><h2>🔮 Possíveis Melhorias Futuras</h2></summary>
 [  ] Mensagens Privadas: Implementar um comando /msg <usuário> <mensagem> para conversas diretas.  
  
 [  ] Persistência de Dados: Salvar o histórico de mensagens em um banco de dados (como SQLite ou PostgreSQL).
 
 [  ] Autenticação de Usuários: Adicionar um sistema de registro e login com senhas.
 
 [  ] Criptografia: Implementar criptografia (como SSL/TLS) para proteger as mensagens.
 
 [  ] Interface Gráfica: Desenvolver uma interface gráfica (GUI) com bibliotecas como Tkinter, PyQt ou Kivy.
 </details>
