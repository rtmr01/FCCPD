# cliente.py
import socket
import threading
import sys
from typing import Optional

HOST = "127.0.0.1"
PORT = 12345

HEADER_LEN = 4
MAX_MSG = 1 << 20  # 1 MB de limite defensivo

def send_msg(sock: socket.socket, data: bytes) -> None:
    size = len(data).to_bytes(HEADER_LEN, "big")
    sock.sendall(size + data)

def recv_exactly(sock: socket.socket, n: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)

def recv_msg(sock: socket.socket) -> Optional[bytes]:
    header = recv_exactly(sock, HEADER_LEN)
    if header is None:
        return None
    size = int.from_bytes(header, "big")
    if size < 0 or size > MAX_MSG:
        # tamanho inválido ou abusivo
        return None
    payload = recv_exactly(sock, size)
    return payload

def receiver(sock: socket.socket):
    while True:
        try:
            data = recv_msg(sock)
            if data is None:
                print("\n[AVISO] Conexão encerrada pelo servidor.")
                break
            texto = data.decode("utf-8", errors="ignore")
            # limpa a linha do prompt e imprime a mensagem recebida
            sys.stdout.write("\r" + " " * 200 + "\r")
            sys.stdout.flush()
            print(texto)
            print("Você: ", end="", flush=True)
        except Exception:
            break
    try:
        sock.close()
    except Exception:
        pass

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print("[ERRO] Não foi possível conectar ao servidor.")
        return

    print(f"[OK] Conectado a {HOST}:{PORT}")

    t = threading.Thread(target=receiver, args=(sock,), daemon=True)
    t.start()

    try:
        # Handshake: servidor pergunta o nome
        first = recv_msg(sock)
        if first is None:
            print("[ERRO] Servidor encerrou a conexão.")
            return
        sys.stdout.write(first.decode("utf-8", errors="ignore"))
        sys.stdout.flush()

        nome = input().strip()
        send_msg(sock, nome.encode("utf-8"))

        while True:
            msg = input("Você: ").strip()
            if not msg:
                continue
            send_msg(sock, msg.encode("utf-8"))
            if msg.lower().startswith("/quit") or msg.lower() == "sair":
                break

    except KeyboardInterrupt:
        try:
            send_msg(sock, b"/quit")
        except Exception:
            pass
    finally:
        try:
            sock.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
