#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor de Chat Multithread com Salas + Message Framing (4 bytes)
Python 3.11
"""

from __future__ import annotations
import socket
import struct
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, Set

# =========================
# Utilitários de Framing
# =========================
# Protocolo: cada mensagem enviada é prefixada por 4 bytes (uint32 big-endian)
# que representam o tamanho exato do payload em bytes (UTF-8).

_MAX_FRAME = 8 * 1024 * 1024  # 8 MiB de limite defensivo

def send_frame(conn: socket.socket, text: str) -> None:
    data = text.encode("utf-8", errors="replace")
    n = len(data)
    if n > _MAX_FRAME:
        raise ValueError("Mensagem excede o tamanho máximo permitido.")
    header = struct.pack("!I", n)
    conn.sendall(header + data)

def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexão encerrada pelo par.")
        buf.extend(chunk)
    return bytes(buf)

def recv_frame(conn: socket.socket) -> Optional[str]:
    # Lê 4 bytes de tamanho; retorna None se conexão fechada graciosamente
    header = conn.recv(4)
    if not header:
        return None
    if len(header) < 4:
        # garante leitura do restante caso chegue fragmentado
        header += _recv_exact(conn, 4 - len(header))
    (length,) = struct.unpack("!I", header)
    if length > _MAX_FRAME:
        raise ValueError("Frame muito grande (possível protocolo inválido).")
    if length == 0:
        return ""
    data = _recv_exact(conn, length)
    return data.decode("utf-8", errors="replace")


# =========================
# Modelo de Cliente
# =========================
@dataclass(eq=False)
class Client:
    conn: socket.socket
    addr: tuple[str, int]
    nickname: str = field(default_factory=lambda: "anon")
    room: Optional[str] = None
    alive: bool = True

    def send(self, msg: str) -> None:
        try:
            send_frame(self.conn, msg)
        except Exception:
            # Erros de envio: marcar para cleanup
            self.alive = False


# =========================
# Servidor de Chat
# =========================
class ChatServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 5050):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

        # Estado compartilhado
        self.lock = threading.Lock()
        self.clients: Dict[socket.socket, Client] = {}
        self.rooms: Dict[str, Set[Client]] = {}  # room -> set(Client)

        # Para encerrar ordenadamente
        self._shutdown = threading.Event()

    # ---------------------
    # Gestão de Salas
    # ---------------------
    def create_room(self, name: str) -> bool:
        with self.lock:
            if name in self.rooms:
                return False
            self.rooms[name] = set()
            return True

    def join_room(self, client: Client, room: str) -> str:
        with self.lock:
            if room not in self.rooms:
                # criação dinâmica
                self.rooms[room] = set()
            # se já estiver em outra sala, sair
            if client.room and client in self.rooms.get(client.room, set()):
                self.rooms[client.room].discard(client)
                self._broadcast(client.room, f"* {client.nickname} saiu da sala.")
            # entrar na nova sala
            self.rooms[room].add(client)
            client.room = room
        self._broadcast(room, f"* {client.nickname} entrou na sala.")
        return room

    def leave_room(self, client: Client) -> None:
        with self.lock:
            if client.room and client in self.rooms.get(client.room, set()):
                room = client.room
                self.rooms[room].discard(client)
                client.room = None
                self._broadcast(room, f"* {client.nickname} saiu da sala.")

    def list_rooms(self) -> str:
        with self.lock:
            parts = []
            for r, members in self.rooms.items():
                parts.append(f"- {r} ({len(members)} online)")
            return "Salas:\n" + ("\n".join(parts) if parts else "(nenhuma)")

    # ---------------------
    # Broadcast
    # ---------------------
    def _broadcast(self, room: str, msg: str, *, sender: Optional[Client] = None) -> None:
        with self.lock:
            targets = list(self.rooms.get(room, set()))
        # enviar fora do lock para minimizar contenção; remover desconectados
        dead: list[Client] = []
        for c in targets:
            # não filtra o remetente; UX comum é o remetente também receber
            c.send(msg)
            if not c.alive:
                dead.append(c)
        if dead:
            with self.lock:
                for c in dead:
                    # limpeza silenciosa
                    self.rooms.get(room, set()).discard(c)
                    self.clients.pop(c.conn, None)

    # ---------------------
    # Loop principal
    # ---------------------
    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # reutilizar endereço rapidamente após reiniciar
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        print(f"Servidor escutando em {self.host}:{self.port}")

        try:
            while not self._shutdown.is_set():
                conn, addr = self.sock.accept()
                client = Client(conn=conn, addr=addr)
                with self.lock:
                    self.clients[conn] = client
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._shutdown.set()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        # finalizar clientes
        with self.lock:
            clients = list(self.clients.values())
        for c in clients:
            try:
                c.conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                c.conn.close()
            except Exception:
                pass

    # ---------------------
    # Tratamento por cliente
    # ---------------------
    def _handle_client(self, client: Client) -> None:
        # Mensagem de boas-vindas e ajuda inicial
        client.send(
            "Bem-vindo ao servidor de chat!\n"
            "Use /help para ver os comandos. Defina um apelido com /nick <nome>.\n"
        )
        try:
            while client.alive and not self._shutdown.is_set():
                msg = recv_frame(client.conn)
                if msg is None:
                    break  # cliente encerrou
                msg = msg.strip()
                if not msg:
                    continue
                if msg.startswith("/"):
                    self._handle_command(client, msg)
                else:
                    # mensagem normal vai para a sala atual
                    if not client.room:
                        client.send("! Você não está em nenhuma sala. Use /join <sala>.\n")
                        continue
                    self._broadcast(client.room, f"[{client.room}] {client.nickname}: {msg}", sender=client)
        except (ConnectionError, OSError):
            pass
        except Exception as e:
            client.send(f"! Erro: {e}\n")
        finally:
            # cleanup
            self.leave_room(client)
            with self.lock:
                self.clients.pop(client.conn, None)
            try:
                client.conn.close()
            except Exception:
                pass

    # ---------------------
    # Comandos
    # ---------------------
    def _handle_command(self, client: Client, line: str) -> None:
        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("/help", "/h", "/?"):
            client.send(
                "Comandos disponíveis:\n"
                "  /help                 Mostra esta ajuda\n"
                "  /nick <nome>          Define seu apelido\n"
                "  /create <sala>        Cria uma sala (se não existir)\n"
                "  /join <sala>          Entra (ou cria e entra) em uma sala\n"
                "  /rooms                Lista as salas ativas\n"
                "  /leave                Sai da sala atual\n"
                "  /quit                 Desconecta do servidor\n"
                "Mensagens sem '/' são enviadas à sua sala atual.\n"
            )
            return

        if cmd == "/nick":
            if len(parts) < 2:
                client.send("Uso: /nick <nome>\n")
                return
            new = parts[1][:32]
            with self.lock:
                old = client.nickname
                client.nickname = new
            client.send(f"Apelido alterado: {old} -> {new}\n")
            if client.room:
                self._broadcast(client.room, f"* {old} agora é {new}.")
            return

        if cmd == "/create":
            if len(parts) < 2:
                client.send("Uso: /create <sala>\n")
                return
            room = parts[1][:48]
            created = self.create_room(room)
            if created:
                client.send(f"Sala criada: {room}\n")
            else:
                client.send(f"Sala '{room}' já existe.\n")
            return

        if cmd == "/join":
            if len(parts) < 2:
                client.send("Uso: /join <sala>\n")
                return
            room = parts[1][:48]
            joined = self.join_room(client, room)
            client.send(f"Entrou na sala: {joined}\n")
            return

        if cmd == "/rooms":
            client.send(self.list_rooms() + "\n")
            return

        if cmd == "/leave":
            if not client.room:
                client.send("Você não está em nenhuma sala.\n")
                return
            self.leave_room(client)
            client.send("Você saiu da sala.\n")
            return

        if cmd == "/quit":
            client.send("Até mais!\n")
            client.alive = False
            try:
                client.conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            return

        client.send(f"Comando desconhecido: {cmd}. Use /help.\n")


# =========================
# Execução direta
# =========================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Servidor de Chat com Salas (TCP + framing)")
    parser.add_argument("--host", default="0.0.0.0", help="Endereço para escutar (padrão: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5050, help="Porta (padrão: 5050)")
    args = parser.parse_args()

    server = ChatServer(host=args.host, port=args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
        server.shutdown()
