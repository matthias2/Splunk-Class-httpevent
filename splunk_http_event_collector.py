"""splunk_http_event_collector.py
    Splunk HTTP event submission class

    Remember: Friends don't let friends send in non Common Information Model data: http://docs.splunk.com/Documentation/CIM/latest/User/Overview
        Please use CIM friendly field names when sending in data.
"""

import requests
import json
import time
import socket
import threading
import Queue

__author__ = "george@georgestarcher.com (George Starcher)"
http_event_collector_debug = False 
http_event_collector_SSL_verify = False

# Default batch max size to match splunk's default limits for max byte 
# See http_input stanza in limits.conf; note in testing I had to limit to 100,000 to avoid http event collector breaking connection
# Auto flush will occur if next event payload will exceed limit
_max_content_bytes = 100000 
_number_of_threads = 10

class http_event_collector:

            
    def __init__(self,token,http_event_server,host="",http_event_port='8088',http_event_server_ssl=True,max_bytes=_max_content_bytes):
        self.token = token
        self.batchEvents = []
        self.maxByteLength = max_bytes
        self.currentByteLength = 0
        self.flushQueue = Queue.Queue(0)
        for x in range(_number_of_threads):
            t = threading.Thread(target=self.batchThread)
            t.daemon = True
            t.start()
        
    
        # Set host to specified value or default to localhostname if no value provided
        if host:
            self.host = host
        else:
            self.host = socket.gethostname()

        # Build and set server_uri for http event collector
        # Defaults to SSL if flag not passed
        # Defaults to port 8088 if port not passed

        if http_event_server_ssl:
            protocol = 'https'
        else:
            protocol = 'http'
            
        self.server_uri = '%s://%s:%s/services/collector/event' % (protocol, http_event_server, http_event_port)

        if http_event_collector_debug:
            print self.token
            print self.server_uri                

    def sendEvent(self,payload,eventtime=""):
        # Method to immediately send an event to the http event collector

        headers = {'Authorization':'Splunk '+self.token}

        # If eventtime in epoch not passed as optional argument and not in payload, use current system time in epoch
        if not eventtime and 'time' not in payload:
            eventtime = str(int(time.time()))
            payload.update({'time':eventtime})

        # Fill in local hostname if not manually populated
        if 'host' not in payload:
            payload.update({"host":self.host})

        # send event to http event collector
        event = []
        event.append(json.dumps(payload))

        self.flushQueue.put(event)
        if http_event_collector_debug:
            print "Single Submit: Sticking the event on the queue."
        self.waitUntilDone()

    def batchEvent(self,payload,eventtime=""):
        # Method to store the event in a batch to flush later

        # Fill in local hostname if not manually populated
        if 'host' not in payload:
            payload.update({"host":self.host})

        # If eventtime in epoch not passed as optional argument and not in payload, use current system time in epoch
        if not eventtime and 'time' not in payload:
            eventtime = str(int(time.time()))
            payload.update({"time":eventtime})
            
        payloadString = json.dumps(payload)
        payloadLength = len(payloadString)

        if (self.currentByteLength+payloadLength) > self.maxByteLength:
            if http_event_collector_debug:
                print "Auto Flush: Sticking the batch on the queue."
            self.flushQueue.put(self.batchEvents)
            self.batchEvents = []
            self.currentByteLength = 0

        self.batchEvents.append(payloadString)
        self.currentByteLength += payloadLength
        
    def batchThread(self):
        # Threads to send batches of events.
        
        while True:
            if http_event_collector_debug:
                print "Events received on thread. Sending to Splunk."
            payload = " ".join(self.flushQueue.get())
            headers = {'Authorization':'Splunk '+self.token}
            requests.post(self.server_uri, data=payload, headers=headers, verify=http_event_collector_SSL_verify)
            self.flushQueue.task_done()
            
    def waitUntilDone(self):
        # Block until all flushQueue is empty.
        self.flushQueue.join()
        return


    def flushBatch(self):
        if http_event_collector_debug:
            print "Manual Flush: Sticking the batch on the queue."
        self.flushQueue.put(self.batchEvents)
        self.batchEvents = []
        self.currentByteLength = 0
        self.waitUntilDone()

def main():

    # This main method is a test and example section. Normal use you would import this class into your code you wish to send

    # Create event collector object, default SSL and HTTP Event Collector Port
    http_event_collector_key = "PUTCOLLECTORKEYHERE"
    http_event_collector_host = "HOSTNAMEOFTHECOLLECTOR"
 
    testevent = http_event_collector(http_event_collector_key, http_event_collector_host)

    # Start event payload and add the metadata information
    payload = {}
    payload.update({"index":"temp"})
    payload.update({"sourcetype":"txt"})
    payload.update({"source":"test"})
    payload.update({"host":"mysterymachine"})

    # Add 5 test events
    for i in range(5):
        payload.update({"event":{"action":"success","message":"individual hello world","event_id":i}})
        testevent.sendEvent(payload)

    # Batch add 50000 test events
    for i in range(500000):
        payload.update({"event":{"action":"success","message":"batch hello world","event_id":i}})
        testevent.batchEvent(payload)
    testevent.flushBatch()

    exit()

if __name__ ==  "__main__":

    main()
