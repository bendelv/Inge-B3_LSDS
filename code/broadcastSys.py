from flask import Flask, request
import http.client as httplib
from threading import Thread
import time
from threading import Timer
import threading
import json
import numpy as np

from abc import ABC, abstractmethod

# Implements trigger mechanisme
class Layer(ABC):
    def __init__(self, suscriber):
        self.suscriber = suscriber

    @abstractmethod
    def notify(self, message):
        pass

    def trigger(self, message):
        self.suscriber.notify(message)

class App(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.app.add_url_rule('/shutdown_server/', 'server', self.shutdown, methods=['GET'])

    def launchServer(self):
        server = Thread(target = self.launchServerNow, args =[])
        server.start()
        time.sleep(1)

    def launchServerNow(self):
        self.app.run(debug=False, use_reloader=False, host=self.host, port=self.port)

    def shutdown(self):
        self.shutdown_server()
        return 'Server shutting down...'
    def shutdown_server(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()


class CausalOrderReliableBroadcast:
    def __init__(self, own, alive, ):
        self.alive = alive
        self.vector = np.array([0]*len(self.alive))
        self.isn = 0
        self.pending = []
        "retrieve all connected adress nodes from bootstrap node"
        pass

    def broadcast(self, method, message):
        w = self.vector.copy()
        w[self.own] = self.isn
        self.isn += 1
        self.rb()
        "Send a json object to all connected user"
        pass


class BestEffortBroadcast:
    def __init__(self, own, alive):
        self.own = own
        self.alive = alive
        self.pl = PerfectLink()
        "retrieve all connected adress nodes from bootstrap node"
        pass

    def broadcast(self, method, url, data):
        for p in self.alive:
            ret, _, _, _ = self.pl.send(self.own, method, message, p, data, {'content-type': 'application/json'})
            "Send a json object to all connected user"
            self.deliver()
        pass

    def deliver(self, method, message):
        return method, message


class FailureDetector(Layer):
    def __init__(self, own, alive, timeout, flaskApp):
        self.pl = PerfectLink(flaskApp)
        self.own = own
        self.alive = alive.copy()
        self.now_alive = alive.copy()
        flaskApp.add_url_rule('/FailurDetector/deliver', 'deliver', self.deliver, methods=['POST'])
        flaskApp.add_url_rule('/FailurDetector/see', 'see', self.status, methods=['GET', 'POST'])
        self.process = alive.copy()
        self.suspected = []
        self.timeout = timeout
        self.t = Timer(self.timeout, self.timeoutCallback)
        self.t.start()
        self.time = time.time()

    def notify(message):
        pass
    #trigger functionallity
    def deliver(self):
        dict = request.get_json()
        # upon event deliver heartbeatRequest
        if dict['message'] == "request":
            self.send_heartbeat_reply(dict['to'], dict['from'])
        # upon event deliver heartbeatReply
        elif dict['message'] == "reply":
            self.alive.append(dict['from'])

        return ""

    def get_alive(self):
        return self.now_alive

    def rm_node(self, process):
        if process in self.process:
            self.process.remove(process)
        if process in self.alive:
            self.alive.remove(process)
        if process in self.suspected:
            self.suspected.remove(process)

    def add_node(self, process):
        if process not in self.process:
            self.process.append(process)
        if process not in self.alive:
            self.alive.append(process)

    def status(self):
        # optimization, implement nodes as a dict for a lookup in O(1) instead
        # of O(n), OKAY here as we assume a small amount of nodes
        title = "<h1> Status of the perfect detectors, Timeout {}</h1>".format(self.timeout)
        timeout = "<h2> Time: {0:.2f}</h2>".format(time.time() - self.time)
        ulA = "<h2>alive</h2><ul>" + "\n".join(["<li>" + x + "</li>" for x in self.alive]) + "</ul>"
        ulS = "<h2>Suspects</h2><ul>" + "\n".join(["<li>" + x + "</li>" for x in self.suspected]) + "</ul>"
        ulP = "<h2>Process</h2><ul>" + "\n".join(["<li>" + x + "</li>" for x in self.process]) + "</ul>"
        return title + timeout + ulA + ulS + ulP

    def timeoutCallback(self):
        self.now_alive = self.alive.copy()
        if len(list(set(self.alive) & set(self.suspected))) == 0:
            self.timeout += 0
        for p in self.process:
            if (p not in self.alive) and (p not in self.suspected):
                self.suspected.append(p)
            elif p in self.alive and p in self.suspected:
                self.suspected.remove(p)
            heartBeat = Thread(target = self.send_heartbeat_request, args =[self.own, p])
            if p in self.alive:
                self.alive.remove(p)
            heartBeat.start()
        self.t = Timer(self.timeout, self.timeoutCallback)
        self.t.start()
        self.time = time.time()
        pass
    # own sends heartBeat request to process
    def send_heartbeat_request(self, own, process):
        dict = {}
        dict['from'] = own
        dict['to'] = process
        dict['message'] = 'request'
        self.pl.send(process, "POST", "/FailurDetector/deliver", json.dumps(dict))
        pass
    # own send heartBeat reply to process
    def send_heartbeat_reply(self, own, process):
        dict = {}
        dict['from'] = own
        dict['to'] = process
        dict['message'] = 'reply'
        self.pl.send(process, "POST", "/FailurDetector/deliver", json.dumps(dict))
        pass

class PerfectLink(Layer):
    def __init__(self, flaskApp):
        super().__init__(None)
        self.flaskApp = flaskApp
        self.flaskApp.add_url_rule('/PerfectLink/',
                                   'message',
                                   self.deliver,
                                   methods=['POST'])
        pass

    #send message: message from process: own to process: process
    def send(self, process, method, url, data):
        # TODO handle exceptions like wring address
        try:
            conn = httplib.HTTPConnection(process, timeout=10)
            conn.request(method, url, data,  {'content-type': 'application/json'})
        except:
            return None
        return conn
    #Process delivered message correctly to own
    def deliver(self):
        args = request.args
        message = request.get_json()
        self.trigger(message)
        return ""

    def notify(self, message):
        pass


def main():
    app0 = App("192.168.1.25", "5000")
    app1 = App("192.168.1.25", "5001")
    app2 = App("192.168.1.25", "5002")
    #process = ["192.168.1.25:5000", "192.168.1.25:5001"]
    process = ["192.168.1.25:5000", "192.168.1.25:5001", "192.168.1.25:5002"]
    f0 = FailureDetector(process[0], process, 2, app0.app)
    f1 = FailureDetector(process[1], process, 5, app1.app)
    f2 = FailureDetector(process[2], process, 5, app2.app)
    app0.launchServer()
    app1.launchServer()
    app2.launchServer()
    time.sleep(10)
    #print("ADD NODE TIME")
    #pl2 = PerfectLink()
    #f0.add_node(process[2])
    #f1.add_node(process[2])

if __name__ == '__main__':
    main()
    print("EXIT MAIN !!!!")
