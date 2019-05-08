#!/usr/bin/env python3

import os
from collections import OrderedDict

class MinecraftConfig(OrderedDict):
    def __init__(self, world_path, filename="server.properties"):
        super().__init__()
        self._filename = os.path.join(world_path, filename)
        if os.path.exists(self._filename):
            self.reload()
        
    def reload(self):
        comment_num = 0
        self.clear()
        with open(self._filename, 'r') as f:
            lines = [x.strip() for x in f.readlines()]
        for line in lines:
            if '=' in line:
                key, value = line.split('=', 1)
                self[key] = value
            else:
                self['__{}'.format(comment_num)] = line
                comment_num += 1
    
    def save(self):
        with open(self._filename, 'w') as f:
            for key, value in self.items():
                if key.startswith('__'):
                    f.write("{!s}\n".format(value))
                else:
                    f.write("{!s}={!s}\n".format(key, value))
