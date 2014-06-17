# -*- coding: utf-8 -*-


def send_to_connection_by_key(func):
    def inner(self, key, *args, **kwargs):
        conn = self.get_connection_by_key(key)
        return func(conn, key, *args, **kwargs)
    return inner
