import socket
import sys
import time

class Client:
    port = 8890
    HOST = '127.0.0.1'
    name = "testing"
    leds = "0000"
    
    def send(self, string):
        print("Sending:", string)
        self.conn.sendall(string.encode("utf-8"))
    def recv(self, bytes):
        string = self.conn.recv(bytes).decode("utf-8")
        print("Received:", string)
        return string
    def recvcmd(self):
        string = ""
        while True:
            character = self.conn.recv(1).decode("utf-8")
            if character == "\n":
                break
            string+=character
        print("Received command:", string)
        return string
    def sendcmd(self,string):
        print("Sending command:", string)
        self.conn.sendall((string+"\n").encode("utf-8"))
        
    def __init__(self):
        try:
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.conn.connect((Client.HOST, Client.port))
            print("Connected")
        except socket.error as err:
            print("Error:", err)
            sys.exit()
        
        self.recvcmd()
        self.sendcmd("name=testing;leds=000")
        self.id = self.recvcmd()
        self.sendcmd("OK")
        self.msgloop()

    def msgloop(self):
        while True:
            command = self.recvcmd()
            if command.startswith("FromServer="):
                self.sendcmd("OK")
        
Client()