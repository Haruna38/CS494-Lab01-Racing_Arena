import os

# SERVER PROPERTIES

SERVER_HOST = '0.0.0.0'
SERVER_PORT = int(os.environ.get('GAME_SERVER_PORT') or 4000)
SERVER_MAX_PLAYERS = 10 # max players
SERVER_DEBUG_MESSAGE = True # log every client message into console

# GAME PROPERTIES

MAX_COUNTDOWN_TIME = 60 # seconds
MIN_COUNTDOWN_TIME = 10 # seconds
ROUND_END_WAITING_TIME = 5 # seconds
GAME_END_WAITING_TIME = 10 # seconds

# export
os.environ['GAME_SERVER_PORT'] = str(SERVER_PORT)
