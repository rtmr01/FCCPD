#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente de terminal para o servidor de chat.
Usa o mesmo framing (4 bytes) e oferece uma interface de linha de comando.
Python 3.11
"""

from __future__ import annotations
import socket
import struct
import threading
import sys

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
            raise ConnectionError("Conexão encerrada.")
        buf.extend(chunk)
    return bytes(buf)

def recv_frame(conn: socket.socket) -> str | None:
    header = conn.recv(4)
    if not header:
        return None
    if len(header) < 4:
        header += _recv_exact(conn, 4 - len(header))
    (length,) = struct.unpack("!I", header)
    if length > _MAX_FRAME:
        raise ValueError("Frame muito grande.")
    if length == 0:
        return ""
    data = _recv_exact(conn, length)
    return data.decode("utf-8", errors="replace")

def reader_loop(conn: socket.socket):
    try:
        while True:
            msg = recv_frame(conn)
            if msg is None:
                print("\n[desconectado do servidor]")
                break
            print(msg, end="" if msg.endswith("\n") else "\n")
    except Exception as e:
        print(f"\n[erro de recepção: {e}]")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        # encerra o processo caso o lado de leitura termine
        try:
            sys.exit(0)
        except SystemExit:
            pass

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cliente de Chat (TCP + framing)")
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor (padrão: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5050, help="Porta do servidor (padrão: 5050)")
    args = parser.parse_args()

    conn = socket.create_connection((args.host, args.port))
    print(f"[conectado a {args.host}:{args.port}]")
    threading.Thread(target=reader_loop, args=(conn,), daemon=True).start()

    try:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            send_frame(conn, line)
            if line.strip().lower() == "/quit":
                break
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[erro de envio: {e}]")
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
