#!/usr/bin/env python
import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
from tornado import gen
import os.path
import uuid
import json
import random
from datetime import datetime

from tornado.options import define, options

SIZE = 100, 60
define("port", default=8000, help="run on the given port", type=int)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", IndexHandler),
            (r"/gamesocket", GameSocketHandler),
            (r"/files/(.*)", tornado.web.StaticFileHandler, {'path': 'files'}),
        ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            autoreload=True,
            debug=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class GameSocketHandler(tornado.websocket.WebSocketHandler):
    players = set()
    apples = [[random.randint(0, SIZE[0]), random.randint(0, SIZE[1])]
        for i in range(20)
    ]

    def get_compression_options(self):
        # Non-None enables compression with default options.
        return {}

    def open(self):
        x_real_ip = self.request.headers.get("X-Real-IP")
        self.ip = x_real_ip or self.request.remote_ip
        self.direction = 'up'
        self.score = 0
        self.nick = 'Anonymous'
        self.die()
        GameSocketHandler.players.add(self)
        GameSocketHandler.send_updates()

    def die(self):
        while 1:
            x, y = random.randint(0, SIZE[0]), random.randint(0, SIZE[1])
            if any(x == sx and y == sy for player in GameSocketHandler.players
                for sx, sy in player.snake):
                    continue
            if any(x == sx and y == sy for sx, sy in GameSocketHandler.apples):
                    continue

            break
        self.snake = [[x, y]]

    @classmethod
    def add_apple(cls):
        while 1:
            x, y = random.randint(0, SIZE[0]), random.randint(0, SIZE[1])
            if any(x == sx and y == sy for player in GameSocketHandler.players
                for sx, sy in player.snake):
                    continue
            if any(x == sx and y == sy for sx, sy in GameSocketHandler.apples):
                    continue

            break
        cls.apples.append([x, y])


    def on_close(self):
        GameSocketHandler.players.remove(self)

    @classmethod
    def send_updates(cls):
        #logging.info("sending message to %d waiters", len(cls.players))
        data = {
            'snakes': [player.snake for player in cls.players],
            'apples': cls.apples,
            'scores': [[player.nick, player.score] for player in cls.players]
        }
        for waiter in cls.players:
            try:
                data['head'] = waiter.snake[-1]
                waiter.write_message(data)
            except:
                logging.error("Error sending message", exc_info=True)

    def on_message(self, message):
        message = json.loads(message)
        logging.info("Got message %r" % message)
        if 'direction' in message:
            if message['direction'] not in ['up', 'left', 'right', 'down']:
                return
            self.direction = message['direction']
        elif 'nick' in message:
            self.nick = message['nick'].replace('<', '').replace('>', '')

def game_tick():
    for player in GameSocketHandler.players:
        d = {'up': (0,-1), 'down': (0,1), 'left': (-1, 0), 'right': (1,0)}
        player.snake.append([player.snake[-1][0]+d[player.direction][0], player.snake[-1][1]+d[player.direction][1]])
        if player.snake[-1] in GameSocketHandler.apples:
            GameSocketHandler.apples.remove(player.snake[-1])
            GameSocketHandler.add_apple()
            player.score += 1
        else:
            player.snake.pop(0)
        if player.snake[-1][0] < 0 or player.snake[-1][1] < 0 or player.snake[-1][0] >= SIZE[0] or player.snake[-1][1] >= SIZE[1]:
            player.die()
        for enemy in GameSocketHandler.players:
            if enemy != player and player.snake[-1] in enemy.snake:
                player.die()
        if player.snake[-1] in player.snake[:-1]:
            player.die()
    GameSocketHandler.send_updates()

def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    tornado.ioloop.PeriodicCallback(game_tick, 100, io_loop = tornado.ioloop.IOLoop.current()).start()
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()

