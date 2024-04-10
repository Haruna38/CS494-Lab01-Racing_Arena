from server.server_enums import *
import socket
from threading import Thread
import re
import base64
import hashlib
import json

# debug omit, yeah
def debug (*msg):
	if SERVER_DEBUG_MESSAGE:
		return print(*msg)
	
	return

# something to parse a WS Payload request
class WSPayload:
	def __init__(self, data):
		self.fromBytes(data)

	def fromBytes (self, data):
		if data == None:
			self.initialized = False
			return
		self.data = data
		self.parse()

		return self

	def parse (self):
		try:
			# first block
			data = self.data[0]
			self.fin = data >> 7

			self.reserved = []
			for i in [6, 5, 4]:
				self.reserved.append((data & (1 << i)) >> i)

			self.opcode = data & 0xf
			self.text = self.opcode == 1

			# second block
			data = self.data[1]
			self.bit_mask = data >> 7
			self.payload_len = data & 0x7f

			# check payload len
			extended_payload_bytes = 0
			if self.payload_len == 126:
				extended_payload_bytes = 2
			elif self.payload_len == 127:
				extended_payload_bytes = 8

			if extended_payload_bytes != 0:
				self.payload_len = 0
				for i in range(0, extended_payload_bytes):
					self.payload_len = (self.payload_len << 8) | self.data[2 + i]

			nextFrame = extended_payload_bytes + 2

			# get mask
			self.mask = []
			if self.bit_mask:
				self.mask = self.data[nextFrame : nextFrame + 4]
				nextFrame += 4
					

			# get obf payload data
			payloads = self.data[nextFrame:]
			self.payload = []
			for p in payloads:
				self.payload.append(p)
			
			# deobf payload data
			if len(self.mask) > 0:
				for i in range(0, len(self.payload)):
					self.payload[i] = self.mask[i % 4] ^ self.payload[i]

			self.payload = bytes(self.payload)

			self.initialized = True
		except Exception as e:
			# payload malformed
			# print(e, self.data)
			self.initialized = False
		
	def information (self):
		debug("WSPayload: ", self.data)
		debug("FIN:", self.fin)
		debug("Reserved:", self.reserved)
		debug("OPCode:", self.opcode)
		debug("Bit Mask:", self.bit_mask)
		debug("Payload Length:", self.payload_len)
		debug("Mask:", self.mask)
		debug("Payload:", self.payload)

