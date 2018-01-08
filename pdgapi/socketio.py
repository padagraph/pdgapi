import threading
import requests
import datetime


class Socketio(object):
    
    def __init__(self, host="http://localhost:3000" ):
        self.host = host
        self.new_event =  "%s/new_event/" % host
        self.multi_events = "%s/multi_events" % host
        
    #def build_job(chan, action, properties):
        #def job():
            #time = datetime.datetime.now().isoformat()
            ##print chan, action, properties 
            #requests.post(CONFIG['url'] + str(chan),
                    #json = {'action': action, 'properties': properties, 'time': time },
                    #timeout=0.2)
        #return job



    def broadcast_multi(self, messages):
        try:
            time = datetime.datetime.now().isoformat()
            for event in messages:
                event['time'] = time

            requests.post(self.multi_events,
                    json = {'messages': messages },
                    timeout=0.2)
        except Exception as e:
            print e

    def broadcast(self, chan, action, data):

        try:
            time = datetime.datetime.now().isoformat()
            data['time'] = time
            data['action'] = action
            requests.post(self.new_event + str(chan),
                    json = data,
                    timeout=0.2)
        except Exception as e:
            print e

        #th = threading.Thread(target=build_job(chan, action, properties))
        #th.start()
