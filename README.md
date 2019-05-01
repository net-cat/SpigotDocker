# SpigotDocker
Terrible Dockerfile and support script for a single Spigot instance.

## Rationale
* I have a Docker server and I want to host a single Minecraft instance for my friends with basic management functionality through "docker exec"
* I don't want to have to run some fancy-pants web front-end for commercial Minecraft hosts with eleventy billion instances of Minecraft.
* I just want to be able to "docker run" an instance, then "docker run" a new instance keeping the same volume when it's time to upgrade.
* I want to be able to support non-traditional management methods, such as through a Telegram or Discord channel.

This system has no aspirations of being anything other than what it is.
* If you need a little more (such as Discord hooks or a simple web interface,) I'll consider pull requests.
* If you need a lot more (such the ability to manage multiple instances,) might I suggest PufferPanel or McMyAdmin.

## Instructions

***NOTE: This is still in early, early alpha.***

Build the containers:

	docker build -t <tag name> -f Dockerfile . --build-arg spigot_ver=1.14 --build-arg minecraft_eula=true

Run the instance:

	docker run -d -v <volume name>:/spigotmc -p 25565:25565 --name <container name> <tag name>

You can add a `_JAVA_OPTIONS` environtment variable, if you want.

	docker run -e _JAVA_OPTIONS="-Xmx24G" -d -v <volume name>:/spigotmc -p 25565:25565 --name <container name> <tag name>

You can manage the server with docker exec.

	docker exec -it <container name> cmd <command> <params>

The commands available are:

* `op <player>` - Give player operator status.
* `deop <player>` - Revoke player operator status.
* `whitelist <player>` - Add player to server whitelist.
* `unwhitelist <player>` - Remove player from server whitelist.
* `ban <player>` - Bad player from server.
* `unban <player>` - Unban player from server.
* `start` - Start server (if stopped)
* `stop` - Stop server (if started)
* `query` - Query if server is running.
* `do_backup` - Place a .tar.xz of the world in the backups directory.
* `say <text>` - Say something to the players on the server.
* `pid` - Get the pid of the server process

## TODO
* Move "eula=true" from build to run.
* Instructions
* Backup needs to back up a few more things than it does.

## License
Yes, picking AGPL was intentional. I don't intend for this to be used commercially and that seemed like the best way to prevent that from ever happening.

