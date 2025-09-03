# cliente.py
import socket
import threading
import sys

HOST = "127.0.0.1"
PORT = 12345

def receiver(sock: socket.socket):
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                print("\n[AVISO] Conexão encerrada pelo servidor.")
                break
            texto = data.decode("utf-8", errors="ignore")
            print("\r" + texto, end="")
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
        first_line = sock.recv(4096).decode("utf-8", errors="ignore")
        sys.stdout.write(first_line)
        sys.stdout.flush()
        nome = input().strip()
        sock.sendall(nome.encode("utf-8"))

        while True:
            msg = input("Você: ").strip()
            if not msg:
                continue
            sock.sendall(msg.encode("utf-8"))
            if msg.lower().startswith("/quit") or msg.lower() == "sair":
                break
    except KeyboardInterrupt:
        try:
            sock.sendall("/quit".encode("utf-8"))
        except Exception:
            pass
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
