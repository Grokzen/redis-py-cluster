#!/usr/bin/env python3

"""
redis cluster command line interface
"""

import re
import socket
from argparse import ArgumentParser
from rediscluster import StrictRedisCluster
from pprint import pprint


def get_parser():
    """Get argument parser -> ArgumentParser"""

    parser = ArgumentParser()

    parser.add_argument(
        '--node', '-n', help='hostname of any cluster node',
        default='127.0.0.1'
    )
    parser.add_argument(
        '--pw', '-a', help='pw to auth, same as for redis-cli'
    )
    parser.add_argument(
        '--port', '-p', help='port where redis is running', default=7000
    )

    return parser


def get_redis_config():
    """Get password and port from local installed redis instance

    These credentials are used, when no values are passed to the
    ArgumentParser
    """

    with open('/etc/redis/redis.conf', 'r') as config_file:
        for line in config_file:
            if re.match('^requirepass(.*)', line):
                password = line.split()[1]
            if re.match('^port(.*)', line):
                port = line.split()[1]
    return port, password


def main():
    args = get_parser().parse_args()

    port, password = get_redis_config()

    if port:
        args.port = port
    if password:
        args.pw = password

    startup_nodes = [{
        'host': args.node,
        'port': args.port
    }]

    rc = StrictRedisCluster(
        startup_nodes=startup_nodes,
        decode_responses=True,
        password=args.pw
    )

    while True:
        cmd_input = input(socket.gethostname() + ':' + args.port + '> ')
        if len(cmd_input) > 0:
            cmd = cmd_input.split()[0]
            cmd_args = cmd_input.split()[1:]

            if cmd in ('quit', 'exit'):
                raise SystemExit
            elif cmd == '?':
                for supported_command in sorted(dir(rc)):
                    if not supported_command.startswith("_"):
                        pprint(supported_command)
            else:
                if hasattr(rc, cmd):
                    method_to_call = getattr(rc, cmd)
                    pprint(method_to_call(*cmd_args))
                else:
                    pprint('The command ' + cmd + ' is not implemented')


if __name__ == '__main__':
    main()
