#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bridge WebSocket <-> TCP (framing de 4 bytes) para o ChatServer.

Uso típico:
  CHAT_HOST=127.0.0.1 CHAT_PORT=5050 \
  python ws_bridge.py --ws-host 0.0.0.0 --ws-port 8765
"""

from __future__ import annotations
import os
import asyncio
import struct
import socket
import argparse
import contextlib
from typing import Optional

import websockets  


_MAX_FRAME = 8 * 1024 * 1024  



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
        return None  # conexão fechada
    if len(header) < 4:
        header += _recv_exact(conn, 4 - len(header))
    (length,) = struct.unpack("!I", header)
    if length > _MAX_FRAME:
        raise ValueError("Frame muito grande.")
    if length == 0:
        return ""
    data = _recv_exact(conn, length)
    return data.decode("utf-8", errors="replace")



class TCPChatConn:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port))

    def close(self) -> None:
        if not self.sock:
            return
        with contextlib.suppress(Exception):
            self.sock.shutdown(socket.SHUT_RDWR)
        with contextlib.suppress(Exception):
            self.sock.close()
        self.sock = None



async def ws_handler(ws, chat_host: str, chat_port: int) -> None:
    """
    Para cada cliente WebSocket criamos uma conexão TCP dedicada ao servidor de chat.
    O navegador envia/recebe texto; o bridge aplica/retira o framing de 4 bytes.
    """
    tcp = TCPChatConn(chat_host, chat_port)
    loop = asyncio.get_running_loop()


    try:
        tcp.connect()
        await ws.send(f"[bridge] conectado ao chat TCP {chat_host}:{chat_port}")
    except Exception as e:
       
        with contextlib.suppress(Exception):
            await ws.send(f"[bridge] falha ao conectar no chat {chat_host}:{chat_port} -> {e}")
        with contextlib.suppress(Exception):
            await ws.close()
        return

    async def pump_tcp_to_ws():
        """Lê frames do TCP (em executor) e envia para o WebSocket."""
        try:
            while True:
                msg = await loop.run_in_executor(None, lambda: recv_frame(tcp.sock))
                if msg is None:
                    # TCP caiu/fechou
                    await ws.send("[bridge] desconectado do servidor de chat.")
                    with contextlib.suppress(Exception):
                        await ws.close()
                    break
                await ws.send(msg)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            with contextlib.suppress(Exception):
                await ws.send(f"[bridge] erro TCP->WS: {e}")
            with contextlib.suppress(Exception):
                await ws.close()

    async def pump_ws_to_tcp():
        """Lê mensagens do WS e envia como frames para o TCP (em executor)."""
        try:
            async for message in ws:
                if not isinstance(message, str):
                    if isinstance(message, (bytes, bytearray)):
                        message = message.decode("utf-8", errors="replace")
                    else:
                        message = str(message)
                await loop.run_in_executor(None, lambda: send_frame(tcp.sock, message))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # Qualquer erro no caminho WS->TCP encerra o TCP
            with contextlib.suppress(Exception):
                await ws.send(f"[bridge] erro WS->TCP: {e}")
        finally:
            tcp.close()

    # Inicia as bombas em paralelo e espera a primeira terminar
    task_tcp_to_ws = asyncio.create_task(pump_tcp_to_ws(), name="tcp->ws")
    task_ws_to_tcp = asyncio.create_task(pump_ws_to_tcp(), name="ws->tcp")

    done, pending = await asyncio.wait(
        {task_tcp_to_ws, task_ws_to_tcp},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancela a tarefa remanescente
    for t in pending:
        t.cancel()
        with contextlib.suppress(Exception):
            await t

    # Garante fechamento
    tcp.close()
    with contextlib.suppress(Exception):
        await ws.close()



async def amain() -> None:
    parser = argparse.ArgumentParser(description="Bridge WebSocket <-> TCP (framing) para ChatServer")
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument("--ws-port", type=int, default=8765)
    parser.add_argument("--chat-host", default=os.environ.get("CHAT_HOST", "127.0.0.1"))
    parser.add_argument("--chat-port", type=int, default=int(os.environ.get("CHAT_PORT", "5050")))
    parser.add_argument("--ping-interval", type=float, default=20.0, help="Intervalo de ping do WS (s)")
    parser.add_argument("--ping-timeout", type=float, default=20.0, help="Timeout de ping do WS (s)")
    args = parser.parse_args()

    print(f"[bridge] WS em ws://{args.ws_host}:{args.ws_port} -> TCP {args.chat_host}:{args.chat_port}")

    
    async with websockets.serve(
        lambda ws: ws_handler(ws, args.chat_host, args.chat_port),
        args.ws_host,
        args.ws_port,
        ping_interval=args.ping_interval,
        ping_timeout=args.ping_timeout,
        max_size=_MAX_FRAME + 8,
    ):
        
        await asyncio.Future()


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("\n[bridge] encerrado por KeyboardInterrupt")


if __name__ == "__main__":
    main()
