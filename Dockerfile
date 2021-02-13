ARG java_ver=14

FROM openjdk:$java_ver-alpine
LABEL version="0.1"

ARG spigot_bin=spigot-*.jar

RUN apk --update add python3
RUN mkdir /opt/spigot
WORKDIR /opt/spigot
COPY --chown=root:root ${spigot_bin} spigot.jar
COPY --chown=root:root minecraft_config.py .
COPY --chown=root:root minecraft_manage.py .
COPY --chown=root:root minecraft_process.py .
COPY --chown=root:root rcon.py .
COPY --chown=root:root cmd.sh cmd
COPY --chown=root:root accept-eula.sh accept-eula
RUN chmod 644 spigot.jar
RUN chmod 755 minecraft_config.py
RUN chmod 755 minecraft_manage.py
RUN chmod 755 minecraft_process.py
RUN chmod 755 rcon.py
RUN chmod 755 cmd
RUN chmod 755 accept-eula
RUN mkdir /spigotmc
WORKDIR /spigotmc
RUN adduser minecraft -h /spigotmc -D
RUN chown -R minecraft .
VOLUME /spigotmc
EXPOSE 25565/tcp
USER minecraft
ENV PATH=/opt/spigot:$PATH
CMD ["cmd", "-j", "/opt/spigot/spigot.jar", "-w", "/spigotmc"]
