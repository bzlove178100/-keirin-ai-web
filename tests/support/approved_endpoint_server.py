"""Synthetic approved endpoint. No external network, credentials or real service."""
import socket

HOST = "0.0.0.0"
PORT = 18443
REQUEST = b"synthetic-egress-check"
RESPONSE = b"synthetic-egress-ok"


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(4)
        server.settimeout(20)
        for _ in range(2):
            connection, _ = server.accept()
            with connection:
                connection.settimeout(2)
                if connection.recv(64) != REQUEST:
                    raise RuntimeError("synthetic_approved_endpoint_request_invalid")
                connection.sendall(RESPONSE)


if __name__ == "__main__":
    main()
