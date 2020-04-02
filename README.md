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

### BuildTools Instructions

Build the BuildTools container:

	docker build -f Dockerfile-buildjar -t spigot_builder .

Create an output directory for the BuildTools container:

	mkdir buildtools-output

Run the BuildTools container:

	docker run -d -v `pwd`/buildtools_output:/home/buildtools --name buildtools_runner spigot_builder

At this point, you can invoke BuildTools as much as you need. All the output will end up in the output directory.

	docker exec -it buildtools_runner buildtools # With the default version.
	docker exec -it buildtools_runner buildtools --rev 1.14.4 # With a specific version

Once you have built all the versions of spigot you need, you can stop or kill the container.

	docker kill buildtools_runner

You can then delete or start the container as needed.

	docker container rm buildtools_runner
	docker start buildtools_runner

If you need to update BuildTools, just delete the container and image and repeat the steps.

	docker image rm spigot_builder

### Running Spigot or Vanilla Minecraft

Please Note:

* The ``X_Y_Z`` and ``X.Y.Z`` notations refers to the version of Minecraft you are installing. The ``Z`` component can be omitted for new releases.
* Vanilla Minecraft works fine. You can skip the BuildTools step and use Mojang-provided ``server.jar`` in place of ``spigot-X.Y.Z.jar``

Build the image, providing the JAR file from the previous step. (Or literally any Spigot JAR file.)

	docker build -t spigot_runner_X_Y_Z -f Dockerfile . --build-arg spigot_bin=buildtools_output/spigot-X.Y.Z.jar

Run the instance:

	docker run -d -v <volume name>:/spigotmc -p 25565:25565 --name <container name> spigot_runner_X_Y_Z

You can add a `_JAVA_OPTIONS` environtment variable, if you want.

	docker run -e _JAVA_OPTIONS="-Xmx24G" -d -v <volume name>:/spigotmc -p 25565:25565 --name <container name> spigot_runner

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

You can also agree to the Minecraft EULA by running `accept-eula` script with `exec`. This only needs to be done once per world. Once this is done, you can use `cmd start` command to start the server and the server will come up automatically on container start.

## TODO
* Scheduled backups. (Because asyncio is wonderful.)
* Figure out whay `cmd stop` hangs.

## License
Yes, picking AGPL was intentional. I don't intend for this to be used commercially and that seemed like the best way to prevent that from ever happening.

