#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor de Chat Multithread com Salas + Message Framing (4 bytes)
Com logging detalhado (conexões, comandos, mensagens, erros).
Python 3.11+
"""

from __future__ import annotations
import socket
import struct
import threading
import logging
import logging.handlers
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Set, Tuple, List


_MAX_FRAME = 8 * 1024 * 1024  # 8 MB

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
    header = conn.recv(4)
    if not header:
        return None
    if len(header) < 4:
        header += _recv_exact(conn, 4 - len(header))
    (length,) = struct.unpack("!I", header)
    if length > _MAX_FRAME:
        raise ValueError("Frame muito grande (possível protocolo inválido).")
    if length == 0:
        return ""
    data = _recv_exact(conn, length)
    return data.decode("utf-8", errors="replace")



@dataclass(eq=False)
class Client:
    conn: socket.socket
    addr: Tuple[str, int]
    nickname: str = field(default_factory=lambda: "anon")
    room: Optional[str] = None
    alive: bool = True

    def send(self, msg: str) -> None:
        try:
            send_frame(self.conn, msg)
        except Exception:
            self.alive = False



class ChatServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5050,
        *,
        max_log_chars: int = 200,
        logger: Optional[logging.Logger] = None,
    ):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

        
        self.lock = threading.Lock()
        self.clients: Dict[socket.socket, Client] = {}
        self.rooms: Dict[str, Set[Client]] = {}

       
        self._shutdown = threading.Event()

      
        self.log = logger or logging.getLogger("chatserver")
        self.max_log_chars = max_log_chars

    
    def _clip(self, s: str) -> str:
        if s is None:
            return ""
        if len(s) <= self.max_log_chars:
            return s
        return s[: self.max_log_chars] + f"... (+{len(s)-self.max_log_chars} chars)"

    def _client_id(self, c: Client) -> str:
        return f"{c.addr[0]}:{c.addr[1]}|{c.nickname or 'anon'}"

    
    def create_room(self, name: str) -> bool:
        with self.lock:
            if name in self.rooms:
                self.log.debug("create_room: já existe room=%s", name)
                return False
            self.rooms[name] = set()
            self.log.info("room_created room=%s", name)
            return True

    def join_room(self, client: Client, room: str) -> str:
        prev_to_notify: Optional[str] = None
        with self.lock:
            if room not in self.rooms:
                self.rooms[room] = set()
                self.log.info("room_created (auto) room=%s by=%s", room, self._client_id(client))

            if client.room and client in self.rooms.get(client.room, set()):
                prev_to_notify = client.room
                self.rooms[client.room].discard(client)
                self.log.info("room_leave room=%s client=%s", prev_to_notify, self._client_id(client))

            self.rooms[room].add(client)
            client.room = room
            joined_room = room

      
        if prev_to_notify:
            self._broadcast(prev_to_notify, f"* {client.nickname} saiu da sala.")
        self._broadcast(joined_room, f"* {client.nickname} entrou na sala.")
        self.log.info("room_join room=%s client=%s", joined_room, self._client_id(client))
        return joined_room

    def leave_room(self, client: Client) -> None:
        room_to_notify: Optional[str] = None
        with self.lock:
            if client.room and client in self.rooms.get(client.room, set()):
                room_to_notify = client.room
                self.rooms[client.room].discard(client)
                client.room = None
                self.log.info("room_leave room=%s client=%s", room_to_notify, self._client_id(client))

        
        if room_to_notify:
            self._broadcast(room_to_notify, f"* {client.nickname} saiu da sala.")

    def list_rooms(self) -> str:
        with self.lock:
            parts = [f"- {r} ({len(members)} online)" for r, members in self.rooms.items()]
        self.log.debug("rooms_list count=%d", len(parts))
        return "Salas:\n" + ("\n".join(parts) if parts else "(nenhuma)")

   
    def _broadcast(self, room: str, msg: str, *, sender: Optional[Client] = None) -> None:
        with self.lock:
            targets = list(self.rooms.get(room, set()))
        dead: List[Client] = []
        for c in targets:
            c.send(msg)
            if not c.alive:
                dead.append(c)
        if dead:
            with self.lock:
                for c in dead:
                    self.rooms.get(room, set()).discard(c)
                    self.clients.pop(c.conn, None)
        self.log.debug(
            "broadcast room=%s size=%d from=%s msg=%s",
            room, len(targets),
            self._client_id(sender) if sender else "server",
            self._clip(msg),
        )

    
    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        self.log.info("server_listen host=%s port=%d", self.host, self.port)

        try:
            while not self._shutdown.is_set():
                try:
                    conn, addr = self.sock.accept()
                except OSError:
                    break
                client = Client(conn=conn, addr=addr)
                with self.lock:
                    self.clients[conn] = client
                self.log.info("client_connected addr=%s:%d", addr[0], addr[1])
                threading.Thread(
                    target=self._handle_client,
                    name=f"client-{addr[0]}:{addr[1]}",
                    args=(client,),
                    daemon=True,
                ).start()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._shutdown.is_set():
            return
        self._shutdown.set()
        self.log.info("server_shutdown_initiated")
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
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
        self.log.info("server_shutdown_complete active_clients=%d", len(clients))

   
    def _handle_client(self, client: Client) -> None:
        client.send(
            "Bem-vindo ao servidor de chat!\n"
            "Use /help para ver os comandos. Defina um apelido com /nick <nome>.\n"
        )
        try:
            while client.alive and not self._shutdown.is_set():
                msg = recv_frame(client.conn)
                if msg is None:
                    self.log.info("client_disconnected %s", self._client_id(client))
                    break
                raw = msg
                msg = msg.strip()
                if not msg:
                    self.log.debug("client_empty_msg %s", self._client_id(client))
                    continue

                self.log.debug("client_recv %s room=%s msg=%s",
                               self._client_id(client), client.room, self._clip(raw))

                if msg.startswith("/"):
                    self._handle_command(client, msg)
                else:
                    if not client.room:
                        client.send("! Você não está em nenhuma sala. Use /join <sala>.\n")
                        self.log.warning("msg_no_room %s msg=%s",
                                         self._client_id(client), self._clip(msg))
                        continue
                    self._broadcast(client.room, f"[{client.room}] {client.nickname}: {msg}", sender=client)
        except (ConnectionError, OSError) as e:
            self.log.info("client_io_error %s err=%s", self._client_id(client), repr(e))
        except Exception:
            client.send("! Erro interno no servidor.\n")
            self.log.exception("client_exception %s", self._client_id(client))
        finally:
            
            self.leave_room(client)
            with self.lock:
                self.clients.pop(client.conn, None)
            try:
                client.conn.close()
            except Exception:
                pass
            self.log.info("client_handler_end %s", self._client_id(client))

    
    def _handle_command(self, client: Client, line: str) -> None:
        parts = line.split()
        cmd = parts[0].lower()
        self.log.info("command %s cmd=%s args=%s room=%s",
                      self._client_id(client), cmd, parts[1:], client.room)

        if cmd in ("/help", "/h", "/?"):
            client.send(
                "Comandos disponíveis:\n"
                "  /help                 Mostra esta ajuda\n"
                "  /nick <nome>          Define seu apelido\n"
                "  /create <sala>        Cria uma sala (se não existir)\n"
                "  /join <sala>          Entra (ou cria e entra) em uma sala\n"
                "  /rooms                Lista as salas ativas\n"
                "  /leave                Sai da sala atual\n"
                "  /who                  Lista membros da sua sala\n"
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
            self.log.info("nick_change %s old=%s new=%s", self._client_id(client), old, new)
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

        if cmd == "/who":
            if not client.room:
                client.send("Você não está em nenhuma sala.\n")
                return
            with self.lock:
                members = [c.nickname for c in self.rooms.get(client.room, set())]
            client.send("Membros na sala:\n" + "\n".join(f" - {m}" for m in members) + "\n")
            self.log.debug("who room=%s members=%d requester=%s",
                           client.room, len(members), self._client_id(client))
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
        self.log.warning("unknown_command %s cmd=%s", self._client_id(client), cmd)



def _setup_logger(log_file: Optional[str], level: str, json_mode: bool,
                  rotate_mb: int, backups: int) -> logging.Logger:
    logger = logging.getLogger("chatserver")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)

    if json_mode:
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
                    "level": record.levelname,
                    "thread": record.threadName,
                    "msg": record.getMessage(),
                    "logger": record.name,
                }
                if record.exc_info:
                    payload["exc"] = self.formatException(record.exc_info)
                return json.dumps(payload, ensure_ascii=False)
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    if log_file:
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=rotate_mb * 1024 * 1024, backupCount=backups, encoding="utf-8"
        )
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Servidor de Chat com Salas (TCP + framing) + Logging")
    parser.add_argument("--host", default="0.0.0.0", help="Endereço para escutar (padrão: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5050, help="Porta (padrão: 5050)")
    parser.add_argument("--log-file", default=None, help="Caminho do arquivo de log (padrão: stdout)")
    parser.add_argument("--log-level", default="INFO", help="Nível de log (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--log-json", default="false", help="true/false para JSON lines")
    parser.add_argument("--log-rotate-mb", type=int, default=20, help="Tamanho de rotação (MB)")
    parser.add_argument("--log-backups", type=int, default=5, help="Qntd de arquivos de backup")
    parser.add_argument("--max-log-chars", type=int, default=200, help="Truncar mensagens longas no log")
    args = parser.parse_args()

    logger = _setup_logger(
        log_file=args.log_file,
        level=args.log_level,
        json_mode=str(args.log_json).lower() in ("1", "true", "yes", "y"),
        rotate_mb=args.log_rotate_mb,
        backups=args.log_backups,
    )

    server = ChatServer(
        host=args.host,
        port=args.port,
        max_log_chars=args.max_log_chars,
        logger=logger,
    )
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        server.shutdown()
