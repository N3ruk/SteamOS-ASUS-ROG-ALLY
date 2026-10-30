import asyncio
from types import SimpleNamespace
import unittest
from py_modules.loader_compat import guard_decky_socket


class GuardTests(unittest.IsolatedAsyncioTestCase):
    def socket(self):
        class Socket:
            async def _read_single_line(self, stream):
                try:
                    return (await stream.readuntil()).decode()
                except asyncio.IncompleteReadError:
                    return ''
            async def _listen_for_method_call(self, stream):
                return await self._read_single_line(stream)
        return Socket

    async def test_eof_wait_yields_and_is_cancelable_instead_of_spinning(self):
        socket = self.socket()
        self.assertTrue(guard_decky_socket({'localplatform.localsocket':SimpleNamespace(UnixSocket=socket)}))
        stream = asyncio.StreamReader();stream.feed_eof()
        task = asyncio.create_task(socket()._read_single_line(stream))
        await asyncio.sleep(.01)
        self.assertFalse(task.done())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task

    async def test_normal_payload_and_idempotence_preserved(self):
        socket = self.socket();module={'localplatform.localsocket':SimpleNamespace(UnixSocket=socket)}
        self.assertTrue(guard_decky_socket(module));original=socket._read_single_line
        self.assertTrue(guard_decky_socket(module));self.assertIs(socket._read_single_line,original)
        stream=asyncio.StreamReader();stream.feed_data(b'hello\n')
        self.assertEqual(await socket()._read_single_line(stream),'hello\n')

    async def test_native_eof_check_or_missing_class_not_patched(self):
        self.assertFalse(guard_decky_socket({}))
        socket=self.socket()
        async def fixed(instance,stream):
            if stream.at_eof(): return
        socket._listen_for_method_call=fixed
        original=socket._read_single_line
        self.assertFalse(guard_decky_socket({'localplatform.localsocket':SimpleNamespace(UnixSocket=socket)}))
        self.assertIs(socket._read_single_line,original)
