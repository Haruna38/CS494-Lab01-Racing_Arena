import os

# CLIENT PROPERTIES

CLIENT_HOST = '0.0.0.0'
CLIENT_PORT = int(os.environ.get('GAME_CLIENT_PORT') or 1275)

# export
os.environ['GAME_CLIENT_PORT'] = str(CLIENT_PORT)