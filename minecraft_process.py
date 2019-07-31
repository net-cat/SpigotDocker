#!/usr/bin/env python3
import asyncio
import os
import datetime
import re
import base64

from rcon import RCONMessage, MinecraftRCON
from minecraft_config import MinecraftConfig

class MinecraftProcess:
    def __init__(self, jar_file, world_path, *, java_exe="java", backup_path=None):
        self._jar_file = os.path.realpath(jar_file)
        self._world_path = os.path.realpath(world_path)
        self._java_exe = java_exe
        self._process = None
        self._comms = None
        self._backup_lock = asyncio.Lock()
        self._backup_process = None
        self._command_lock = asyncio.Lock()
        self._rcon_port = None
        self._rcon_password = None
        
        if backup_path is None:
            self._backup_path = os.path.join(self._world_path, "backups")
            if not os.path.exists(self._backup_path):
                os.mkdir(self._backup_path)
        else:
            self._backup_path = os.path.realpath(backup_path)
        

    async def _process_waiter(self):
        if self._process is not None:
            await self._process.wait()
            self._process = None
            self._rcon_port = None
            self._rcon_password = None
            
    def _force_enable_rcon(self):
        #['broadcast-rcon-to-ops', 'rcon.port', 'enable-rcon', 'rcon.password']
        config = MinecraftConfig(self._world_path)
        changed = False
        if config.get('enable-rcon', 'false') != 'true':
            config['enable-rcon'] = 'true'
            changed = True
        if 'rcon.port' not in config:
            config['rcon.port'] = '25575'
            changed = True
        if not config.get('rcon.password', ''):
            config['rcon.password'] = base64.b64encode(os.urandom(48), b'./').decode('ascii')
            changed = True
        if changed:
            config.save()
        return int(config['rcon.port']), config['rcon.password']
        
    async def start(self):
        if self._process is not None:
            return False, 'Process already started. (pid={})'.format(self._process.pid)
        
        self._rcon_port, self._rcon_password = self._force_enable_rcon()
        
        self._process = await asyncio.create_subprocess_exec(
            self._java_exe, "-jar", self._jar_file, cwd=self._world_path,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
            )

        asyncio.ensure_future(self._process_waiter())

        await self._reconnect()
        if self._process is None:
            return False, "Process started but didn't stay up."
        if self._comms is None:
            return False, "Process started but couldn't establish RCON connection. (pid={})".format(self._process.pid)
        return True, "Process started and RCON connection established. (pid={})".format(self._process.pid) 

    async def _reconnect(self):
        while self._process is not None:
            new_comms = MinecraftRCON("127.0.0.1", self._rcon_port)
            try:
                await new_comms.connect()
            except ConnectionRefusedError:
                print('Connection refused.')
                await asyncio.sleep(3)
            except Exception:
                print('another exception?')
                await asyncio.sleep(3)
            else:
                print('Connection worked.')
                self._comms = new_comms
                break
        
        if self._comms is not None:
            if not await self._comms.send_password(self._rcon_password):
                await self._comms.close()
                self._comms = None

    async def query(self):
        if self._process is not None:
            return True, self._process.pid
        return False, None

    async def do_backup(self):
        if self._backup_lock.locked():
            return False, "Backup already in progress."
        async with self._backup_lock, self._command_lock:
            # Do the prep work
            await self._comms.send_command('say', 'Backing up the world...')
            await self._comms.send_command('save-off')
            try:
                await self._comms.send_command('save-all')
        
                # Backups can run long, so spin it off in a separate process.
                backup_filename = os.path.join(self._backup_path, datetime.datetime.now().isoformat() + ".tar.bz2")
                self._backup_process = await asyncio.create_subprocess_exec(
                    'tar', '-cjf', backup_filename, 'world', 'world_nether', 'world_the_end',
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                    )
                stdout, stderr = await self._backup_process.communicate()
                retcode = self._backup_process.returncode
                self._backup_process = None
        
                # Cleanup
                if retcode == 0:
                    await self._comms.send_command('say', '... backup done!')
                    return True, "Backed up world to {}".format(backup_filename)
                await self._comms.send_command('say', '... backup FAILED!')
                return False, "Failed to back up world to {}. (return={})".format(backup_filename, retcode), stdout.decode('utf-8'), stderr.decode('utf-8')
            finally:
                await self._comms.send_command('save-on')

    async def say(self, what):
        async with self._command_lock:
            await self._comms.send_command('say', what)
            return True, None
    
    async def _command_template(self, *cmd, success_re=None):
        async with self._command_lock:
            if self._process is None:
                return False, 'Minecraft process is not running. You can start it again by calling "start".'
            if self._comms is None:
                await self._reconnect()
            recv_msg = await self._comms.send_command(*cmd)
            response = recv_msg.payload.decode('utf-8')
            if success_re is not None:
                success = re.match(success_re, response) is not None
            else:
                success = bool(response)
            return success, response

    async def ban(self, player, reason=None):
        cmd = ['ban', player]
        if reason is not None:
            cmd.append(reason)
        return await self._command_template(*cmd, success_re=r'^Banned (\S+): (.*)')

    async def unban(self, player):
        return await self._command_template('pardon', player, success_re=r'^Unbanned (\S+)')

    async def whitelist(self, player):
        return await self._command_template('whitelist', 'add', player, success_re=r'^Added (\S+) to the whitelist')

    async def unwhitelist(self, player):
        return await self._command_template('whitelist', 'remove', player, success_re=r'^Removed (\S+) from the whitelist')

    async def op(self, player):
        return await self._command_template('op', player, success_re=r'^Made (\S+) a server operator')

    async def deop(self, player):
        return await self._command_template('deop', player, success_re=r'^Made (\S+) no longer a server operator')

    async def wait(self):
        await self._process.wait()

    async def stop(self):
        async with self._command_lock:
            if self._process is None:
                return False, 'The Minecraft process is already stopped.'
            await self._comms.send_command("stop")
            await self.wait()
            # self._process will be set to none by self._process_waiter

