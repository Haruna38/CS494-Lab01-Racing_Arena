from client.client import *
from server.game import *
from threading import Thread

# start server
Thread(target=Game().start,args=[]).start()

# start client
Thread(target=Client().start,args=[]).start()