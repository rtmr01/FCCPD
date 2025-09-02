# servidor.py

import socket
import threading

# Classe para representar a thread que vai cuidar de cada cliente
class ClientThread(threading.Thread):
    def __init__(self, client_socket, client_address):
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.client_address = client_address
        print(f"[NOVA CONEXÃO] {self.client_address} conectado.")

    def run(self):
        # Loop principal para comunicação com o cliente
        while True:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message:
                    print(f"[{self.client_address}] {message}")
                    # Lógica para processar a mensagem e responder
                    response = f"Servidor recebeu: {message}"
                    self.client_socket.send(response.encode('utf-8'))
                else:
                    # Cliente desconectou
                    break
            except:
                break
        
        print(f"[CONEXÃO ENCERRADA] {self.client_address} desconectou.")
        self.client_socket.close()

# --- Função Principal do Servidor ---
def main():
    HOST = '127.0.0.1'  # Endereço IP do Servidor
    PORT = 12345        # Porta que o Servidor vai escutar

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[ESCUTANDO] Servidor está escutando em {HOST}:{PORT}")

    # Loop para aceitar novas conexões
    while True:
        client_socket, client_address = server_socket.accept()
        # Cria uma nova thread para cada cliente que se conecta
        new_thread = ClientThread(client_socket, client_address)
        new_thread.start()

if __name__ == "__main__":
    main()