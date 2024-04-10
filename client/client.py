from flask import Flask, render_template
from client.client_enums import *
import os

class Client:
	def __init__(self) -> None:
		self.app = Flask(__name__, static_url_path='', static_folder='./public')
		
		@self.app.route("/") 
		def index(): 
			return render_template('index.html', WS_ENDPOINT=os.environ['WS_ENDPOINT'])

	def start(self):
		self.app.run(host=CLIENT_HOST, port=CLIENT_PORT)
		