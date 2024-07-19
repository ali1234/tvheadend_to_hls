#!/usr/bin/env python3

import pathlib
import shlex

import uvicorn
import os
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
import time
import subprocess

import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject


#Read settings
config={}
config["hls_local_path"]="/tmp/tvhtohls/hls"
config["hls_http_path"]="/hls/"
config["static_local_path"]=pathlib.Path(__file__).parent / 'static'
config["static_http_path"]="/"

for setting in config.keys():
    if setting in os.environ:
        config[setting]=os.environ[setting]

if not os.path.isdir(config["hls_local_path"]):
    print("hls_local_path '%s' is not a directory" % config["hls_local_path"])
    exit()



class Streamer(FastAPI):
    def __init__(self):
        super().__init__()
        self.pipeline = Gst.Pipeline.new("pipeline")

        self.source = Gst.ElementFactory.make("videotestsrc", "source")
        self.source.set_property("is-live", True)
        self.overlay = Gst.ElementFactory.make("textoverlay", "overlay")
        self.overlay.set_property("text", "TEST")
        self.overlay.set_property("valignment", "center")
        self.overlay.set_property("font-desc", "sans normal 80")
        self.scaler = Gst.ElementFactory.make("videoconvertscale", "scaler")
        caps = Gst.Caps.from_string("video/x-raw, width=480, height=270, format=I420")
        self.filter = Gst.ElementFactory.make("capsfilter", "filter")
        self.filter.set_property("caps", caps)
        self.encoder = Gst.ElementFactory.make("x264enc", "encoder")
        self.parser = Gst.ElementFactory.make("h264parse", "parser")
        self.sink = Gst.ElementFactory.make(f"hlssink2", "hls")
        self.sink.set_property("max-files", 5)
        self.sink.set_property("send-keyframe-requests", True)
        self.sink.set_property("target-duration", 2)
        self.sink.set_property("location", config['hls_local_path'] + '/segment%05d.ts')
        self.sink.set_property("playlist-location", config["hls_local_path"] + "/stream.m3u8")

        self.pipeline.add(self.source)
        self.pipeline.add(self.overlay)
        self.pipeline.add(self.scaler)
        self.pipeline.add(self.filter)
        self.pipeline.add(self.encoder)
        self.pipeline.add(self.parser)
        self.pipeline.add(self.sink)

        self.source.link(self.overlay)
        self.overlay.link(self.scaler)
        self.scaler.link(self.filter)
        self.filter.link(self.encoder)
        self.encoder.link(self.parser)
        self.parser.link(self.sink)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        self.pipeline.set_state(Gst.State.PLAYING)

    def set_channel(self, channel):
        self.overlay.set_property("text", channel)

    def on_message(self, bus, message):
        err, debug = message.parse_error()
        print("Error: %s" % err, debug)


def main():
    Gst.init(None)
    app = Streamer()

    @app.get("/channel")
    async def read_m3u8(channel: str = ""):
        app.set_channel(channel)
        return Response(content="OK", media_type="text/plain;charset=utf-8")

    app.mount(config["hls_http_path"], StaticFiles(directory=config["hls_local_path"]), name="hls")
    app.mount(config["static_http_path"], StaticFiles(directory=config["static_local_path"], html=True), name="static")

    app.set_channel("test")
    uvicorn.run(app, port=8888, host="0.0.0.0", log_level="info")
    print("Ending program")
    time.sleep(1)


if __name__ == "__main__":
    main()

