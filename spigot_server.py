#!/usr/bin/env python3

import subprocess
import os
import tarfile
import datetime
import time
import socketserver
import struct
import json
import threading
import queue
import re
import sys

class MinecraftProcess:
    # (time, thread, level, text)
    _log_re = a = re.compile(r'^\[(\d{2}:\d{2}:\d{2})\]\s+\[([^/]+)\/(\w+)\]:\s+(.*)')
   
    _regexes = {
        'player_action': dict(
            # (player, src_ip, src_port, entity_id, region, x, y, z)
            player_join = re.compile(r'^([^[]+)\[.*?/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})\] logged in with entity id (\d+) at \(\[([^[]+).*?\](-?\d+\.\d+),\s+(-?\d+\.\d+),\s+(-?\d+\.\d+)\)'),

            # (player, reason)
            player_disconnect = re.compile(r'^(\S+) lost connection: (.*)'),

            # (player)
            player_left_game = re.compile(r'^(\S+) has left the game'),
        ),
        'command_result': dict(
            # (player)
            player_opped = re.compile(r'^Made (\S+) a server operator'),

            # (player)
            player_deopped = re.compile(r'^Made (\S+) no longer a server operator'),
            
            # (player)
            player_whitelisted = re.compile(r'^Added (\S+) to the whitelist'),
            
            # (player)
            player_unwhitelisted = re.compile(r'^Removed (\S+) from the whitelist'),

            # (player, reason)
            player_banned = re.compile(r'^Banned (\S+): (.*)'),

            # (player)
            player_unbanned = re.compile(r'^Unbanned (\S+)'),

            # (startup_time)
            startup_done = re.compile(r'^Done \((\d+\.\d+)s\)! For help, type'),

            save_off = re.compile(r'^Automatic saving is now disabled'),
            save_all = re.compile(r'^Saving the game \(this may take a moment!\)'),
            save_all_done = re.compile(r'^Saved the game'),
            save_on = re.compile(r'^Automatic saving is now enabled'),
            nothing_changed_op = re.compile(r'^Nothing changed. The player already is an operator'),
            nothing_changed_deop = re.compile(r'^Nothing changed. The player is not an operator'),
            nothing_changed_ban = re.compile(r'^Nothing changed. The player is already banned'),
            nothing_changed_unban = re.compile(r"^Nothing changed. The player isn't banned"),
            already_whitelisted = re.compile(r'^Player is already whitelisted'),
            already_not_whitelisted = re.compile(r'^Player is not whitelisted'),
            player_not_found = re.compile(r'^That player does not exist'),
        )
    }

    def __init__(self, jar_file, world_path, *, java_exe="java", backup_path=None):
        self._jar_file = os.path.realpath(jar_file)
        self._world_path = os.path.realpath(world_path)
        self._process = None
        self._java_exe = java_exe
        self._stdout_thread = None
        self._running = False
        self._stop_commanded = False
        self._command_lock = threading.RLock()
        self._queues = {'player_action': queue.Queue(), 'command_result': queue.Queue()}

        if backup_path is None:
            self._backup_path = os.path.join(self._world_path, "backups")
            if not os.path.exists(self._backup_path):
                os.mkdir(self._backup_path)
        else:
            self._backup_path = os.path.realpath(backup_path)

    def _reader_stdout(self):
        while self._running:
            line = self._process.stdout.readline().decode('utf-8').strip()

            # Parse log entry.
            log_match = self._log_re.match(line)
            if log_match is None:
                continue
            time_, thread, level, text = log_match.groups()

            # Determine what's being logged.
            
            #print('text', text)
            for regex_type, regexes in self._regexes.items():
                for message_type, regex in regexes.items():
                    matches = regex.match(text)
                    if matches is not None:
                        result = (message_type,) + matches.groups()
                        self._queues[regex_type].put(result)

            # This is temporary until I get some kind of plugin registration going.
            while not self._queues['player_action'].empty():
                self._queues['player_action'].get()

    def _clear_queues(self):
        with self._command_lock:
            for q in self._queues.values():
                while not q.empty():
                    q.get()

    def start(self):
        with self._command_lock:
            if self._process is not None:
                return False, 'ALREADY_STARTED'
            self._process = subprocess.Popen([self._java_exe, "-jar", self._jar_file], cwd=self._world_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE)#, stderr=subprocess.PIPE)
            self._running = True
            self._stdout_thread = threading.Thread(target=self._reader_stdout)
            self._stdout_thread.start()
            results = self._wait_for_result('startup_done')
            return True, float(results[1])

    def query(self):
        return self._process is not None and self._process.poll() is None

    def send_command(self, cmd, wait=None):
        with self._command_lock:
            a = self._process.stdin.write((cmd + "\n").encode('utf-8'))
            self._process.stdin.flush()
            return self._wait_for_result(wait)

    def _wait_for_result(self, wait=None):
        if wait is None:
            return

        while True:
            result = self._queues['command_result'].get()
            if isinstance(wait, str) and wait == result[0]:
                return result
            elif isinstance(wait, tuple) and result[0] in wait:
                return result
            else:
                print("unknown", result, file=sys.stderr)

    def do_backup(self):
        with self._command_lock:
            self.send_command('save-off', 'save_off')
            try:
                self.send_command('save-all')
                self._wait_for_result('save_all')
                self._wait_for_result('save_all_done')
                filename = os.path.join(self._backup_path, datetime.datetime.now().isoformat() + ".tar.xz")
                with tarfile.open(filename, 'w:xz') as backup:
                    for dimension in ('world', 'world_nether', 'world_the_end'):
                        backup.add(os.path.join(self._world_path, dimension), dimension)
                return True, filename
            except Exception as ex:
                return False, repr(ex)
            finally:
                self.send_command('save-on', 'save_on')

    def say(self, what):
        self.send_command('say ' + what)
        return True, None

    def ban(self, player, reason=None):
        cmd = 'ban ' + player
        if reason is not None:
            cmd += ' ' + reason
        result = self.send_command(cmd, ('player_banned', 'nothing_changed_ban', 'player_not_found'))
        return result[0] == 'player_banned' and player == result[1], player

    def unban(self, player):
        result = self.send_command('pardon ' + player, ('player_unbanned', 'nothing_changed_unban', 'player_not_found'))
        return result[0] == 'player_unbanned' and player == result[1], player

    def whitelist(self, player):
        result = self.send_command('whitelist add ' + player, ('player_whitelisted', 'already_whitelisted', 'player_not_found'))
        return result[0] == 'player_whitelisted' and player == result[1], player

    def unwhitelist(self, player):
        result = self.send_command('whitelist remove ' + player, ('player_unwhitelisted', 'already_not_whitelisted', 'player_not_found'))
        return result[0] == 'player_unwhitelisted' and player == result[1], player

    def op(self, player):
        result = self.send_command('op ' + player, ('player_opped', 'nothing_changed_op', 'player_not_found'))
        return result[0] == 'player_opped' and player == result[1], player

    def deop(self, player):
        result = self.send_command('deop ' + player, ('player_deopped', 'nothing_changed_deop', 'player_not_found'))
        return result[0] == 'player_deopped' and player == result[1], player

    def wait(self):
        self._process.wait()
        if self._stop_commanded:
            self._running = False
        self._stdout_thread.join()

    def stop(self):
        if self._process is None:
            return False, 'ALREADY_STOPPED'
        with self._command_lock:
            self._stop_commanded = True
            self.send_command("stop")
            self.wait()
            self._process = None
            self._threads = {'stderr': None, 'stdout': None}
            self._stop_commanded = False
            return True, None

    def pid(self):
        if self._process is not None:
            return self._process.pid
        return None

