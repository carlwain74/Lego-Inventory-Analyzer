"""
gunicorn.conf.py — production server config.

preload_app=True imports app.py (and runs its init_db() call, which creates
tables and migrates the schema) exactly once in the master process before
forking workers. Without this, each worker imports app.py independently and
races the others to create/ALTER the same SQLite file concurrently — this is
what caused workers to crash with "table already exists" and, worse, a
column-rename migration to fail with "no such column" when one worker
renamed a column out from under another mid-check.

Each worker still needs its own SQLite connections rather than sharing the
ones opened in the master pre-fork (not safe across a fork), so post_fork
disposes the inherited connection pool — the next query in that worker
transparently opens a fresh connection.
"""

bind    = '0.0.0.0:5000'
workers = 2
timeout = 120

preload_app = True


def post_fork(server, worker):
    import database
    if database._engine is not None:
        database._engine.dispose()
