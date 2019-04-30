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

ARG spigot_ver=latest
ARG spigot_path=/spigotmc
ARG minecraft_eula=false

RUN apk --update add screen
RUN mkdir $spigot_path
WORKDIR $spigot_path
RUN adduser minecraft -h $spigot_path -D
COPY --from=build_stage --chown=minecraft:minecraft /root/spigot-$spigot_ver.jar .
RUN echo "eula=$minecraft_eula" > eula.txt
RUN chown -R minecraft .
VOLUME $spigot_path
EXPOSE 25565/tcp
USER minecraft

