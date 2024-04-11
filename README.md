# Racing Arena
**(Python 3 Socket + Flask + HTML/CSS/JS)**

## Requirements
- Python 3.10+

## Prepare
```bash
pip3 install -r requirements.txt
```

## Running
### On a local machine
```bash
python3 main.py
```
### Using Docker
- Check the [docker file](./Dockerfile) for more information.
- You can also change exposed ports in the file.

### Editing
- The program will log the exposed endpoints in the console.
- Change game server properties in [`./server/server_enums.py`](./server/server_enums.py)
- Change client properties in [`./client/client_enums.py`](./client/client_enums.py)