# Wrapper for Socket Client (to support WS and such).
class SocketClient:
	def __init__(self, socket, address, WSKey = None) -> None:
		self.address = address
		self.socket = socket
		self.setWSKey(WSKey)

	# set WS Key by given client key
	def setWSKey (self, WSKey) -> None:
		try:
			self.WSKey = base64.b64encode(hashlib.sha1(bytes([ord(i) for i in (WSKey + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')])).digest()).decode()
			self.WebSocket = self.WSKey != None
			return True
		except:
			self.WSKey = None
			self.WebSocket = False
			return False

	# setup and verify connection with WebSocket instance
	def setupWSConnection (self, WSKey) -> bool:
		result = self.setWSKey(WSKey)
		if result:
			oldWebSocket = self.WebSocket
			self.WebSocket = False # temp remove to allow send raw data
			self.send(f'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {self.WSKey}\r\n\r\n')
			debug(f"[{self.addressString()}] WebSocket connection setup successfully.")
			self.WebSocket = oldWebSocket

		return result

	# check if message contains WebSocket setup, and setup if present and this socket client
	# has not been initialized with WebSocket connection yet.
	def checkAndSetupWSConnectionIfEligible (self, msg) -> bool:		
		if len(msg) >= 1 and (not self.WebSocket) and 'Connection: Upgrade\r\n' in msg and 'Upgrade: websocket\r\n' in msg:
			socketKey = re.findall(r'Sec\-WebSocket\-Key:\s*(.+)\r\n', msg)

			if socketKey == None:
				return False
			
			debug(f"[{self.addressString()}] Obtained client WS Key: '{socketKey[0]}'.")

			return self.setupWSConnection(socketKey[0])
		
		return False

	def addressString (self) -> str:
		return f'{self.address[0]}:{self.address[1]}'
	
	def send (self, data):
		sendAsText = type(data) == str

		if type(data) != bytes:
			data = data.encode('utf-8')

		if self.WebSocket: # handle differently for WS
			payload = bytes([
				(1 << 7) | (000 << 4) | (1 if sendAsText else 2), # fin - reserved(3) - opcode
				0, # mask - payload len, calculate later
				# this part will be inserted later to calculate len (0-2-8 bytes extended)
				# 0x0, 0x0, 0x0, 0x0, # no masks
			]) + data # raw payload data

			payloadLen = len(payload)
			payloadheaderSize = payloadLen
			extraPayloadLenBytes = 0

			if payloadLen >= 0x10000: # larger than 2 bytes
				extraPayloadLenBytes = 8
				payloadheaderSize = 127
			elif payloadLen >= 126:
				extraPayloadLenBytes = 2
				payloadheaderSize = 126

			# what to put to payload len header (2nd byte)
			payload = payload[:1] + bytes([(payload[1] << 7) | payloadheaderSize]) + payload[2:]

			# extended payload length
			if extraPayloadLenBytes != 0:
				exLenBytes = []
				for i in range(0, extraPayloadLenBytes):
					exLenBytes.insert(0, payloadLen & 0xff)
					payloadLen >>= 8

				payload = payload[:2] + bytes(exLenBytes) + payload[2:]

			data = payload + b'\r\n'
			
		self.socket.send(data)

	def sendJSON(self, dict):
		data = json.dumps(dict, skipkeys=True)
		return self.send(data)

	oldPayload = bytes([])

	def get_data(self, delim = 1024, toBytes = False) -> str | bytes:
		msg = self.socket.recv(delim)

		binary = True

		if self.WebSocket:
			data = WSPayload(msg)

			resetPayload = False

			if not data.initialized:
				msg = bytes([])
			elif data.opcode == 8: # close frame
				self.socket.close()
				resetPayload = True
				msg = bytes([])
			else:
				self.oldPayload += data.payload
				msg = bytes([])
				if data.fin == 1: # this is the final frame
					resetPayload = True
					msg = self.oldPayload
					binary = not data.text
			
			if resetPayload:
				self.oldPayload = bytes([])
			
		if not toBytes:
			msg = ''.join([chr(i) for i in msg])

		return msg, binary
	
	def close (self):
		return self.socket.close()

# Socket Clients Manager instance.
class SocketClientManager:
	def __init__(self) -> None:
		self.clients = []

	def find(self, address) -> SocketClient | None:
		for client in self.clients:
			if client.address == address:
				return client
		
		return None

	def add(self, socket, address, WSKey = None) -> SocketClient:
		# check if client exist first
		newClient = self.find(address)

		new = False

		if newClient == None:
			newClient = SocketClient(socket, address, WSKey)
			self.clients.append(newClient)
			new = True

		return newClient, new
	
	def tryClose(self, client):
		try:
			client.close()
		except:
			pass
	
	def closeAtIndex(self, index, closeClient = False):
		if index >= 0 and index < len(self.clients):
			cli = self.clients[index]
			if closeClient:
				self.tryClose(cli)
			
			self.clients.pop(index)
	
	# close a socket client and removes from list of sockets
	def closeSocket(self, client, dontTryClose = False):
		# try closing the client first
		if not dontTryClose:
			self.tryClose(client)
		
		# remove socket from list of client
		if client in self.clients:
			self.closeAtIndex(self.clients.index(client))

	# close a socket client by address and removes from list of sockets
	def closeSocketByAddress(self, address):
		index = 0

		for client in self.clients:
			if client.address == address:
				break

			index += 1

		if index < len(self.clients):
			self.closeAtIndex(index, True)

# The Socket Server instance.
class SocketServer:
	def __init__(self) -> None:
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		self.socket = s
		self.clients = SocketClientManager()
		self.news = []

	def start (self):
		self.socket.bind((SERVER_HOST, SERVER_PORT))

		self.socket.listen(SERVER_MAX_PLAYERS)

		debug(f'[Socket Startup] Server started at \'ws://{SERVER_HOST}:{SERVER_PORT}\'.')

		self.safeHandler(self.onServerStartup)

		while True:
			c, addr = self.socket.accept()     # Establish connection with client.
			cli, new = self.clients.add(c, addr)
			
			if new:
				debug(f'[{cli.addressString()}] New connection established.')
				self.news.append(cli)
			
			Thread(target=self.on_new_client, args=[cli]).start()

	def safeHandler (self, func, *args):
		try:
			if func != None:
				func(*args)
		except Exception as e:
			debug(e)

	def setMessageHandler(self, func):
		self.onMessage = func
	
	def setClientCloseHandler(self, func):
		self.onClientClose = func

	def setClientConnectHandler(self, func):
		self.onClientConnect = func

	def setServerOnStartup(self, func):
		self.onServerStartup = func

	onMessage = None
	onClientClose = None
	onClientConnect = None
	onServerStartup = None
	
	def on_new_client(self, cli: SocketClient):
		try:
			while True:
				msg, isBinary = cli.get_data(2048) # up to 2KB only
				if len(msg) < 1:
					continue

				notWS = not cli.checkAndSetupWSConnectionIfEligible(msg)

				if cli in self.news:
					self.news.remove(cli)
					self.safeHandler(self.onClientConnect, cli)

				if notWS:
					# get socket data
					debug(f'[{cli.addressString()}] Received message (Type: {"Binary" if isBinary else "Text (UTF-8)"}):')
					debug(msg)

					self.safeHandler(self.onMessage, cli, msg)
					
		except Exception as e:
			# debug(e)
			self.clients.closeSocket(cli, True)
			debug(f'[{cli.addressString()}] Connection closed by client.')
			self.safeHandler(self.onClientClose, cli)

			