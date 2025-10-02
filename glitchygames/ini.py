#!/usr/bin/env python3
"""INI file parsing utility for sprite data."""

import configparser
import logging

log = logging.getLogger("game.ini")
log.addHandler(logging.NullHandler())

config = configparser.RawConfigParser()
config.read("ini.spr")

sprite_section = dict(config["sprite"])
log.info(sprite_section["pixels"])
