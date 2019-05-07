import asyncio
import struct
import random
from collections import namedtuple

class RCONMessage:
    request_id_sequence = random.randint(1, 0x7fffffff)
    SIZE = struct.Struct("I")
    PREFIX = struct.Struct("II")
    SUFFIX = struct.Struct("H")
    
    def __init__(self, *args):
        self._pad = 0
        if len(args) == 0:
            self._size = None
            self._type = None
            self._payload = None
            self._next_request_id()
        elif len(args) == 1:
            self.decode(args[0])
        elif len(args) == 2:
            self.type, self.payload = args
            self._next_request_id()
        elif len(args) == 3:
            self.type, self.payload, self.request_id = args
        else:
            raise TypeError("(raw_data) or (type, payload, [request_id])")
            
    def _next_request_id(self):
        self._request_id = self.request_id_sequence
        self.__class__.request_id_sequence += 1
    
    @property
    def type(self):
        return self._type
    
    @type.setter
    def type(self, value):
        value = int(value)
        if value < 0 or value > 0xffffffff:
            raise ValueError("Must be in uint32_t range.")
        self._type = value
        
    @property
    def payload(self):
        return self._payload
    
    @payload.setter
    def payload(self, value):
        if not isinstance(value, bytes):
            raise TypeError("Payload must be bytes.")
        self._payload = value
        self._size = self.PREFIX.size + self.SUFFIX.size + len(value)
        
    @property
    def request_id(self):
        return self._request_id
    
    @request_id.setter
    def request_id(self, value):
        if value < 0 or value > 0xffffffff:
            raise ValueError("Must be in uint32_t range.")
        self._request_id = int(value)
    

    def encode(self):
        if None in (self._size, self._type, self._payload):
            raise ValueError("Incomplete message.")

        raw_data = bytearray()
        raw_data += self.SIZE.pack(self._size)
        raw_data += self.PREFIX.pack(self._request_id, self._type)
        raw_data += self._payload
        raw_data += self.SUFFIX.pack(self._pad)
        
        return bytes(raw_data)
    
    def decode(self, raw_data):
        if not isinstance(raw_data, bytes):
            raise TypeError("Can only decode bytes.")
        self._size = self.SIZE.unpack_from(raw_data)[0]
        self._request_id, self._type = self.PREFIX.unpack_from(raw_data, self.SIZE.size)
        self._payload = raw_data[self.SIZE.size + self.PREFIX.size:-self.SUFFIX.size]
        self._pad = self.SUFFIX.unpack_from(raw_data, -self.SUFFIX.size)[0]
        
    def __str__(self):
        return "{}({}, {!r}, {})".format(self.__class__.__name__, self.type, self.payload, self.request_id)

class RCON:
    SendAndReceive = namedtuple("SendAndReceive", ('send_msg', 'recv_msg'))

    def __init__(self, addr, port):
        self._addr = addr
        self._port = int(port)
        
    async def connect(self):
        self._reader, self._writer = await asyncio.open_connection(self._addr, self._port)
        
    async def recv_msg(self):
        raw_data = await self._reader.readexactly(RCONMessage.SIZE.size)
        size = RCONMessage.SIZE.unpack(raw_data)[0]
        raw_data += await self._reader.readexactly(size)
        return RCONMessage(raw_data)
    
    async def send_msg(self, *args):
        if len(args) == 1 and isinstance(args[0], RCONMessage):
            msg = args[0]
        elif len(args) == 2 or len(args) == 3:
            msg = RCONMessage(*args)
        else:
            raise TypeError("(RCONMessage) or (type, payload, [request_id])")
        self._writer.write(msg.encode())
        await self._writer.drain()
        return msg
        
    async def send_and_recv(self, *args):
        send_msg = await self.send_msg(*args)
        recv_msg = await self.recv_msg()
        return self.SendAndReceive(send_msg, recv_msg)
        
    async def close(self):
        self._writer.close()
        if(hasattr(self._writer, 'wait_closed')):
            await self._writer.wait_closed()

class MinecraftRCON(RCON):
    class MinecraftRCONError(Exception): pass
    
    def __init__(self, addr, port):
        super().__init__(addr, port)
        
    async def send_password(self, password):
        if isinstance(password, str):
            password = password.encode('utf-8')
        if not isinstance(password, bytes):
            raise TypeError("Password must be bytes or str")

        send_msg, recv_msg = await self.send_and_recv(3, password)
        if recv_msg.type == 0xffffffff:
            return False
        if recv_msg.request_id == send_msg.request_id:
            return True
        raise MinecraftRCONError("Minecraft auth neither failed nor succeeded: {!s}".format(recv_msg))
        
    async def send_command(self, *cmd):
        cmd = [x.encode('utf-8') if isinstance(x, str) else x for x in cmd]
        cmd = b' '.join(cmd)
        return (await self.send_and_recv(2, cmd)).recv_msg
        
async def module_main(server, port, password, command):
    mcrcon = MinecraftRCON(server, port)
    
    try:
        await mcrcon.connect()
    except ConnectionRefusedError:
        print("Connection failed.")
        return
    print("Authenticated:", await mcrcon.send_password(password))
    print("Command:", command)
    print("Response:", await mcrcon.send_command(command))
    await mcrcon.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", "-P", help="Minecraft RCON Password")
    parser.add_argument("--addr", help="Minecraft RCON Server Address")
    parser.add_argument("--port", "-p", type=int, help="Minecraft RCON Server Address")
    parser.add_argument("cmd", nargs="+", help="Command")
    args = parser.parse_args()
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(module_main(args.addr, args.port, args.password, ' '.join(args.cmd)))
    loop.close()
    
    
    
    
    
    
    
    