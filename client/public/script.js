(function(){
	let players = [];
	let maxScore, player_name;

	let getColorFromPlayer = function (player) {
		if (player.points < 1) return {
			bgColor: "rgba(0,0,0,0)",
			color: "white"
		}
		var color = (player.name.split("").reduce((a,b) => a + b.charCodeAt(0) * 100, 0) % (1 << 24)).toString(16).padStart(6, "0")
		var r = parseInt(color.substring(0, 2), 16); // hexToR
		var g = parseInt(color.substring(2, 4), 16); // hexToG
		var b = parseInt(color.substring(4, 6), 16); // hexToB
		var uicolors = [r / 255, g / 255, b / 255];
		var c = uicolors.map((col) => {
			if (col <= 0.03928) {
				return col / 12.92;
			}
			return Math.pow((col + 0.055) / 1.055, 2.4);
		});
		var L = (0.2126 * c[0]) + (0.7152 * c[1]) + (0.0722 * c[2]);
		return {
			bgColor: "#" + color,
			color: (L > 0.179) ? "black" : "white"
		};
	}

	let updateVisual = function () {
		for (let player of players) {
			if (player.name === player_name) {
				document.querySelector("#points").innerText = `${player.points}`;
			}
			
			let id = "player_" + player.name;
			let find = document.querySelector(".player-bar#" + id);

			if (find == null && !player.gameovered) {
				find = document.createElement("div");
				find.setAttribute("class", "player-bar");
				find.setAttribute("id", id);
				document.querySelector("#race").appendChild(find)
			}

			if (player.gameovered) { if (find != null) find.remove(); }
			else {
				let isYou = player.name === player_name;
				let x = document.createElement(isYou ? "b" : "p");
				x.innerText = `${player.name}${isYou ? " (You)" : ""} - ${player.points}`;
				find.innerHTML = "";
				find.appendChild(x);
				let colorMode = getColorFromPlayer(player);
				find.setAttribute("style", `color: ${colorMode.color}; width: ${Math.min(100, player.points / maxScore * 100) || 0}%; background-color: ${colorMode.bgColor}`);
			}
		}
	}

	let colors = {
		red: "red",
		green: "green",
		blue: "blue"
	}

	let Timer = {
		endValue: null,
		interval: null,
		set: function () {
			document.querySelector("#timer > #timer-text").innerHTML = this.val();
		},
		val: function () {
			return Math.max(Math.ceil((this.endValue - Date.now()) / 1000), 0)
		},
		start: function (value) {
			this.endValue = value;
			this.clear();
			this.interval = setInterval(function(){
				this.set();
			}.bind(this), 250)
		},
		clear: function () {
			clearInterval(this.interval)
		}
	}

	let NotifBox = {
		element: document.querySelector("#notif-box"),
		content: document.querySelector("#notif-box > #notif-content"),
		timeout: null,
		set: function (text = null, color = null, textcolor = null) {
			if (text) this.content.innerText = text;
			let style = "";
			if (colors[color]) style += `background-color: ${color};`;
			if (textcolor) style += `color: ${textcolor};`
			if (style) this.element.setAttribute("style", style);
			clearTimeout(this.timeout);
			this.timeout = setTimeout(function () {
				this.element.setAttribute("style", "opacity: 0;");
			}.bind(this), 5000)
		}
	}

	let question = document.querySelector("#question");
	let sub = document.querySelector("#subtitle");

	let inputBox = document.querySelector("#input");

	let socket = new WebSocket(String(WS_ENDPOINT).replace(/^ws\:\/\/0\.0\.0\.0\:(\d+)\//, "ws://localhost:$1/"));

	socket.sendJSON = function(e) {
		return this.send(JSON.stringify(e))
	}

	socket.onmessage = function (e) {
		let { data } = e;
		try {
			data = JSON.parse(data);
			spec = data.data;

			if (spec && spec.time_end != null) Timer.start(spec.time_end);

			if (spec && spec.points_to_win != null) {
				maxScore = spec.points_to_win;
				document.querySelector("#winning-points").innerText = maxScore;
				updateVisual();
			}

			switch (data.name) {
				case "message":
					NotifBox.set(spec, "blue", "white");
					break;
				case "error":
				case "disqualified":
					NotifBox.set(spec, "red", "white");
					break;
				case "register_success":
					NotifBox.set("Registered successfully.", "green", "white");
					player_name = spec;
					inputBox.setAttribute("type", "number");
					document.querySelector("#text").innerText = `What's your answer?`;
					document.querySelector("#name").innerText = player_name;
					document.querySelector("#profile").removeAttribute("style");
					window.onbeforeunload = function () {
						return "Leave game?";
					}
					updateVisual();
					break;
				case "round_started":
					question.innerText = `${spec.num1} ${spec.operator} ${spec.num2} = ?`;
					sub.innerText = "Be the first correct one to gain more points!";
					break;
				case "round_ended":
					question.innerText = spec.not_started ? "Waiting for more players..." : `${spec.num1} ${spec.operator} ${spec.num2} = ${spec.result.join(" or ")}`;
					sub.innerText = spec.game_end ? "Next game will start shortly..." : "Next round will start shortly...";
					break;
				case "correct_answer":
					NotifBox.set("Correct Answer!", "green", "white");
					break;
				case "wrong_answer":
					NotifBox.set("Wrong Answer :(", "red", "white");
					break;
				case "players_info":
					players = spec;
					updateVisual();
					break;
				case "player_left": {
					let element = document.querySelector(".player-bar#player_" + spec);
					if (element != null) element.remove();
					break;
				}
				case "winner":
					question.innerText = spec;
					sub.innerHTML = "Wins the game!<br>Next game will start shortly...";
					break;
			}
		}
		catch (e) { console.log(e) }
	}

	inputBox.addEventListener("keypress", function (e) {
		if (e.keyCode != 13 || inputBox.value == '') return;
		e.preventDefault();
		if (player_name == null) {
				socket.sendJSON({
				name: "register",
				nickname: inputBox.value
			});
			NotifBox.set("Registering...", "blue", "white");
		}
		else {
			socket.sendJSON({
				name: "answer",
				answer: inputBox.value
			});
			NotifBox.set("Sending Answer...", "blue", "white");
		}

		inputBox.value = ""
	});
})();