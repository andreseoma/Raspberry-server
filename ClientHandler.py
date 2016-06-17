import socket
import threading

class Client:
    """All commands end with a newline \n. After a connection from the client,
    the handler sends an "ID\n" request and to that the client responds with data
    describing itself in the format for example "type=PC;name=Doe;\n" and so on with all
    of the parameters. The parameters are saved in a dict. The parameters can be changed
    by sending for example "param;name=test\n", to which the server responds "OK\n".
    Also the server can change a parameter by sending the previous command.
    After this the server assigns the device an unique id currently not
    in use like this "ID=1\n", to which the client responds "OK\n". Now the connection is
    established.
    The server sends the id of the first client with the given name to
    the request "GetID?name\n" with the syntax "ID=7\n". It also sends all the IDs in use with ; separator as
    a response to "GetIDs?\n"".
    Data can be sent for example from client 1 to client 7 by using it's id "To7=message\n",
    to which the server responds "OK\n".
    The server sends to the other client "From1=message\n", to which it must respond something.
    """
    clientDict = {}
    clientDictLock = threading.Lock()
    
    def send(self, string):
        with self.msgLock:
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
        with self.msgLock:
            print("Sending command:", string)
            self.conn.sendall((string+"\n").encode("utf-8"))
    def checkOK(self):
        if self.recvcmd() != "OK":
            print("Did not receive OK!!!")
    
    def __init__(self, conn, address, site):
        self.conn = conn
        self.address = address
        self.data = {}
        self.msgLock = threading.Lock()
        self.dataLock = threading.Lock()
        self.waitingForAResponse = False
        self.site = site
        
        print("Connection from:", address)
        self.thread = threading.Thread(target = self.startCommunication).start()

    def startCommunication(self):
        #exchange the initial information as explained before
        self.sendcmd("ID")
        self.conn.settimeout(4)
        try:
            msg = self.recvcmd()
            with self.dataLock:
                for pairs in msg.split(";"):
                    param, value = pairs.split("=",1)
                    self.data[param] = value
        except socket.timeout as err:
            print("Client didn't respond, dropping")
            conn.close()
            return

        #give the client a unique id and put it in a dictionary
        with Client.clientDictLock:
            self.id = 1
            while True:
                if self.id in Client.clientDict:
                    self.id += 1
                else:
                    break
            Client.clientDict[self.id] = self
        
        self.sendcmd("ID={}".format(self.id))
        self.checkOK()
        self.site.update()
        self.msgloop()

    def msgloop(self):
        while True:
            #wait for a command
            self.conn.settimeout(None)
            try:
                command = self.recvcmd()
            except:
                with Client.clientDictLock:
                    del Client.clientDict[self.id]
                self.site.update()
                return
            self.conn.settimeout(4)
            if self.waitingForAResponse:
                with self.dataLock:
                    #a message was sent to the device by the webserver, update the site with the response
                    self.waitingForAResponse = False
                    self.responseDestination.write(command)
                    self.responseDestination.finish()
                continue
            if command == "":
                continue
            elif command.startswith("GetID?"):
                sent = False
                name = command.split("?",1)[1]
                for client in Client.clientDict.values():
                    if client.data["name"] == name:
                        self.sendcmd("ID="+str(client.id))
                        sent = True
                        break
                if not sent:
                    self.sendcmd("NONE")
            elif command == "GETIDs?":
                response = ""
                for id, client in Client.clientDict.items():
                    response += client.data["name"] + "=" + str(id)+";"
                sendcmd(response[:-1])
            elif command.startswith("To"):
                match = re.match(r"To(\d*)=(.*)", command)
                if match:
                    id, data = match.groups()
                    if int(id) in Client.clientDict:
                        self.sendcmd("OK")
                        Client.clientDict[int(id)].sendcmd("From"+id+"="+data)
                    else:
                        self.sendcmd("BAD ID")
                else:
                    self.sendcmd("BAD REQUEST")
            elif command.startswith("param;"):
                match = re.match(r"param;(.*?)=(.*)", command)
                if match:
                    param, value = match.groups()
                    with self.dataLock:
                        self.data[param] = value
                    self.site.update()
                    self.sendcmd("OK")

if __name__ == "__main__":
    from WebPageGen import *
    port = 8890
    HOST = ''
    site = website()
    print("Website starting.")

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST,port))
        s.listen(10)
    except socket.error as err:
        print("Error:", err)
        sys.exit()

    while True:
        while 1:
            #wait for new connections and make a new object, which handles the client in a new thread
            conn, address = s.accept()
            Client(conn, address, site)
