# server.py
import socket
import threading

HOST = "127.0.0.1"
PORT = 12345

HEADER_LEN = 4
MAX_MSG = 1 << 20  # 1 MB

salas: dict[str, set[socket.socket]] = {
    "#geral": set(),
    "#jogos": set(),
}
clientes: dict[socket.socket, dict] = {}
lock_salas = threading.Lock()

def send_msg(sock: socket.socket, data: bytes) -> None:
    size = len(data).to_bytes(HEADER_LEN, "big")
    sock.sendall(size + data)

def enviar(sock: socket.socket, texto: str):
    try:
        send_msg(sock, texto.encode("utf-8"))
    except Exception:
        pass  # conexão pode já estar fechada

def recv_exactly(sock: socket.socket, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)

def recv_msg(sock: socket.socket) -> bytes | None:
    header = recv_exactly(sock, HEADER_LEN)
    if header is None:
        return None
    size = int.from_bytes(header, "big")
    if size < 0 or size > MAX_MSG:
        return None
    payload = recv_exactly(sock, size)
    return payload

def broadcast(nome_sala: str, mensagem: str, excluir: socket.socket | None = None):
    """Envia a 'mensagem' para todos da sala 'nome_sala', exceto 'excluir'."""
    with lock_salas:
        destinatarios = list(salas.get(nome_sala, set()))
    for s in destinatarios:
        if excluir is not None and s is excluir:
            continue
        enviar(s, mensagem)

def mover_para_sala(sock: socket.socket, nova_sala: str):
    """Remove o cliente da sala atual (se houver) e adiciona na nova_sala."""
    with lock_salas:
        info = clientes.get(sock)
        if not info:
            return
        sala_atual = info.get("sala")
        if sala_atual and sala_atual in salas and sock in salas[sala_atual]:
            salas[sala_atual].remove(sock)

        if nova_sala not in salas:
            salas[nova_sala] = set()

        salas[nova_sala].add(sock)
        info["sala"] = nova_sala

    enviar(sock, f"[SYS] Você entrou em {nova_sala}.")
    broadcast(nova_sala, f"[SYS] {info['nome']} entrou na sala.", excluir=sock)

def listar_salas() -> str:
    with lock_salas:
        linhas = [f"{nome} ({len(membros)} conectado(s))" for nome, membros in salas.items()]
        return "\n".join(linhas) if linhas else "(sem salas)"

class ClientThread(threading.Thread):
    def __init__(self, client_socket: socket.socket, client_address):
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.client_address = client_address

    def run(self):
        sock = self.client_socket
        addr = self.client_address
        info = None

        try:
            enviar(sock, "[SYS] Conectado ao servidor. Informe seu nome de usuário:")
            nome_bytes = recv_msg(sock)
            if not nome_bytes:
                enviar(sock, "[SYS] Nome inválido. Encerrando.")
                sock.close()
                return

            nome = nome_bytes.decode("utf-8", errors="ignore").strip()
            if not nome:
                enviar(sock, "[SYS] Nome inválido. Encerrando.")
                sock.close()
                return

            with lock_salas:
                clientes[sock] = {"nome": nome, "sala": None}
                info = clientes[sock]

            enviar(sock, f"[SYS] Bem-vindo, {nome}! Use /join <sala>, /list, /quit. Padrão: #geral")
            mover_para_sala(sock, "#geral")

            while True:
                data = recv_msg(sock)
                if data is None:
                    break
                msg = data.decode("utf-8", errors="ignore").strip()
                if not msg:
                    continue

                if msg.startswith("/"):
                    partes = msg.split(maxsplit=1)
                    cmd = partes[0].lower()

                    if cmd == "/join":
                        if len(partes) == 1:
                            enviar(sock, "[SYS] Uso: /join <nome_da_sala>")
                            continue
                        destino = partes[1].strip()
                        if not destino.startswith("#"):
                            destino = "#" + destino
                        old_info = clientes.get(sock, {})
                        antiga = old_info.get("sala")

                        mover_para_sala(sock, destino)
                        if antiga and antiga != destino:
                            broadcast(antiga, f"[SYS] {old_info['nome']} saiu da sala.")

                    elif cmd == "/list":
                        enviar(sock, "[SYS] Salas disponíveis:\n" + listar_salas())

                    elif cmd == "/quit":
                        enviar(sock, "[SYS] Desconectando...")
                        break

                    else:
                        enviar(sock, "[SYS] Comando não reconhecido. Use /join, /list, /quit.")
                    continue

                info = clientes.get(sock)
                if not info or not info.get("sala"):
                    enviar(sock, "[SYS] Você não está em nenhuma sala. Use /join <sala>.")
                    continue

                sala = info["sala"]
                nome = info["nome"]
                broadcast(sala, f"[{sala}] {nome}: {msg}", excluir=None)

        except (ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            with lock_salas:
                info = clientes.pop(sock, None)
                if info:
                    sala = info.get("sala")
                    if sala in salas and sock in salas[sala]:
                        salas[sala].remove(sock)
                # remove salas vazias (exceto padrões)
                for sala_nome in list(salas.keys()):
                    if sala_nome not in ("#geral", "#jogos") and len(salas[sala_nome]) == 0:
                        salas.pop(sala_nome, None)

            if info and info.get("sala"):
                broadcast(info["sala"], f"[SYS] {info['nome']} desconectou.", excluir=sock)

            try:
                sock.close()
            except Exception:
                pass
            print(f"[CONEXÃO ENCERRADA] {addr} desconectou.")

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Opcional: reutilizar porta rapidamente em desenvolvimento
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[ESCUTANDO] Servidor em {HOST}:{PORT}")

    try:
        while True:
            client_socket, client_address = server_socket.accept()
            print(f"[NOVA CONEXÃO] {client_address} conectado.")
            ClientThread(client_socket, client_address).start()
    except KeyboardInterrupt:
        print("\n[SYS] Encerrando servidor...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()
