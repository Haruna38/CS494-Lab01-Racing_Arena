import json
from server.socket_handler import *
from threading import Timer
import random
import time
import re
import os

random.seed(time.time())

class Player:
	def __init__(self, client) -> None:
		self.client = client
		self.name = None
		self.points = 0
		self.answered = None
		self.registered = False # only set this to True after they registered
		self.justJoined = True # immunity to point decrease if joined mid-match, but also receives less points
		self.penalty = 0 # gameovered after a penalty
		self.gameovered = False

class PlayerManager:
	def __init__(self) -> None:
		self.list = []

	def find(self, client) -> Player | None:
		for player in self.list:
			if player.client == client:
				return player
		return None
	
	def add(self, client) -> Player:
		player = Player(client)
		self.list.append(player)
		return player
	
	def remove(self, client) -> Player | None:
		for player in self.list:
			if player.client == client:
				self.list.remove(player)
				return player
			
		return None

class Game:
	def __init__(self) -> None:
		server = self.server = SocketServer()
		server.setMessageHandler(self.onMessage)
		server.setClientCloseHandler(self.onClientClose)
		server.setClientConnectHandler(self.onClientConnect)
		server.setServerOnStartup(self.startRound)
		self.players = PlayerManager()
		self.round = Set(self)

	def generateRaceValues(self):
		self.winningPoints = random.randint(3, 26)
		self.countdown = MAX_COUNTDOWN_TIME # seconds, decrease 1s every round
	
	def start(self):
		os.environ['WS_ENDPOINT'] = f"ws://{SERVER_HOST}:{SERVER_PORT}/"
		self.server.start()

	def startRound(self):
		self.round.start()

	def sendData(self, cli, name, content):
		message = {
			"name": name,
			"data": content
		}

		if cli == None:
			# send to all players
			for player in self.players.list:
				try:
					player.client.sendJSON(message)
				except Exception as e:
					continue

			return

		try:
			cli.sendJSON(message)
		except Exception as e:
			return
	
	def sendError(self, cli, errorMsg):
		return self.sendData(cli, "error", errorMsg)
	
	def sendMessage(self, cli, msg):
		return self.sendData(cli, "message", msg)

	def onMessage(self, cli, msg):
		try:
			data = json.loads(msg)

			player = self.players.find(cli)

			if player == None:
				return self.sendError(cli, "Who are you?")
			
			match data['name']:
				case 'register':
					try:
						if player.registered:
							return self.sendError(cli, "You are already registered.")
						
						nickname = str(data['nickname'])
						if nickname == None or nickname == "":
							return self.sendError(cli, "Nickname must not be blank.")
						
						if re.match(r'^[a-zA-Z0-9_]{1,10}$', nickname) == None:
							return self.sendError(cli, "Nickname must only from 1-10 character(s) and only contains alphanumerics and/or underscores (_).")
						
						for player in self.players.list:
							if player.registered and player.name == nickname:
								return self.sendError(cli, "Someone already picked this nickname. Please try another.")
							
						player.registered = True
						player.name = nickname

						self.sendData(None, "players_info", [{
							"name": player.name,
							"points": player.points,
							"gameovered": player.gameovered
						}])

						if self.round.notEnoughPlayers:
							self.round.start()

						return self.sendData(cli, "register_success", player.name)
					except Exception as e:
						print("register (debug):", e)
						return self.sendError(cli, "Please provide a nickname.")
				case 'answer':
					try:
						if not player.registered:
							return self.sendError(cli, "Please register first.")
						
						if player.gameovered:
							return self.sendError(cli, "Sorry, you are disqualified for this set.")
						
						if self.round.roundEnd:
							return self.sendError(cli, "Not in a round.")
						
						if player.answered != None:
							return self.sendError(cli, "You already gave the answer for this question.")
						
						answer = data['answer']
						if type(answer) != str and type(answer) != int:
							return self.sendError(cli, "Invalid answer.")
						
						if type(answer) == str:
							if re.match(r'^\-{0,1}[0-9]+$', answer) == None:
								return self.sendError(cli, "Invalid answer.")
							else:
								answer = int(answer)
						
						player.answered = answer

						self.round.answers.append(player)

						self.sendMessage(cli, "Answer received.")
					except Exception as e:
						print("answer (debug):", e)
						return self.sendError(cli, "Please provide an answer.")
		except Exception as e:
			print("handle:", e)
			return

	def onClientClose(self, cli):
		player = self.players.remove(cli)

		if player != None and player.registered:
			self.sendData(None, "player_left", player.name)

	def playerStatus (self, client = None):
		playersData = []

		for player in self.players.list:
			if not player.registered:
				continue

			playersData.append({
				"name": player.name,
				"points": player.points,
				"gameovered": player.gameovered
			})

		self.sendData(client, "players_info", playersData)

	def onClientConnect(self, cli):
		newPlayer = self.players.add(cli)

		self.round.status(newPlayer.client)

		self.playerStatus(newPlayer.client)


