#! /bin/bash

# docker run -it --rm --privileged -p 8888:8888 --device /dev/gpiochip0 zinen2/alpine-pigpiod

docker run -it --rm --name gpioexperiment \
                           --device=/dev/gpiochip0 \
                           --device=/dev/gpiomem \
                           gpio \
                           python /src/fan.py \
                           --min-temp=19 \
                           --min-run-time=10 \
                           --min-sleep-time=10 \
                           --min-temp-offset=0 \
                           --verbose \
                           --sensor

