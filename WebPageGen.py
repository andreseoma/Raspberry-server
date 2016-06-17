import threading
import re
import tornado.ioloop
import tornado.web
import tornado.gen
import tornado.locks
from ClientHandler import *

#these are the table data that are used for generating the web page
tableHeader = """<tr>
	<th>ID</th>
	<th style="padding-right: 35px;">Status</th>
	<th>LEDS</th>
	<th>Send a command</th>
</tr>"""
ledStart = """<tr id="row{ID}">
	<td>{ID}</td>
	<td>{name}</td>
	<td style="text-align:left; padding-right: 5px;">
	{ledentries}</td>
	<td style="padding-right:5px;">
	<textarea id="text{ID}"  onkeydown="return sendCommand({ID})"></textarea></td>
	<td id="response{ID}">Press enter to send</td>
</tr>"""
ledEntry = """<img id="led{ID},{led}" onclick="ledClick2({ID},{led})" src="static/green-led-{status}-md.png" width="40" height="40">"""

class MainHandler(tornado.web.RequestHandler):
    @staticmethod
    def tableData():
        #it generates the table according to the clients in clientDict
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
        #this reads the html from the file, puts in the table and returns it
        file = open("testpage.html")
        contents = file.read()
        file.close()
        return contents.replace("{tableEntries}", MainHandler.tableData())
        
    def get(self, parameter):
        #when a client opens the website with his browser, this method gets called, it sends the html with the table
        #to the browser
        self.write(self.mainPage())

    @tornado.web.asynchronous
    def post(self, parameter):
        #when a led is clicked on in the browser or enter is pressed in the text area,
        #this method gets called, the parameter is "leds" or "send" accordingly
        data = self.request.body.decode("utf-8")
        print("Got: "+data+". Parameter: " + parameter)
        if parameter == "leds":
            id = int(self.request.arguments["id"][0])
            led = int(self.request.arguments["led"][0])
            device = Client.clientDict[id]
            with device.dataLock:
                leds = device.data["leds"]
                lednew = "1" if leds[led-1]=="0" else "0"
                leds = leds[:led-1]+lednew+leds[led:]
                device.data["leds"] = leds #update the led states on the device object
                Client.clientDict[id].sendcmd("param;leds="+leds) #send the new led state to the device
                self.write("Leds updated") #send data to the browser for debugging purposes
            self.application.website.condition.notify_all() #notify everyone to update their page
            self.finish() #finish the send
        elif parameter == "send":
            id = int(self.request.arguments["id"][0])
            cmd = self.request.arguments["cmd"][0].decode("utf-8")
            print("Got a command:", cmd+" .ID:",id)
            client = Client.clientDict[id]
            with client.dataLock:
                #notify the client handler that we are waiting for a response and where to respond
                client.waitingForAResponse = True
                client.responseDestination = self
            client.sendcmd("FromServer="+cmd) #send the info to the device
            #don't finish the post, because the clienthandler will receive a response
        else:
            self.finish()

class EventSource(tornado.web.RequestHandler):
    #this is for pushing the updated html to the browsers as the data is changed
    def initialize(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        self.condition = self.application.website.condition

    @tornado.gen.coroutine
    def get(self):
        #each browser calls this method, it waits until new data is available (waits on the condition)
        #and then it sends new data to the browser, which then updates the table in the browser using javascript
        while True:
            yield self.condition.wait()
            yield self.update()
            if self._finished:
                break

    @tornado.gen.coroutine
    def update(self):
        #this sends the whole table to the browser
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
            (r"/(send|leds)?$", MainHandler),
            (r"/events", EventSource),
        ], static_path="static")
        self.app.listen(80)
        self.app.website = self
        self.ioloop = tornado.ioloop.IOLoop.current()
        self.thread = threading.Thread(target = self.ioloop.start)
        self.thread.start()

    def update(self):
        #this function can be safely called from other threads, only this method is threadsafe,
        #because the notification has to be made by the webserver main thread
        self.ioloop.add_callback(self.notifyCondition)
        pass

    def notifyCondition(self):
        self.condition.notify_all()