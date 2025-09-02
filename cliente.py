import socket
import threading

def receive_messages(client_socket):
    """
    Escuta por mensagens do servidor e as imprime no console.
    Executa em uma loop infinito até que a conexão seja encerrada.
    """
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                print("\n[AVISO] O servidor encerrou a conexão.")
                break
            
            print(f"\rServidor: {message}\nVocê: ", end="")

        except ConnectionResetError:
            print("\n[ERRO] A conexão foi perdida com o servidor.")
            break
        except Exception as e:
            print(f"\n[ERRO] Ocorreu um erro: {e}")
            break
            
    client_socket.close()


def main():
    HOST = '127.0.0.1'  
    PORT = 12345        

    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    
    try:
        client_socket.connect((HOST, PORT))
        print(f"[CONECTADO] Conectado ao servidor em {HOST}:{PORT}")
        print("Digite 'sair' a qualquer momento para encerrar a conexão.")
    except ConnectionRefusedError:
        print("[FALHA] Não foi possível se conectar ao servidor. Verifique se ele está em execução.")
        return 

   
    receive_thread = threading.Thread(target=receive_messages, args=(client_socket,), daemon=True)
    receive_thread.start()

    
    try:
        while True:
            message = input("Você: ")
            
            if message.lower() == 'sair':
                print("[DESCONECTANDO] Encerrando a conexão...")
                break

            client_socket.send(message.encode('utf-8'))

    except KeyboardInterrupt:
        print("\n[DESCONECTANDO] Encerrando a conexão...")
    finally:
        client_socket.close()

if __name__ == "__main__":
    main()