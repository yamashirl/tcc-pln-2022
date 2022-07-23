#!/bin/bash

if test "$1" == "up"; then
    echo up

    podman pod create \
        --name tcc \
        --publish 8888:80 \
    	--publish 8000:8000

    podman container run \
        --name tika-server \
        --detach \
        --pod tcc \
        docker.io/apache/tika:latest-full

#    podman container run \
#        --name jupyter-notebook \
#        --detach \
#        --env       TIKA_CLIENT_ONLY=1 \
#        --env       TIKA_SERVER_ENDPOINT="http://localhost:9998" \
#        --pod tcc \
#        --volume    tcc_volume:/notebook \
#        localhost/jupyter:spacylg

    podman container run \
	--name mysql-server \
	--detach \
	--env		MYSQL_ROOT_PASSWORD=see-cret \
	--pod tcc \
	--volume 	tcc_database:/var/lib/mysql \
    	docker.io/library/mysql:latest
    
    podman container run \
        --name django-server \
	--tty \
	--detach \
	--pod tcc \
	--volume tcc_web:/webproject \
	localhost/django:latest

#    echo sleeping for 5 seconds
#    sleep 5

#    podman container logs jupyter-notebook

elif test "$1" == "down"; then
    echo down
    podman container stop tika-server
    #podman container stop jupyter-notebook
    podman container stop mysql-server
    podman container stop django-server

    echo removing
    podman container rm tika-server
    #podman container rm jupyter-notebook
    podman container rm mysql-server
    podman container rm django-server
    podman pod rm tcc
else
    echo unkwnown
fi