class CommandHandler(socketserver.BaseRequestHandler):
    allowed_methods = ('start', 'query', 'do_backup', 'say', 'ban', 'unban', 'whitelist', 'unwhitelist', 'op', 'deop', 'stop', 'pid')

    def handle(self):
        size = struct.unpack("I", self.request.recv(4))[0]
        raw_json = self.request.recv(size)

        try:
            decoded_json = json.loads(raw_json.decode('utf-8'))

            if isinstance(decoded_json, list) and len(decoded_json) > 0:
                method = decoded_json[0]
                args = decoded_json[1:]

                if method not in self.allowed_methods:
                    raise RuntimeError('{} is not an allowed method'.format(method))
                
                method = getattr(self.server._mc_process, method)
                reply = [True] + list(method(*args))
                
        except Exception as ex:
            reply = [False, None, repr(ex)]
        
        self.request.sendall(json.dumps(reply).encode('utf-8'))

class StreamServer(socketserver.UnixStreamServer):
    def __init__(self, *args, mc_proc, **kw):
        super().__init__(*args, **kw)
        self._mc_process = mc_proc

def launch_socket_server(socket, world, spigot_jar):
    p = MinecraftProcess(spigot_jar, world)
    print('Server starting...', file=sys.stderr)

    good_start = True

    try:
        start_time = p.start()
    except KeyboardInterrupt:
        print("Server will shut down as soon as it's done starting...")
        good_start = False
        start_time = 0.0

    print('Server started in {} seconds.'.format(start_time), file=sys.stderr)
    if good_start:
        try:
            server = StreamServer(socket, CommandHandler, mc_proc=p)
        except OSError as ex:
            print('Unable to create socket:', repr(ex), file=sys.stderr)
            good_start = False

    if good_start:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

    print('Server stopping.', file=sys.stderr)
    if good_start:
        server.shutdown()
    p.stop()
    if os.path.exists(socket):
        os.unlink(socket)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--socket', type=os.path.realpath, required=True, help="Location of socket file.")
    parser.add_argument('-w', '--world', type=os.path.realpath, default=None, help="Location of minecraft world.")
    parser.add_argument('-j', '--spigot-jar', type=os.path.realpath, default=None, help="Location of spigot JAR file.")
    parser.add_argument('command', nargs='?', default=None, help="Command to send to running server.")
    parser.add_argument('args', nargs='*', default=None, help="Command arguments.")
    args = parser.parse_args()

    if args.command is None:
        if args.world is None or args.spigot_jar is None:
            print("In order to start a minecraft server, you must specify -w and -j.", file=sys.stderr)
            print("Allowed commands:", ' '.join(CommandHandler.allowed_methods), file=sys.stderr)
            sys.exit(1)

        # For now, just keep the queues clear.

        launch_socket_server(args.socket, args.world, args.spigot_jar)

    else:
        to_send = [args.command]
        if args.command == 'say' and len(args.args) > 0:
            to_send.append(' '.join(args.args))
        elif args.command in ('start', 'query', 'do_backup', 'stop', 'pid') and len(args.args) == 0:
            pass
        elif args.command in ('unban', 'whitelist', 'unwhitelist', 'op', 'deop') and len(args.args) == 1:
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

