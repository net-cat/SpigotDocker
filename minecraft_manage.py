#!/usr/bin/env python3
import asyncio
import os
import struct
import json
import signal
import sys

from minecraft_process import MinecraftProcess

class MinecraftSocketServer:
    allowed_methods = ('start', 'query', 'do_backup', 'say', 'ban', 'unban', 'whitelist', 'unwhitelist', 'whitelistctl', 'op', 'deop', 'stop')

    def __init__(self, loop):
        self._mc_process = None
        self._server = None
        self._loop = loop
        self._sigint_default = None
        self._sigterm_default = None

    async def _connection_handler(self, reader, writer):
        size = struct.unpack("I", await reader.readexactly(4))[0]
        raw_json = await reader.readexactly(size)
        
        try:
            decoded_json = json.loads(raw_json.decode('utf-8'))
            if isinstance(decoded_json, list) and decoded_json:
                method = decoded_json[0]
                args = decoded_json[1:]
                
                if method not in self.allowed_methods:
                    raise RuntimeError('{} is not an allowed method'.format(method))
                
                method = getattr(self._mc_process, method)
                reply = [True] + list(await method(*args))
        except Exception as ex:
            reply = [False, None, repr(ex)]
        
        writer.write(json.dumps(reply).encode('utf-8'))
        

    async def start(self, socket, world, minecraft_jar):
        self._mc_process = MinecraftProcess(minecraft_jar, world)
        print('Server starting...', file=sys.stderr)
        await self._mc_process.start()
        
        self._server = await asyncio.start_unix_server(self._connection_handler, socket)
        await self._server.wait_closed()
    
        if os.path.exists(socket):
            os.unlink(socket)
    
    async def teardown(self):
        self._server.close()
        self._mc_process.terminate()
        await self._mc_process.wait()
        await self._server.wait_closed()
        
    def set_signal_handlers(self):
        if self._sigint_default is None and self._sigterm_default is None:
            self._sigint_default = signal.signal(signal.SIGINT, self._signal_handler)
            self._sigterm_default = signal.signal(signal.SIGTERM, self._signal_handler)
            return True
        return False
        
    def remove_signal_handlers(self):
        if self._sigint_default is not None:
            signal.signal(signal.SIGINT, self._sigint_default)
            self._sigint_default = None
        if self._sigterm_default is not None:
            signal.signal(signal.SIGTERM, self._sigterm_default)
            self._sigterm_default = None
    
    def _signal_handler(self, signum, frame):
        print("Signal caught. Tearing down server.")
        asyncio.run_coroutine_threadsafe(self.teardown(), self._loop)
        
        
    
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--socket', type=os.path.realpath, required=True, help="Location of socket file.")
    parser.add_argument('-w', '--world', type=os.path.realpath, default=None, help="Location of minecraft world.")
    parser.add_argument('-j', '--minecraft-jar', type=os.path.realpath, default=None, help="Location of minecraft JAR file.")
    parser.add_argument('--accept-eula', action='store_true', help="Agree to the Minecraft EULA for the active world.")
    parser.add_argument('command', nargs='?', default=None, help="Command to send to running server.")
    parser.add_argument('args', nargs='*', default=None, help="Command arguments.")
    args = parser.parse_args()

    if args.accept_eula:
        with open(os.path.join(args.world, 'eula.txt'), 'w', encoding='utf-8') as f:
            f.write("eula=true\n")

    elif args.command is None:
        if args.world is None or args.minecraft_jar is None:
            print("In order to start a minecraft server, you must specify -w and -j.", file=sys.stderr)
            print("Allowed commands:", ' '.join(MinecraftSocketServer.allowed_methods), file=sys.stderr)
            sys.exit(1)

        loop = asyncio.get_event_loop()
        socket_server = MinecraftSocketServer(loop)
        socket_server.set_signal_handlers()
        loop.run_until_complete(socket_server.start(args.socket, args.world, args.minecraft_jar))
        loop.close()

    else:
        to_send = [args.command]
        if args.command == 'say' and len(args.args) > 0:
            to_send.append(' '.join(args.args))
        elif args.command in ('start', 'query', 'do_backup', 'stop') and len(args.args) == 0:
            pass
        elif args.command in ('unban', 'whitelist', 'whitelistctl', 'unwhitelist', 'op', 'deop') and len(args.args) == 1:
            to_send.append(args.args[0])
        elif args.command in ('ban') and len(args.args) > 0:
            to_send += args.args[0:2]
        else:
            print("Command not found or wrong number of arguments.", file=sys.stderr)
            sys.exit(1)

        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(args.socket)
        except FileNotFoundError:
            print('Unable to find socket. Server not running?', file=sys.stderr)
            sys.exit(1)
        raw = json.dumps(to_send).encode('utf-8')
        s.send(struct.pack("I", len(raw)) + raw)
        print(s.recv(65535).decode('utf-8'))