class Set:
	def __init__(self, manager: Game) -> None:
		self.manager = manager
		self.roundEnd = True
		self.endGame = True
		self.endTime = None
		self.winner = None
		self.result = None
		self.num1 = None
		self.num2 = None
		self.operator = None
		self.notStarted = True
		self.notEnoughPlayers = True

	def restartRound (self):
		# restart player stuff
		for player in self.manager.players.list:
			player.answered = None

			if player.registered:
				player.justJoined = False

			if self.endGame:
				player.points = 0
				player.penalty = 0
				player.gameovered = False
		
		if self.noPlayers():
			self.notStarted = True
			self.notEnoughPlayers = True

			self.status()
		else:
			try:
				self.answers = []
				
				if self.endGame:
					self.manager.generateRaceValues()
				else:
					self.manager.countdown = max(self.manager.countdown - 1, MIN_COUNTDOWN_TIME)

				if self.endGame:
					self.manager.playerStatus()

				self.operator = random.choice(["+", "-", "*", "/", "%"])
				self.num1 = random.randrange(-10000, 10000, 1)
				self.num2 = random.randrange(-10000, 10000, 1)
				self.roundEnd = False
				self.endGame = False
				self.endTime = int((time.time() + self.manager.countdown) * 1000)
				self.winner = None
				self.notStarted = False
				self.notEnoughPlayers = False

				self.status()
			except Exception as e:
				print("restart:", e)

			Timer(self.manager.countdown, self.endRound, []).start()

	def noPlayers (self) -> bool:
		for player in self.manager.players.list:
			if player.registered and not player.gameovered:
				return False

		return True

	def status (self, client = None):
		if self.roundEnd:
			if not self.notStarted:
				self.manager.playerStatus(client)

				self.manager.sendData(client, "round_ended", {
					"num1": self.num1,
					"num2": self.num2,
					"operator": self.operator,
					"result": self.result,
					"points_to_win": self.manager.winningPoints,
					"time_end": self.endTime,
					"game_end": self.endGame
				})

				if self.endGame and self.winner != None:
					self.manager.sendData(client, "winner", self.winner.name)
			else:
				self.manager.sendData(client, "round_ended", {
					"not_started": True,
					"time_end": self.endTime,
					"game_end": self.endGame
				})
		else:
			self.manager.sendData(client, "round_started", {
				"time_end": self.endTime,
				"num1": self.num1,
				"num2": self.num2,
				"operator": self.operator,
				"points_to_win": self.manager.winningPoints
			})

	def start(self):
		self.notEnoughPlayers = False
		self.endRound(True)
		
	def endRound (self, init = False):
		try:
			self.roundEnd = True

			if not init:
				# calculate result
				result = self.result = int(eval(f'{self.num1} {self.operator} {self.num2}'))

				firstCorrect = None

				# check list of answered
				for player in self.answers:
					if player.answered == result:
						player.penalty = 0

						self.manager.sendData(player.client, "correct_answer", "")

						if firstCorrect == None:
							firstCorrect = player
						else:
							player.points += 1
					else:
						player.answered = None
						self.answers.remove(player)

				# check for all players to check how many failed
				totalPointsLost = 0
				for player in self.manager.players.list:
					if (not player.registered) or player.gameovered:
						continue

					if player.answered == None:
						# incorrect answer
						self.manager.sendData(player.client, "wrong_answer", "")
						if player.justJoined:
							continue

						if player.points > 0:
							totalPointsLost += 1
							player.points -= 1
						
						player.penalty += 1
						if player.penalty >= 3: # wrong answer 3 times in a row
							player.gameovered = True
							self.manager.sendData(player.client, "disqualified", "You are disqualified for many wrong answers in a row.")

				# give more points to first correct one
				if firstCorrect != None:
					if firstCorrect.justJoined:
						# nerf to prevent smurfers
						totalPointsLost //= 2
					
					firstCorrect.points += max(totalPointsLost, 1) + (0 if firstCorrect.justJoined else 1)

				# check if someone wins yet?
				self.winner = None
				for player in self.answers:
					if player.points >= self.manager.winningPoints and (self.winner == None or self.winner.points < player.points):
						self.winner = player

				if self.winner != None:
					self.endGame = True

			if self.noPlayers():
				self.endGame = True

		except Exception as e:
			print("game_end:", e)

		waiting_time = GAME_END_WAITING_TIME if self.endGame else ROUND_END_WAITING_TIME

		self.endTime = int((time.time() + waiting_time) * 1000)

		try:
			self.status()
		except Exception as e:
			print("game_status:", e)

		Timer(waiting_time, self.restartRound, []).start()