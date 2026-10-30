"""Process-local guard for Decky #975; no Loader files or other plugins changed.

The affected socket loop repeatedly consumes empty EOF without yielding, starving
async _unload. Park just that exhausted reader until the process shuts down.
Reference: https://github.com/SteamDeckHomebrew/decky-loader/issues/975
"""
import asyncio
import sys


def guard_decky_socket(modules=None):
    modules = sys.modules if modules is None else modules
    for name in ('decky_loader.localplatform.localsocket', 'localplatform.localsocket'):
        socket_class = getattr(modules.get(name), 'UnixSocket', None)
        receive = getattr(socket_class, '_read_single_line', None)
        dispatch = getattr(socket_class, '_listen_for_method_call', None)
        if receive is None or dispatch is None:
            continue
        if getattr(receive, '_ally_eof_guard', False):
            return True
        reader_names = getattr(getattr(receive, '__code__', None), 'co_names', ())
        loop_names = getattr(getattr(dispatch, '__code__', None), 'co_names', ())
        if 'at_eof' in loop_names or 'readuntil' not in reader_names or '_read_single_line' not in loop_names:
            return False  # Native fix or unknown implementation: do not replace.

        async def guarded_receive(instance, stream, *args, **kwargs):
            if stream.at_eof():
                await asyncio.Future()
            payload = await receive(instance, stream, *args, **kwargs)
            if not payload and stream.at_eof():
                await asyncio.Future()
            return payload

        guarded_receive._ally_eof_guard = True
        socket_class._read_single_line = guarded_receive
        return True
    return False
