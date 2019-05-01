ARG java_ver=12

FROM openjdk:$java_ver-jdk-alpine AS build_stage
LABEL version="0.1"

ARG spigot_ver=latest

WORKDIR /root
ADD https://hub.spigotmc.org/jenkins/job/BuildTools/lastBuild/artifact/target/BuildTools.jar /root
RUN apk add git
RUN java -jar BuildTools.jar --rev $spigot_ver

FROM openjdk:$java_ver-alpine
LABEL version="0.1"

ARG minecraft_eula=false

RUN apk --update add python3
RUN mkdir /opt/spigot
WORKDIR /opt/spigot
COPY --from=build_stage --chown=root:root /root/spigot-*.jar spigot.jar
COPY --chown=root:root spigot_server.py .
COPY --chown=root:root cmd.sh cmd
RUN chmod 644 spigot.jar
RUN chmod 755 spigot_server.py
RUN chmod 755 cmd
WORKDIR /root
RUN mkdir /spigotmc
WORKDIR /spigotmc
RUN adduser minecraft -h /spigotmc -D
RUN echo "eula=$minecraft_eula" > eula.txt
RUN chown -R minecraft .
VOLUME /spigotmc
EXPOSE 25565/tcp
USER minecraft
ENV PATH=/opt/spigot:$PATH
CMD ["cmd", "-j", "/opt/spigot/spigot.jar", "-w", "/spigotmc"]


