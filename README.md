# SpigotDocker
Terrible Dockerfile and support script for a single Spigot instance.

# Rationale
* I have a Docker server and I want to host a single Minecraft instance for my friends with basic management functionality through "docker exec"
* I don't want to have to run some fancy-pants web front-end for commercial Minecraft hosts with eleventy billion instances of Minecraft.
* I just want to be able to "docker run" an instance, then "docker run" a new instance keeping the same volume when it's time to upgrade.
* I want to be able to support non-traditional management methods, such as through a Telegram or Discord channel.

This system has no aspirations of being anything other than what it is.
* If you need a little more (such as Discord hooks or a simple web interface,) I'll consider pull requests.
* If you need a lot more (such the ability to manage multiple instances,) might I suggest PufferPanel or McMyAdmin.

# Instructions
TODO

This is still in early, early alpha.
There is a critical piece missing that makes directions pointless. (That is, integrating management script into the Dockerfile.)

# TODO
* Integrate the management script into the Dockerfile
* Move "eula=true" from build to run.
* Move spigot.jar out of the storage volume.
* Instructions

# License
Yes, picking AGPL was intentional. I don't intend for this to be used commercially and that seemed like the best way to prevent that from ever happening.

