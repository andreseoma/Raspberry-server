import socket
import sys
import threading
import queue
import time
import re
import queue
import select
import tornado.ioloop
import tornado.web
import tornado.gen
import tornado.locks
import threading

tableHeader = """<tr>
	<th>ID</th>
	<th style="padding-right: 35px;">Status</th>
	<th>LEDS</th>
</tr>"""
ledStart = """<tr id="row{ID}">
	<td>{ID}</td>
	<td>{name}</td>
	<td style="text-align:center; padding-right: 5px;">
	{ledentries}</td>
</tr>"""
ledEntry = """<img id="led{ID},{led}" onclick="ledClick2({ID},{led})" src="static/green-led-{status}-md.png" width="40" height="40">"""

class MainHandler(tornado.web.RequestHandler):
    @staticmethod
    def tableData():
        tableEntries = ""
        with Client.clientDictLock:
            clients = Client.clientDict
        print("Clients:", clients)
        for id in sorted(clients.keys()):
            data = clients[id].data
            ledStuff = ""
            if "leds" in data:
                print("Leds:", data["leds"])
                for n in range(len(data["leds"])):
                    ledStuff += ledEntry.format(ID = id, led = n+1, status = "on" if data["leds"][n]=="1" else "off")
            #print(ledstuff)
            tableEntries += ledStart.format(ID=id, name=data["name"], ledentries = ledStuff)
        return tableHeader + tableEntries

    @staticmethod
    def mainPage():
        file = open("testpage.html")
        contents = file.read()
        file.close()
        return contents.replace("{tableEntries}", MainHandler.tableData())
        
    def get(self):
        self.write(self.mainPage())
        print("Main get finish\n")

    def post(self):
        data = self.request.body.decode("utf-8")
        print("Got:"+data)
        print("As a list:"+str(self.request.arguments))
        if data.startswith("LED"):
            print("here")
            id = int(self.request.arguments["id"][0])
            led = int(self.request.arguments["led"][0])
            device = Client.clientDict[id]
            with device.dataLock:
                leds = device.data["leds"]
                lednew = "1" if leds[led-1]=="0" else "0"
                leds = leds[:led-1]+lednew+leds[led:]
                device.data["leds"] = leds
                Client.clientDict[id].sendcmd("param;leds="+leds)
                print("New leds:", leds)
            #send updated info to all the connections
                self.write("OK")
            self.application.website.condition.notify_all() #notify everyone to update their page

class images(tornado.web.RequestHandler):
    def get(self, filename):
        file = open(filename, 'rb')
        self.write(file.read())
        file.close()

class EventSource(tornado.web.RequestHandler):
    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        self.led = 1
        self.condition = self.application.website.condition

    @tornado.gen.coroutine
    def get(self):
        while True:
            yield self.condition.wait()
            yield self.update()
            if self._finished:
                break

    @tornado.gen.coroutine
    def update(self):
        try:
            self.write("data:"+MainHandler.tableData().replace("\n","")+"\n\n")
            #self.write("data:"+MainHandler.mainPage().replace("\n","")+"\n\n") #update the page with new data
            yield self.flush()
        except tornado.iostream.StreamClosedError:
            self.finish()
            return

class website:
    def __init__(self):
        self.condition = tornado.locks.Condition()
        self.app = tornado.web.Application([
            (r"/", MainHandler),
            (r"/events", EventSource),
        ], static_path="static")
        self.app.listen(80)
        self.app.website = self
        self.ioloop = tornado.ioloop.IOLoop.current()
        self.thread = threading.Thread(target = self.ioloop.start)
        self.thread.start()

    def update(self):
        self.ioloop.add_callback(self.notifyCondition)
        pass

    def notifyCondition(self):
        self.condition.notify_all()


class Client:
    """All commands end with a newline \n. After a connection from the client,
    the handler sends an "ID\n" request and to that the client responds with data
    describing itself in the format "type=PC;name=Doe;\n" and so on with all
    of the parameters. The parameters are saved in a dict. The parameters can be changed
    by sending for example "param;name=test", to which the server responds "OK\n".
    After this the server assigns the device an unique id currently not
    in use like this "ID=1\n", to which the client responds "OK\n". Now the connection is
    established. The server sends the id of the first client with the name name to
    the request "GetID?name\n" with the syntax "ID=7\n". It also sends all the IDs in use with ; separator as
    a response to "GetIDs?\n"".
    Data can be sent for example from client 1 to client 7 by using it's id "To7=message\n",
    to which the server responds "OK\n".
    The server sends to the other client "From1=message\n", to which it must respond "OK\n".
    """
    clientDict = {}
    clientDictLock = threading.Lock()
    
    def send(self, string):
        with self.msgLock:
            print("Sending:", string)
            self.conn.sendall(string.encode("utf-8"))
    def recv(self, bytes):
        #with self.msgLock:
            string = self.conn.recv(bytes).decode("utf-8")
            print("Received:", string)
            return string
    def recvcmd(self):
        #with self.msgLock:
            string = ""
            while True:
                character = self.conn.recv(1).decode("utf-8")
                if character == "\n":
                    break
                string+=character
            print("Received command:", string)
            return string

    def checkAndRecvCmd(self):
        #with self.msgLock:
            self.conn.settimeout(0)
            try:
                character = self.conn.recv(1).decode("utf-8")
                if character != "\n":
                    self.conn.settimeout(4)
                    return character+recvcmd()
            except:
                pass
            self.conn.settimeout(4)
            return ""
    def sendcmd(self,string):
        with self.msgLock:
            print("Sending command:", string)
            self.conn.sendall((string+"\n").encode("utf-8"))
    def checkOK(self):
        if self.recvcmd() != "OK":
            print("Did not receive OK!!!")
    
    def __init__(self, conn, address):
        self.conn = conn
        self.address = address
        self.data = {}
        self.msgLock = threading.Lock()
        self.dataLock = threading.Lock()
        
        print("Connection from:", address)
        self.thread = threading.Thread(target = self.startCommunication).start()

    def startCommunication(self):
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
        site.update()
        self.msgloop()

    def msgloop(self):
        while True:
            self.conn.settimeout(None)
            try:
                command = self.recvcmd()
            except:
                with Client.clientDictLock:
                    del Client.clientDict[self.id]
                site.update()
                return
            self.conn.settimeout(4)
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
                    sendcmd("NONE")
            elif command == "GETIDs?":
                response = ""
                for id, client in Client.clientDict.items():
                    response += client.data["name"] + "=" + str(id)+";"
                sendcmd(response[:-1])
            elif command.startswith("To"):
                id, data = re.match(r"To(\d*)=(.*)", command).groups()
                self.sendcmd("OK\n")
                Client.clientDict[int(id)].sendcmd("From"+id+"="+data)
            elif command.startswith("param;"):
                param, value = re.match(r"param;(.*?)=(.*)", command).groups()
                with self.dataLock:
                    self.data[param] = value
                site.update()



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
        conn, address = s.accept()
        Client(conn, address)

